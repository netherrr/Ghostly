from __future__ import annotations

import asyncio
import html
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from typing import Any

from bot_api import BotAPI
from config import Settings
from crypto_pay import CryptoPayClient
from db import Database, display_name, decode_json, extract_message_content, extract_file_metadata
from i18n import btn, tr, tr_template
from keyboards import (
    admin_menu,
    admin_method_keyboard,
    admin_methods_keyboard,
    admin_payment_keyboard,
    admin_pending_keyboard,
    admin_plan_keyboard,
    admin_plans_keyboard,
    admin_settings_keyboard,
    admin_single_payment_keyboard,
    back_menu,
    broadcast_chat_keyboard,
    broadcast_menu_keyboard,
    cancel_keyboard,
    connect_keyboard,
    crypto_payment_keyboard,
    inline,
    keyword_delete_keyboard,
    keywords_keyboard,
    lang_keyboard,
    last_deleted_keyboard,
    main_menu,
    manual_payment_keyboard,
    payment_methods_keyboard,
    plans_keyboard,
    referral_keyboard,
    support_keyboard,
    user_broadcast_menu_keyboard,
)


# Bump on every deploy. Shown in /edit and /health so it is obvious at a glance
# whether the running bot actually has the latest code (i.e. Railway redeployed).
BUILD = "2026-06-26 · edit-alerts-v12"


def e(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def split_escaped_for_pre(text: str, budget: int = 3500) -> list[str]:
    """Split raw text so each chunk, once HTML-escaped and wrapped in <pre>,
    stays safely under Telegram's 4096-character per-message limit.

    Long screens (start, connect, privacy …) easily exceed that limit. Embedding
    the whole current text in a single message made the send fail outright, so
    the admin saw only part of the editable text — or nothing. We split on line
    boundaries when possible and hard-split only individual lines that are
    themselves too long, measuring the *escaped* length so multi-character
    escapes (``&lt;``, ``&amp;`` …) never push a chunk over the limit.
    """
    if not text:
        return []
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = line if not current else f"{current}\n{line}"
        if len(html.escape(candidate)) <= budget:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(html.escape(line)) <= budget:
            current = line
            continue
        # A single line longer than the budget: split it character by character.
        piece = ""
        for ch in line:
            if piece and len(html.escape(piece + ch)) > budget:
                chunks.append(piece)
                piece = ch
            else:
                piece += ch
        current = piece
    if current:
        chunks.append(current)
    return chunks


APP_TIMEZONE_NAME = os.getenv("APP_TIMEZONE", "Europe/Kyiv").strip() or "Europe/Kyiv"
try:
    APP_TIMEZONE = ZoneInfo(APP_TIMEZONE_NAME)
except Exception:
    APP_TIMEZONE = timezone.utc
    APP_TIMEZONE_NAME = "UTC"


def dt(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        return value
    try:
        # Telegram/DB timestamps are stored in UTC. Show them in the project/user
        # timezone so deleted-message alerts match the time users see in Telegram.
        if getattr(value, "tzinfo", None) is None:
            value = value.replace(tzinfo=timezone.utc)
        local_value = value.astimezone(APP_TIMEZONE)
        label = "Київ" if APP_TIMEZONE_NAME in {"Europe/Kyiv", "Europe/Kiev"} else APP_TIMEZONE_NAME
        return local_value.strftime("%d.%m.%Y %H:%M") + f" ({label})"
    except Exception:
        return str(value)



def media_kind_label(kind: str, lang: str) -> str:
    labels = {
        "uk": {
            "photo": "фото",
            "video": "відео",
            "animation": "GIF",
            "document": "файл",
            "audio": "аудіо",
            "voice": "голосове",
            "video_note": "кружок",
            "sticker": "стікер",
            "unknown": "медіа",
        },
        "ru": {
            "photo": "фото",
            "video": "видео",
            "animation": "GIF",
            "document": "файл",
            "audio": "аудио",
            "voice": "голосовое",
            "video_note": "кружок",
            "sticker": "стикер",
            "unknown": "медиа",
        },
        "en": {
            "photo": "photo",
            "video": "video",
            "animation": "GIF",
            "document": "file",
            "audio": "audio",
            "voice": "voice message",
            "video_note": "video note",
            "sticker": "sticker",
            "unknown": "media",
        },
    }
    return labels.get(lang, labels["en"]).get(kind, kind or labels.get(lang, labels["en"])["unknown"])


def plan_name(plan: dict[str, Any] | None, lang: str) -> str:
    if not plan:
        return "—"
    return str(plan.get(f"name_{lang}") or plan.get("name_en") or plan.get("code"))


def plan_features(plan: dict[str, Any], lang: str) -> str:
    return str(plan.get(f"features_{lang}") or plan.get("features_en") or "")


def plan_duration_label(days: int | str | None, lang: str) -> str:
    try:
        d = int(days or 0)
    except Exception:
        d = 0
    if d >= 30000:
        return "назавжди" if lang == "uk" else "навсегда" if lang == "ru" else "lifetime"
    if d == 1:
        return "1 день" if lang == "uk" else "1 день" if lang == "ru" else "1 day"
    if d == 3:
        return "3 дні" if lang == "uk" else "3 дня" if lang == "ru" else "3 days"
    if d == 7:
        return "7 днів" if lang == "uk" else "7 дней" if lang == "ru" else "7 days"
    if d == 30:
        return "1 місяць" if lang == "uk" else "1 месяц" if lang == "ru" else "1 month"
    if d == 90:
        return "3 місяці" if lang == "uk" else "3 месяца" if lang == "ru" else "3 months"
    if d == 180:
        return "6 місяців" if lang == "uk" else "6 месяцев" if lang == "ru" else "6 months"
    if d == 365:
        return "1 рік" if lang == "uk" else "1 год" if lang == "ru" else "1 year"
    return f"{d} днів" if lang == "uk" else f"{d} дней" if lang == "ru" else f"{d} days"


def plan_price_uah(plan: dict[str, Any] | None, uah_rate: Any = None) -> Decimal | None:
    if not plan:
        return None
    manual = plan.get("price_uah")
    try:
        if manual is not None and str(manual).strip() not in {"", "0", "0.00", "None", "null"}:
            return Decimal(str(manual)).quantize(Decimal("1"))
    except Exception:
        pass
    try:
        rate = Decimal(str(uah_rate if uah_rate is not None else 0).replace(",", "."))
        if rate > 0:
            return (Decimal(str(plan.get("price_usd") or 0)) * rate).quantize(Decimal("1"))
    except Exception:
        return None
    return None


def plan_price_stars(plan: dict[str, Any] | None) -> int:
    if not plan:
        return 1
    manual = plan.get("price_stars")
    try:
        if manual is not None and str(manual).strip() not in {"", "0", "0.00", "None", "null"}:
            return max(1, int(Decimal(str(manual)).quantize(Decimal("1"))))
    except Exception:
        pass
    # Fallback: roughly 50 Stars per 1 USD package. Admin can set exact values.
    try:
        return max(1, int((Decimal(str(plan.get("price_usd") or 0)) * Decimal("50")).quantize(Decimal("1"))))
    except Exception:
        return 1


def amount_uah_line(amount: Decimal | None, lang: str) -> str:
    if amount is None:
        return ""
    if lang == "en":
        return f"🇺🇦 To pay: {amount} UAH"
    if lang == "ru":
        return f"🇺🇦 К оплате: {amount} грн"
    return f"🇺🇦 До сплати: {amount} грн"


def payment_amount_lines(amount_usd: Decimal, amount_uah: Decimal | None, method_code: str, lang: str) -> str:
    """Plain amount lines safe for insertion into editable templates.

    Dynamic template values must not contain <b>/<code>. If the template was
    edited with Premium emoji, Telegram renders using entities and HTML tags
    inside inserted variables become visible text.
    """
    amount_usd_s = str(amount_usd)
    if method_code == "ua_card" and amount_uah is not None:
        if lang == "en":
            return f"🇺🇦 To pay: {amount_uah} UAH\n💵 USD: ${amount_usd_s}"
        if lang == "ru":
            return f"🇺🇦 К оплате: {amount_uah} грн\n💵 USD: ${amount_usd_s}"
        return f"🇺🇦 До сплати: {amount_uah} грн\n💵 USD: ${amount_usd_s}"
    if lang == "en":
        return f"💵 To pay: ${amount_usd_s}"
    if lang == "ru":
        return f"💵 К оплате: ${amount_usd_s}"
    return f"💵 До сплати: ${amount_usd_s}"


def strip_visible_html_tags(value: str) -> str:
    s = str(value or "")
    replacements = {
        "<b>": "", "</b>": "",
        "<strong>": "", "</strong>": "",
        "<i>": "", "</i>": "",
        "<em>": "", "</em>": "",
        "<code>": "", "</code>": "",
        "<pre>": "", "</pre>": "",
    }
    for a, b in replacements.items():
        s = s.replace(a, b)
    return s.strip()


def method_title(method: dict[str, Any], lang: str) -> str:
    return str(method.get(f"title_{lang}") or method.get("title_en") or method.get("code"))


def method_instructions(method: dict[str, Any], lang: str) -> str:
    return strip_visible_html_tags(str(method.get(f"instructions_{lang}") or method.get("instructions_en") or ""))


def looks_suspicious(text: str) -> bool:
    t = text.lower()
    has_url = "http://" in t or "https://" in t or "t.me/" in t
    risky_words = [
        "seed phrase", "mnemonic", "connect wallet", "airdrop", "verify wallet",
        "password", "login code", "2fa", "private key", "recovery phrase",
        "сид фраз", "сид-фраз", "пароль", "код вход", "приватный ключ",
        "сід фраз", "сід-фраз", "код входу", "приватний ключ",
    ]
    return has_url and any(w in t for w in risky_words)



def extract_message_attachment(msg: dict[str, Any]) -> dict[str, Any]:
    """Return lightweight proof/media metadata for messages sent to the bot."""
    if msg.get("photo"):
        photo = msg["photo"][-1]
        return {"kind": "photo", "file_id": photo.get("file_id"), "caption": msg.get("caption") or ""}
    for kind in ("video", "document", "animation", "audio", "voice", "video_note", "sticker"):
        if msg.get(kind):
            item = msg[kind]
            return {"kind": kind, "file_id": item.get("file_id"), "caption": msg.get("caption") or item.get("file_name") or ""}
    if msg.get("text"):
        return {"kind": "text", "file_id": None, "caption": msg.get("text") or ""}
    return {"kind": "unknown", "file_id": None, "caption": ""}


def proof_summary(proof: dict[str, Any] | None) -> str:
    if not proof:
        return "—"
    kind = proof.get("kind") or "unknown"
    cap = (proof.get("caption") or "").strip()
    if cap:
        return f"{kind}: {cap[:120]}"
    return str(kind)


SUPPORTED_EDIT_ENTITY_TYPES = {
    "bold", "italic", "underline", "strikethrough", "spoiler", "code", "pre",
    "text_link", "custom_emoji", "blockquote", "expandable_blockquote",
}

TEMPLATE_ALIASES = {
    "start": "start",
    "старт": "start",
    "connect": "connect",
    "підключити": "connect",
    "подключить": "connect",
    "business": "business_connected",
    "бізнес": "business_connected",
    "бизнес": "business_connected",
    "privacy": "privacy",
    "приватність": "privacy",
    "приватность": "privacy",

    # Dynamic screens. These are edited as protected templates with variables.
    "status": "status",
    "статус": "status",
    "plans": "plans",
    "tariffs": "plans",
    "тарифи": "plans",
    "тарифы": "plans",
    "subscription": "subscription",
    "підписка": "subscription",
    "подписка": "subscription",
    "keywords": "keywords",
    "ключові": "keywords",
    "ключевые": "keywords",
    "deleted": "deleted",
    "видалені": "deleted",
    "удаленные": "deleted",
    "удалённые": "deleted",
    "referrals": "referrals",
    "referral": "referrals",
    "реферали": "referrals",
    "рефералы": "referrals",
    "menu": "menu",
    "меню": "menu",
    "language": "choose_lang",
    "lang": "choose_lang",
    "мова": "choose_lang",
    "язык": "choose_lang",
    "choose_payment": "choose_payment",
    "payment": "choose_payment",
    "оплата": "choose_payment",
    "manual_payment": "payment_manual",
    "manual": "payment_manual",
    "ручна": "payment_manual",
    "ручная": "payment_manual",
    "keyword_prompt": "prompt_keyword_add",
    "keyword_add": "prompt_keyword_add",
    "prompt_keyword": "prompt_keyword_add",
    "кеворд": "prompt_keyword_add",
    "ключове": "prompt_keyword_add",
    "proof_prompt": "prompt_manual_payment_proof",
    "payment_proof": "prompt_manual_payment_proof",
    "proof": "prompt_manual_payment_proof",
    "квитанція": "prompt_manual_payment_proof",
    "квитанция": "prompt_manual_payment_proof",
    "support": "support",
    "donate": "support",
    "підтримка": "support",
    "поддержка": "support",
    "guide": "disappearing_guide",
    "disappearing": "disappearing_guide",
    "зникаючі": "disappearing_guide",
    "исчезающие": "disappearing_guide",
}

DYNAMIC_TEMPLATE_SPECS = {
    "status": {
        # Everything visible is editable text/emoji; only the {placeholders}
        # below are filled by the bot with live data.
        "vars": ["plan_name", "business_status", "saved_count", "deleted_count", "status_hint"],
        "labels": {
            "uk": {
                "plan_name": "статус підписки (активна до дати / відкритий доступ)",
                "business_status": "стан підключення (підключено / не підключено)",
                "saved_count": "скільки нових повідомлень збережено",
                "deleted_count": "скільки видалених знайдено",
                "status_hint": "підказка під статусом",
            },
            "ru": {
                "plan_name": "статус подписки (активна до даты / открытый доступ)",
                "business_status": "состояние подключения (подключено / не подключено)",
                "saved_count": "сколько новых сообщений сохранено",
                "deleted_count": "сколько удалённых найдено",
                "status_hint": "подсказка под статусом",
            },
            "en": {
                "plan_name": "subscription status (active until date / open access)",
                "business_status": "connection state (connected / not connected)",
                "saved_count": "how many new messages saved",
                "deleted_count": "how many deleted found",
                "status_hint": "hint shown under the status",
            },
        },
        "default": {
            "uk": "🛡 Статус захисту\n\n💎 Доступ: {plan_name}\n🔌 Автоматизація чатів: {business_status}\n💬 Збережено нових повідомлень: {saved_count}\n👻 Видалених знайдено: {deleted_count}\n\n{status_hint}",
            "ru": "🛡 Статус защиты\n\n💎 Доступ: {plan_name}\n🔌 Автоматизация чатов: {business_status}\n💬 Сохранено новых сообщений: {saved_count}\n👻 Удалённых найдено: {deleted_count}\n\n{status_hint}",
            "en": "🛡 Protection status\n\n💎 Access: {plan_name}\n🔌 Chat Automation: {business_status}\n💬 New messages saved: {saved_count}\n👻 Deleted found: {deleted_count}\n\n{status_hint}",
        },
    },
    "plans": {
        "vars": ["plans_list"],
        "labels": {
            "uk": {"plans_list": "твій поточний доступ (дата підписки або «немає підписки»)"},
            "ru": {"plans_list": "твой текущий доступ (дата подписки или «нет подписки»)"},
            "en": {"plans_list": "your current access (subscription date or “no subscription”)"},
        },
        "default": {
            "uk": "💎 Тарифи VERTUU SPY BOT\n\n{plans_list}",
            "ru": "💎 Тарифы VERTUU SPY BOT\n\n{plans_list}",
            "en": "💎 VERTUU SPY BOT plans\n\n{plans_list}",
        },
    },
    "keywords": {
        # The monitored-groups label and the /watch how-to used to be locked
        # inside the {keywords_hint} value; they are inlined here so they can be
        # fully edited. Only pure data stays in variables.
        "vars": ["keywords_count", "keywords_list", "monitored_groups"],
        "labels": {
            "uk": {"keywords_count": "скільки слів додано", "keywords_list": "список твоїх ключових слів", "monitored_groups": "групи на моніторингу"},
            "ru": {"keywords_count": "сколько слов добавлено", "keywords_list": "список твоих ключевых слов", "monitored_groups": "группы на мониторинге"},
            "en": {"keywords_count": "how many keywords", "keywords_list": "your keywords list", "monitored_groups": "monitored groups"},
        },
        "default": {
            "uk": "🔎 Сповіщення за ключовими словами\n\nСлів: {keywords_count}\n\n{keywords_list}\n\n📡 Групи на моніторингу:\n{monitored_groups}\n\nℹ️ Додай мене в групу (адміном) і надішли там /watch. Я напишу в особисті, коли зʼявляться твої слова. /unwatch — вимкнути.",
            "ru": "🔎 Оповещения по ключевым словам\n\nСлов: {keywords_count}\n\n{keywords_list}\n\n📡 Группы на мониторинге:\n{monitored_groups}\n\nℹ️ Добавь меня в группу (админом) и отправь там /watch. Я напишу в личку, когда встретятся твои слова. /unwatch — выключить.",
            "en": "🔎 Keyword alerts\n\nKeywords: {keywords_count}\n\n{keywords_list}\n\n📡 Monitored groups:\n{monitored_groups}\n\nℹ️ Add me to a group (as admin) and send /watch there. I'll DM you when your keywords appear. /unwatch to stop.",
        },
    },
    "deleted": {
        "vars": ["deleted_messages_list", "deleted_count"],
        "labels": {
            "uk": {"deleted_count": "скільки видалених знайдено", "deleted_messages_list": "список останніх видалених повідомлень"},
            "ru": {"deleted_count": "сколько удалённых найдено", "deleted_messages_list": "список последних удалённых сообщений"},
            "en": {"deleted_count": "how many deleted found", "deleted_messages_list": "list of recent deleted messages"},
        },
        "default": {
            "uk": "👁 Останні видалені\n\nЗнайдено: {deleted_count}\n\n{deleted_messages_list}",
            "ru": "👁 Последние удалённые\n\nНайдено: {deleted_count}\n\n{deleted_messages_list}",
            "en": "👁 Last deleted\n\nFound: {deleted_count}\n\n{deleted_messages_list}",
        },
    },
    "referrals": {
        "vars": ["referral_link", "normal_count", "premium_count", "bonus_days_total", "access_left", "normal_days", "normal_limit", "premium_days"],
        "labels": {
            "uk": {
                "referral_link": "твоє реферальне посилання", "normal_count": "к-сть звичайних рефералів",
                "premium_count": "к-сть Premium-рефералів", "bonus_days_total": "скільки днів зароблено",
                "access_left": "до якої дати доступ", "normal_days": "бонус-днів за звичайного реферала",
                "normal_limit": "ліміт звичайних рефералів", "premium_days": "бонус-днів за Premium-реферала",
            },
            "ru": {
                "referral_link": "твоя реферальная ссылка", "normal_count": "кол-во обычных рефералов",
                "premium_count": "кол-во Premium-рефералов", "bonus_days_total": "сколько дней заработано",
                "access_left": "до какой даты доступ", "normal_days": "бонус-дней за обычного реферала",
                "normal_limit": "лимит обычных рефералов", "premium_days": "бонус-дней за Premium-реферала",
            },
            "en": {
                "referral_link": "your referral link", "normal_count": "number of normal referrals",
                "premium_count": "number of Premium referrals", "bonus_days_total": "how many days earned",
                "access_left": "access valid until", "normal_days": "bonus days per normal referral",
                "normal_limit": "normal referral limit", "premium_days": "bonus days per Premium referral",
            },
        },
        "default": {
            "uk": "🤝 Реферальна система\n\nЗапрошуй друзів — отримуй дні Premium.\n• Звичайний реферал: +{normal_days} дн. (до {normal_limit} рефералів)\n• Premium-реферал: +{premium_days} дн.\n\n🔗 Твоє посилання:\n{referral_link}\n\n👥 Звичайних: {normal_count}\n💎 Premium: {premium_count}\n🎁 Зароблено днів: {bonus_days_total}\n⏳ Доступ до: {access_left}",
            "ru": "🤝 Реферальная система\n\nПриглашай друзей — получай дни Premium.\n• Обычный реферал: +{normal_days} дн. (до {normal_limit} рефералов)\n• Premium-реферал: +{premium_days} дн.\n\n🔗 Твоя ссылка:\n{referral_link}\n\n👥 Обычных: {normal_count}\n💎 Premium: {premium_count}\n🎁 Заработано дней: {bonus_days_total}\n⏳ Доступ до: {access_left}",
            "en": "🤝 Referral system\n\nInvite friends — earn Premium days.\n• Normal referral: +{normal_days}d (up to {normal_limit})\n• Premium referral: +{premium_days}d\n\n🔗 Your link:\n{referral_link}\n\n👥 Normal: {normal_count}\n💎 Premium: {premium_count}\n🎁 Days earned: {bonus_days_total}\n⏳ Access until: {access_left}",
        },
    },
    "choose_payment": {
        # The flag/label are inlined into the template so they can be edited
        # (e.g. swapped for a Premium emoji); only the numbers stay as variables.
        # The UAH line disappears automatically when there is no UAH amount.
        "vars": ["plan_name", "amount_usd", "amount_uah"],
        "labels": {
            "uk": {"plan_name": "назва тарифу", "amount_usd": "сума в доларах", "amount_uah": "сума в гривнях"},
            "ru": {"plan_name": "название тарифа", "amount_usd": "сумма в долларах", "amount_uah": "сумма в гривнах"},
            "en": {"plan_name": "plan name", "amount_usd": "amount in USD", "amount_uah": "amount in UAH"},
        },
        "default": {
            "uk": "💳 Оплата тарифу\n\nТариф: {plan_name}\nСума: ${amount_usd}\n🇺🇦 До сплати: {amount_uah} грн\n\nОбери спосіб оплати:",
            "ru": "💳 Оплата тарифа\n\nТариф: {plan_name}\nСумма: ${amount_usd}\n🇺🇦 К оплате: {amount_uah} грн\n\nВыбери способ оплаты:",
            "en": "💳 Plan payment\n\nPlan: {plan_name}\nAmount: ${amount_usd}\n🇺🇦 To pay: {amount_uah} UAH\n\nChoose payment method:",
        },
    },
    "payment_manual": {
        # Same idea: flags/labels live in the editable template, numbers stay in
        # variables. The UAH line is shown only for UAH card payments.
        "vars": ["plan_name", "amount_uah", "amount_usd", "instructions"],
        "labels": {
            "uk": {"plan_name": "назва тарифу", "amount_uah": "сума в гривнях", "amount_usd": "сума в доларах", "instructions": "реквізити/інструкція способу оплати"},
            "ru": {"plan_name": "название тарифа", "amount_uah": "сумма в гривнах", "amount_usd": "сумма в долларах", "instructions": "реквизиты/инструкция способа оплаты"},
            "en": {"plan_name": "plan name", "amount_uah": "amount in UAH", "amount_usd": "amount in USD", "instructions": "payment method details/instructions"},
        },
        "default": {
            "uk": "💳 Ручна оплата\n\n💎 Тариф: {plan_name}\n💰 Сума: ${amount_usd}\n🇺🇦 До сплати: {amount_uah} грн\n\n{instructions}\n\nПісля оплати: натисни «Я оплатив» і надішли скрін/квитанцію/файл/відео. Адмін перевірить оплату й активує доступ.",
            "ru": "💳 Ручная оплата\n\n💎 Тариф: {plan_name}\n💰 Сумма: ${amount_usd}\n🇺🇦 К оплате: {amount_uah} грн\n\n{instructions}\n\nПосле оплаты: нажми «Я оплатил» и отправь скрин/квитанцию/файл/видео. Админ проверит оплату и активирует доступ.",
            "en": "💳 Manual payment\n\n💎 Plan: {plan_name}\n💰 Amount: ${amount_usd}\n🇺🇦 To pay: {amount_uah} UAH\n\n{instructions}\n\nAfter payment: press “I paid” and send a screenshot/receipt/file/video. Admin will verify and activate access.",
        },
    },
}


# Human-readable descriptions for the {placeholders} of one-off (tr) messages,
# shown in the /edit legend. Sparse on purpose — any placeholder without a
# description is still listed, just without an explanation.
MESSAGE_LABELS: dict[str, dict[str, str]] = {
    "stars": {"uk": "кількість зірок", "ru": "количество звёзд", "en": "number of Stars"},
    "days": {"uk": "кількість днів", "ru": "количество дней", "en": "number of days"},
    "date": {"uk": "дата", "ru": "дата", "en": "date"},
    "amount": {"uk": "сума", "ru": "сумма", "en": "amount"},
    "url": {"uk": "посилання на оплату", "ru": "ссылка на оплату", "en": "payment link"},
    "app": {"uk": "назва бота", "ru": "название бота", "en": "bot name"},
    "bot_username": {"uk": "юзернейм бота", "ru": "юзернейм бота", "en": "bot username"},
    "plan": {"uk": "назва тарифу", "ru": "название тарифа", "en": "plan name"},
    "price": {"uk": "ціна", "ru": "цена", "en": "price"},
    "chat": {"uk": "назва чату", "ru": "название чата", "en": "chat name"},
    "author": {"uk": "автор повідомлення", "ru": "автор сообщения", "en": "message author"},
    "time": {"uk": "час", "ru": "время", "en": "time"},
    "saved": {"uk": "збережений вміст (текст або інфо про медіа)", "ru": "сохранённое содержимое (текст или инфо о медиа)", "en": "saved content (text or media info)"},
    "type": {"uk": "тип медіа", "ru": "тип медиа", "en": "media type"},
}


def message_legend(lang: str, variables: list[str]) -> str:
    """`{placeholder} — meaning` legend for a one-off message's placeholders."""
    lines: list[str] = []
    for var in dict.fromkeys(variables):  # de-dupe, keep order
        token = "{" + var + "}"
        desc = (MESSAGE_LABELS.get(var) or {}).get(lang) or (MESSAGE_LABELS.get(var) or {}).get("uk")
        lines.append(f"• <code>{e(token)}</code> — {e(desc)}" if desc else f"• <code>{e(token)}</code>")
    return "\n".join(lines)


def message_key_to_tr(template_key: str) -> str:
    """`msg_<trkey>_<lang>` -> `<trkey>`."""
    raw = str(template_key)
    if raw.startswith("msg_"):
        raw = raw[len("msg_"):]
    for suffix in ("_uk", "_ru", "_en"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
            break
    return raw


def template_base(key: str | None) -> str:
    if not key:
        return ""
    raw = str(key)
    for suffix in ("_uk", "_ru", "_en"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
            break
    # payment_manual can be method-specific, for example:
    # payment_manual_ua_card_uk / payment_manual_trc20_uk.
    if raw.startswith("payment_manual_"):
        return "payment_manual"
    return raw


def is_dynamic_template_key(key: str | None) -> bool:
    return template_base(key) in DYNAMIC_TEMPLATE_SPECS


def dynamic_template_default(base: str, lang: str) -> str:
    spec = DYNAMIC_TEMPLATE_SPECS.get(base) or {}
    default = spec.get("default") or {}
    return str(default.get(lang) or default.get("uk") or "")


def dynamic_required_vars(base: str) -> list[str]:
    spec = DYNAMIC_TEMPLATE_SPECS.get(base) or {}
    return list(spec.get("vars") or [])


def dynamic_var_labels(base: str, lang: str) -> dict[str, str]:
    """Human-readable description for each {placeholder} of a dynamic screen."""
    spec = DYNAMIC_TEMPLATE_SPECS.get(base) or {}
    labels = spec.get("labels") or {}
    return dict(labels.get(lang) or labels.get("uk") or {})


def dynamic_legend(base: str, lang: str, only: list[str] | None = None) -> str:
    """Build the `{placeholder} — what it means` legend shown during /edit.

    When ``only`` is given, list just those placeholders (so the legend matches
    exactly what is present in the text the admin is about to edit).
    """
    labels = dynamic_var_labels(base, lang)
    variables = only if only is not None else dynamic_required_vars(base)
    lines: list[str] = []
    for var in variables:
        token = "{" + var + "}"
        desc = labels.get(var)
        lines.append(f"• <code>{e(token)}</code> — {e(desc)}" if desc else f"• <code>{e(token)}</code>")
    return "\n".join(lines)


# Old saved templates may still bundle an emoji/label together with data inside a
# single variable (e.g. {amount_uah_line} = "🇺🇦 …: 11 грн"). For editing we show
# the decomposed form instead, so the emoji/label become editable and only the
# number stays as data. This only rewrites the PREVIEW; the saved template is
# untouched until the admin sends back new content.
DYNAMIC_VAR_MIGRATIONS: dict[str, dict[str, dict[str, str]]] = {
    "choose_payment": {
        "amount_uah_line": {
            "uk": "🇺🇦 До сплати: {amount_uah} грн",
            "ru": "🇺🇦 К оплате: {amount_uah} грн",
            "en": "🇺🇦 To pay: {amount_uah} UAH",
        },
    },
    "payment_manual": {
        "payment_amount_lines": {
            "uk": "🇺🇦 До сплати: {amount_uah} грн\n💵 До сплати: ${amount_usd}",
            "ru": "🇺🇦 К оплате: {amount_uah} грн\n💵 К оплате: ${amount_usd}",
            "en": "🇺🇦 To pay: {amount_uah} UAH\n💵 To pay: ${amount_usd}",
        },
        "amount_uah_line": {
            "uk": "🇺🇦 До сплати: {amount_uah} грн",
            "ru": "🇺🇦 К оплате: {amount_uah} грн",
            "en": "🇺🇦 To pay: {amount_uah} UAH",
        },
    },
    "keywords": {
        "keywords_hint": {
            "uk": "📡 Групи на моніторингу:\n{monitored_groups}\n\nℹ️ Додай мене в групу (адміном) і надішли там /watch. Я напишу в особисті, коли зʼявляться твої слова. /unwatch — вимкнути.",
            "ru": "📡 Группы на мониторинге:\n{monitored_groups}\n\nℹ️ Добавь меня в группу (админом) и отправь там /watch. Я напишу в личку, когда встретятся твои слова. /unwatch — выключить.",
            "en": "📡 Monitored groups:\n{monitored_groups}\n\nℹ️ Add me to a group (as admin) and send /watch there. I'll DM you when your keywords appear. /unwatch to stop.",
        },
    },
}


def migrate_dynamic_text(base: str, text: str, lang: str) -> str:
    """Rewrite old bundled placeholders into their editable decomposed form."""
    text = text or ""
    for old_var, langs in (DYNAMIC_VAR_MIGRATIONS.get(base) or {}).items():
        token = "{" + old_var + "}"
        if token in text:
            text = text.replace(token, langs.get(lang) or langs.get("uk") or "")
    return text


def present_dynamic_vars(base: str, text: str) -> list[str]:
    """Declared data placeholders that actually appear in this text."""
    return [v for v in dynamic_required_vars(base) if ("{" + v + "}") in (text or "")]


def missing_dynamic_vars(base: str, text: str) -> list[str]:
    return [v for v in dynamic_required_vars(base) if "{" + v + "}" not in (text or "")]


def html_to_plain(value: Any) -> str:
    """Turn an HTML-markup fragment into plain text.

    Saved templates are rendered through Telegram *entities* (not parse_mode
    HTML), so any leftover markup like ``<code>`` would otherwise be shown to
    the user literally. The dynamic values we inject (keyword lists, hints,
    deleted previews, …) are built with HTML tags for the default screens, so we
    strip the tags and unescape entities before substituting them into an
    entity-rendered template.
    """
    text = "" if value is None else str(value)
    if "<" not in text and "&" not in text:
        return text
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _drop_empty_optional_lines(
    source: str, entities: list[dict[str, Any]], values: dict[str, str]
) -> tuple[str, list[dict[str, Any]]]:
    """Remove template lines whose only data variables resolve to empty.

    This lets a default template inline a label/emoji on an optional line — e.g.
    ``🇺🇦 До сплати: {amount_uah} грн`` — and have the whole line disappear when
    there is no value. So the flag/emoji stays editable inside the template while
    the line itself is still conditional. Telegram entity offsets are kept valid:
    entities that overlap a removed line are dropped, the rest are shifted.
    """
    if not source or "{" not in source:
        return source, entities
    parts: list[str] = []
    removed: list[tuple[int, int]] = []  # (utf16_start, utf16_len) of removed text
    utf = 0
    lines = source.split("\n")
    last = len(lines) - 1
    for i, line in enumerate(lines):
        has_nl = i < last
        line_utf = utf16_len(line)
        tokens = [t for t in re.findall(r"\{([a-zA-Z0-9_]+)\}", line) if t in values]
        drop = bool(tokens) and all(not str(values.get(t) or "").strip() for t in tokens)
        if drop:
            if has_nl:
                removed.append((utf, line_utf + 1))  # line + trailing newline
            elif parts and parts[-1].endswith("\n"):
                # Last line: also remove the newline emitted by the previous line.
                removed.append((utf - 1, line_utf + 1))
                parts[-1] = parts[-1][:-1]
            else:
                removed.append((utf, line_utf))
        else:
            parts.append(line + ("\n" if has_nl else ""))
        utf += line_utf + (1 if has_nl else 0)
    if not removed:
        return source, entities
    new_source = "".join(parts)

    def removed_before(off: int) -> int:
        return sum(rl for rs, rl in removed if rs + rl <= off)

    def overlaps(off: int, length: int) -> bool:
        end = off + length
        return any(not (end <= rs or off >= rs + rl) for rs, rl in removed)

    new_entities: list[dict[str, Any]] = []
    for ent in entities:
        try:
            off = int(ent.get("offset", 0))
            length = int(ent.get("length", 0))
        except Exception:
            continue
        if overlaps(off, length):
            continue
        ne = dict(ent)
        ne["offset"] = off - removed_before(off)
        new_entities.append(ne)
    return new_source, new_entities


def render_dynamic_template(text: str, entities: list[dict[str, Any]] | None, values: dict[str, str]) -> tuple[str, list[dict[str, Any]]]:
    """Replace {variables} and keep Telegram entity offsets valid.

    Values are sanitized to plain text first: the surrounding template is sent
    with entities, so HTML tags inside the injected values must not survive or
    they appear as literal ``<code>`` to the user.
    """
    values = {k: html_to_plain(v) for k, v in (values or {}).items()}
    entities = [dict(x) for x in (entities or []) if isinstance(x, dict)]
    # Optional lines (their only variables are empty) are removed first, so an
    # inline emoji/label on such a line stays editable yet only shows when there
    # is data to display.
    source, entities = _drop_empty_optional_lines(text or "", entities, values)
    repls: list[tuple[int, int, int]] = []
    for m in re.finditer(r"\{([a-zA-Z0-9_]+)\}", source):
        name = m.group(1)
        if name not in values:
            continue
        old_token = m.group(0)
        new_val = str(values.get(name) or "")
        repls.append((utf16_len(source[:m.start()]), utf16_len(old_token), utf16_len(new_val)))

    rendered = source
    for name, value in values.items():
        rendered = rendered.replace("{" + name + "}", str(value or ""))

    if not repls:
        return rendered, entities

    adjusted: list[dict[str, Any]] = []
    for ent in entities:
        try:
            off = int(ent.get("offset", 0))
            length = int(ent.get("length", 0))
        except Exception:
            continue
        end = off + length
        shift = 0
        drop = False
        for start, old_len, new_len in repls:
            old_end = start + old_len
            if end <= start:
                continue
            if off >= old_end:
                shift += new_len - old_len
                continue
            drop = True
            break
        if drop:
            continue
        ent["offset"] = off + shift
        adjusted.append(ent)
    return rendered, adjusted


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def py_index_from_utf16(text: str, offset: int) -> int:
    if offset <= 0:
        return 0
    total = 0
    for idx, ch in enumerate(text):
        step = utf16_len(ch)
        if total + step > offset:
            return idx
        total += step
        if total == offset:
            return idx + 1
    return len(text)


def clean_entities_for_edit(entities: list[dict[str, Any]] | None, skip_utf16: int = 0) -> list[dict[str, Any]]:
    """Copy Telegram entities after optional UTF-16 prefix removal.

    This preserves Premium custom emoji (`custom_emoji_id`) and regular formatting.
    Telegram uses UTF-16 offsets, so we must not calculate offsets with len().
    """
    cleaned: list[dict[str, Any]] = []
    for ent in entities or []:
        ent_type = ent.get("type")
        if ent_type not in SUPPORTED_EDIT_ENTITY_TYPES:
            continue
        start = int(ent.get("offset") or 0)
        length = int(ent.get("length") or 0)
        if length <= 0:
            continue
        if start < skip_utf16:
            # Do not try to keep partially-overlapping entities; command entity lives here.
            continue
        item = dict(ent)
        item["offset"] = start - skip_utf16
        cleaned.append(item)
    return cleaned


def command_payload_from_message(msg: dict[str, Any]) -> tuple[str, list[dict[str, Any]], int]:
    """Return text/entities after `/edit` command and the skipped UTF-16 length.

    This is intentionally conservative: Telegram can send command entities in
    slightly different ways when the admin replies, quotes text, or uses
    /edit@BotName. We first strip the visible command with a regex, then fall
    back to Telegram entities. This prevents the literal `/edit` from being
    saved into the edited message.
    """
    text = msg.get("text") or ""
    entities = msg.get("entities") or []

    m = re.match(r"^/edit(?:@[A-Za-z0-9_]+)?(?=\s|$)", text)
    if m:
        idx = m.end()
    else:
        command_len_utf16 = None
        for ent in entities:
            if ent.get("type") == "bot_command" and int(ent.get("offset") or 0) == 0:
                command_len_utf16 = int(ent.get("length") or 0)
                break
        if command_len_utf16 is None:
            command_len_utf16 = utf16_len("/edit")
        idx = py_index_from_utf16(text, command_len_utf16)

    while idx < len(text) and text[idx] in {" ", "\n", "\t"}:
        idx += 1
    skip = utf16_len(text[:idx])
    return text[idx:], clean_entities_for_edit(entities, skip), skip


def parse_template_prefix(text: str, entities: list[dict[str, Any]], lang: str) -> tuple[str | None, str, list[dict[str, Any]]]:
    """Parse `/edit start` / `/edit connect` smart template mode.

    If the first word after /edit is a known template key, the edited text is
    also saved into DB and reused for future /start/callback messages.
    """
    stripped = text.lstrip()
    leading_py = len(text) - len(stripped)
    if not stripped:
        return None, text, entities
    first = stripped.split(maxsplit=1)[0].lower().strip()
    template = TEMPLATE_ALIASES.get(first)
    if not template:
        return None, text, entities
    start_idx = leading_py + len(stripped.split(maxsplit=1)[0])
    while start_idx < len(text) and text[start_idx] in {" ", "\n", "\t"}:
        start_idx += 1
    key = f"{template}_{lang}"
    return key, text[start_idx:], clean_entities_for_edit(entities, utf16_len(text[:start_idx]))

def strip_accidental_edit_prefix(text: str, entities: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """If admin sends `/edit ...` as the replacement text, strip it too."""
    m = re.match(r"^/edit(?:@[A-Za-z0-9_]+)?(?=\s|$)", text or "")
    if not m:
        return text, entities
    idx = m.end()
    while idx < len(text) and text[idx] in {" ", "\n", "\t"}:
        idx += 1
    skip = utf16_len(text[:idx])
    return text[idx:], clean_entities_for_edit(entities, skip)


def iter_callback_data(markup: dict[str, Any] | None) -> list[str]:
    result: list[str] = []
    if not isinstance(markup, dict):
        return result
    for row in markup.get("inline_keyboard") or []:
        if not isinstance(row, list):
            continue
        for btn_obj in row:
            if isinstance(btn_obj, dict) and btn_obj.get("callback_data"):
                result.append(str(btn_obj.get("callback_data")))
    return result


def first_callback_with_prefix(markup: dict[str, Any] | None, prefix: str) -> str | None:
    for data in iter_callback_data(markup):
        if data.startswith(prefix):
            return data
    return None


def detect_template_from_target(target: dict[str, Any] | None, lang: str) -> str | None:
    """Auto-detect which reusable template an edited bot message belongs to.

    Order matters: connect/privacy/business screens may also contain the brand name,
    so specific screens must be checked before the generic start screen.
    """
    if not target:
        return None
    text = str(target.get("text") or target.get("caption") or "")
    low = text.lower()
    callbacks = iter_callback_data(target.get("reply_markup"))

    # Callback buttons are the most reliable way to understand the screen.
    # This lets /edit work even when the message text was heavily customized
    # with Premium emoji and no longer contains the old keywords.
    if any(cb.startswith("manual_paid:") for cb in callbacks):
        return f"payment_manual_{lang}"
    if any(cb.startswith("pay:") for cb in callbacks):
        return f"choose_payment_{lang}"
    if any(cb.startswith("buy:") for cb in callbacks):
        return f"plans_{lang}"
    if any(cb.startswith("setlang:") for cb in callbacks):
        return f"choose_lang_{lang}"
    if any(cb in {"kw_add", "kw_delete_menu"} or cb.startswith("kw_del:") for cb in callbacks):
        return f"keywords_{lang}"
    if any(cb == "support_custom" or cb.startswith("support_amount:") for cb in callbacks):
        return f"support_{lang}"
    # The last-deleted screen carries these unique buttons, so it stays editable
    # even when its text is fully replaced with custom Premium-emoji content.
    if any(cb in {"toggle_own", "disappearing_guide"} for cb in callbacks):
        return f"deleted_{lang}"

    # Static/specific screens first. Privacy and connection instructions can
    # contain words like "Business-підключення", so they must not be mistaken
    # for the dynamic Status screen.
    if any(x in low for x in ["приватність", "приватность", "privacy", "forget_me", "видалити мої дані", "удалить мои данные", "видалення даних", "удаление данных", "не прошу код", "session string", "дані очищаються", "данные очищаются"]):
        return f"privacy_{lang}"
    if any(x in low for x in ["business-підключення активовано", "business-подключение актив", "business connection activated", "підключення активовано", "подключение активировано"]):
        return f"business_connected_{lang}"
    if any(x in low for x in ["як підключити", "как подключить", "how to connect", "chatbots", "чат-бот", "після підключення", "после подключения"]):
        return f"connect_{lang}"
    if any(x in low for x in ["головне меню", "главное меню", "main menu", "обери, що потрібно", "выбери, что нужно", "choose what you need"]):
        return f"menu_{lang}"
    if any(x in low for x in ["обери мову", "выбери язык", "choose language", "choose a language"]):
        return f"choose_lang_{lang}"
    if any(x in low for x in ["підтримати проект", "поддержать проект", "support the project", "підтримка проекту", "поддержка проекта"]):
        return f"support_{lang}"
    if any(x in low for x in ["зникаючі повідомлення", "исчезающие сообщения", "disappearing messages"]):
        return f"disappearing_guide_{lang}"

    # Dynamic screens. Detect them only by clear screen markers, not by generic
    # words like "Business", otherwise privacy/connect screens get misdetected.
    if any(x in low for x in ["статус захисту", "статус защиты", "protection status", "збережено нових", "сохранено новых", "new messages saved", "видалених знайдено", "удалённых найдено", "deleted found"]):
        return f"status_{lang}"
    # Payment screens must be detected before plans because they also contain
    # generic words like "Тариф" and plan names.
    if any(x in low for x in ["ручна оплата", "ручная оплата", "manual payment", "до сплати", "до оплаты", "сума в грн", "сумма в грн", "usdt trc20", "usdt bep20", "binance id", "картка:", "карта:", "отримувач:", "получатель:", "я оплатив", "i paid"]):
        return f"payment_manual_{lang}"
    if any(x in low for x in ["оплата тарифу", "оплата тарифа", "plan payment", "обери спосіб оплати", "выбери способ оплаты", "choose payment method"]):
        return f"choose_payment_{lang}"
    if any(x in low for x in ["тарифи vertuu", "тарифы vertuu", "vertuu spy bot plans", "обери тариф", "выбери тариф", "choose a plan", "choose plan", "free-режим", "free режим"]):
        return f"plans_{lang}"
    if any(x in low for x in ["ключовими словами", "ключевым словам", "keyword alerts", "keywords:", "слів:", "слов:"]):
        return f"keywords_{lang}"
    if any(x in low for x in ["останні видалені", "последние удал", "last deleted", "deleted found", "видалених повідомлень", "удалённых сообщений"]):
        return f"deleted_{lang}"
    if any(x in low for x in ["реферальна система", "реферальная система", "referral system", "referral_link", "твоя ссылка", "твоє посилання", "your link", "запрошуй друзів", "приглашай друзей"]):
        return f"referrals_{lang}"
    if any(x in low for x in ["надішли ключове слово", "отправь ключевое слово", "send the keyword", "ключове слово або фразу", "keyword or phrase"]):
        return f"prompt_keyword_add_{lang}"
    if any(x in low for x in ["надішли квитанцію", "отправь квитанцию", "send a receipt", "скрін/квитанцію", "receipt/screenshot"]):
        return f"prompt_manual_payment_proof_{lang}"
    if any(x in low for x in ["vertuu", "шпигун", "шпион", "spy bot", "що я вмію", "что я умею", "what i can", "особистий захист", "личный защит", "telegram-чат"]):
        return f"start_{lang}"
    return None


def message_text_and_entities(msg: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Read a normal admin message as rich Telegram text for /edit state mode."""
    if msg.get("text") is not None:
        return msg.get("text") or "", clean_entities_for_edit(msg.get("entities") or [], 0)
    if msg.get("caption") is not None:
        return msg.get("caption") or "", clean_entities_for_edit(msg.get("caption_entities") or [], 0)
    return "", []


def edit_content_from_message(msg: dict[str, Any]) -> tuple[str, list[dict[str, Any]], dict[str, Any] | None]:
    """Return replacement text/entities and optional media for the admin template editor.

    Supports: text-only, photo+caption, video+caption, animation+caption, document+caption and sticker-only.
    Premium custom emoji and rich formatting are preserved through Telegram entities.
    """
    text, entities = message_text_and_entities(msg)
    media = extract_message_attachment(msg)
    supported_media = {"photo", "video", "animation", "document", "sticker", "audio", "voice", "video_note"}
    if media.get("kind") not in supported_media or not media.get("file_id"):
        media_obj = None
    else:
        media_obj = {"kind": media.get("kind"), "file_id": media.get("file_id")}
        if media.get("kind") in {"sticker", "video_note"}:
            # Telegram stickers and video notes cannot carry a caption.
            text, entities = "", []
    return text, entities, media_obj


def target_edit_mode(target: dict[str, Any] | None) -> str:
    if not target:
        return "text"
    if target.get("text") is not None:
        return "text"
    return "caption"


def state_prompt(lang: str, state: str, payload: dict[str, Any]) -> str:
    if state == "support_stars_amount":
        return {
            "uk": "⭐ Надішли кількість зірок, яку хочеш відправити. Наприклад: <code>100</code>",
            "ru": "⭐ Отправь количество звёзд, которое хочешь отправить. Например: <code>100</code>",
            "en": "⭐ Send the number of Stars you want to send. Example: <code>100</code>",
        }.get(lang, "⭐ Send Stars amount")
    if state == "keyword_add":
        return {
            "uk": "🔎 Надішли ключове слово або фразу, яку треба відстежувати.",
            "ru": "🔎 Отправь ключевое слово или фразу, которую нужно отслеживать.",
            "en": "🔎 Send the keyword or phrase you want to track.",
        }.get(lang, "🔎 Send keyword")
    if state == "admin_grant":
        return "🎁 Надішли Telegram ID і кількість днів. Приклад: <code>123456789 30</code>"
    if state == "admin_revoke":
        return "🚫 Надішли Telegram ID користувача, у якого забрати доступ."
    if state == "admin_set_setting":
        return f"⚙️ Надішли нове значення для <code>{e(payload.get('key'))}</code>."
    if state == "admin_set_plan":
        return f"✏️ Надішли нове значення для тарифу #{e(payload.get('plan_id'))}, поле <code>{e(payload.get('field'))}</code>."
    if state == "admin_set_method":
        return f"✏️ Надішли нове значення для методу <code>{e(payload.get('code'))}</code>, поле <code>{e(payload.get('field'))}</code>."
    if state == "manual_payment_proof":
        return "📎 Надішли квитанцію/скрін/фото/відео/файл або текстовий коментар по оплаті. Після цього заявка піде адміну на перевірку."
    if state == "admin_upload_connect_video":
        return "🎬 Надішли відео-інструкцію файлом/відео в цей чат. Я збережу file_id і буду показувати її користувачам у розділі «Як підключити»."
    if state == "admin_upload_guide_video":
        return "👻 Надішли відео-інструкцію про зникаючі повідомлення (відео/файл/анімація/фото). Я збережу її і буду показувати користувачам у розділі «Останні видалені» → «Як дивитись зникаючі повідомлення»."
    if state == "admin_edit_message":
        template_key = payload.get("template_key")
        if template_key:
            return (
                f"✏️ Надішли новий контент для шаблону <code>{e(template_key)}</code>.\n"
                "Можна надіслати текст, фото з підписом, відео з підписом, GIF або файл. Я оновлю поточний екран і збережу його для майбутніх показів."
            )
        return "✏️ Надішли новий контент для повідомлення: текст або фото/відео/GIF/файл з підписом. Premium emoji, жирний, курсив, посилання та перенос рядків збережуться."
    if state == "admin_create_plan":
        return "➕ Надішли новий тариф у форматі:\n<code>code price days Назва тарифу</code>\n\nПриклад:\n<code>vip_week 0.99 7 VIP 7 днів</code>"
    if state == "admin_broadcast_template":
        return (
            "📝 <b>Шаблон розсилки</b>\n\n"
            "Перешли або надішли боту повідомлення, яке треба розсилати: текст, фото, відео, GIF, документ, аудіо, голос, відеоповідомлення, стікер або альбом.\n\n"
            "Бот скопіює його в чати в оригінальному вигляді. Для альбому перешли всі частини поспіль."
        )
    if state == "admin_broadcast_add":
        return (
            "➕ <b>Додати чат</b>\n\n"
            "Перешли боту будь-яке повідомлення з потрібної групи/каналу або надішли числовий chat_id.\n\n"
            "Важливо: бот має бути адміністратором у цьому чаті (з правом видаляти повідомлення)."
        )
    if state == "admin_broadcast_interval":
        return "⏱ Надішли інтервал розсилки у хвилинах. Приклад: <code>15</code>"
    if state == "admin_userbroadcast_template":
        return (
            "📨 <b>Розсилка в боті</b>\n\n"
            "Перешли або надішли боту повідомлення, яке треба розіслати всім користувачам бота: текст, фото, відео, GIF, документ, аудіо, голос, відеоповідомлення, стікер або альбом.\n\n"
            "Бот скопіює його кожному в особисті в оригінальному вигляді. Для альбому перешли всі частини поспіль."
        )
    if state == "admin_ref_bonus":
        return "✏️ Надішли <code>user_id днів</code>. Приклад: <code>123456789 5</code>"
    return "Надішли значення або натисни Скасувати."


class BotHandlers:
    def __init__(self, settings: Settings, db: Database, bot: BotAPI, crypto: CryptoPayClient):
        self.settings = settings
        self.db = db
        self.bot = bot
        self.crypto = crypto


    def debug_telegram_update(self, update: dict[str, Any]) -> None:
        """Safe debug snapshot for Railway logs.

        Does not print message text/captions, only update structure and media IDs presence.
        Useful for checking whether Telegram sends timer/self-destruct media to Business bots at all.
        """
        try:
            keys = sorted(list(update.keys()))
            payload: dict[str, Any] = {"update_id": update.get("update_id"), "keys": keys}

            msg = None
            msg_key = None
            for k in ("business_message", "edited_business_message", "message", "deleted_business_messages", "business_connection"):
                if k in update:
                    msg = update.get(k)
                    msg_key = k
                    break

            payload["kind"] = msg_key
            if isinstance(msg, dict):
                payload["message_keys"] = sorted(list(msg.keys()))
                payload["message_id"] = msg.get("message_id")
                payload["business_connection_id"] = msg.get("business_connection_id")
                chat = msg.get("chat") or {}
                if isinstance(chat, dict):
                    payload["chat_type"] = chat.get("type")
                    payload["chat_id"] = chat.get("id")
                if msg_key == "deleted_business_messages":
                    payload["deleted_message_ids"] = msg.get("message_ids")
                    payload["deleted_chat"] = (msg.get("chat") or {}).get("id") if isinstance(msg.get("chat"), dict) else None

                media_summary = {}
                for media_key in ("photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker", "location"):
                    if media_key in msg:
                        data = msg.get(media_key)
                        if media_key == "photo" and isinstance(data, list) and data:
                            media_summary[media_key] = {
                                "count": len(data),
                                "last_has_file_id": bool((data[-1] or {}).get("file_id")),
                                "last_file_size": (data[-1] or {}).get("file_size"),
                            }
                        elif isinstance(data, dict):
                            media_summary[media_key] = {
                                "has_file_id": bool(data.get("file_id")),
                                "file_size": data.get("file_size"),
                                "mime_type": data.get("mime_type"),
                                "keys": sorted(list(data.keys())),
                            }
                        else:
                            media_summary[media_key] = True
                payload["media"] = media_summary

                timer_keys = []
                def scan_timer(obj: Any, prefix: str = "") -> None:
                    if isinstance(obj, dict):
                        for kk, vv in obj.items():
                            low = str(kk).lower()
                            if any(x in low for x in ("ttl", "self_destruct", "self-destruct", "expire", "expires", "timer")):
                                timer_keys.append(prefix + str(kk))
                            scan_timer(vv, prefix + str(kk) + ".")
                    elif isinstance(obj, list):
                        for idx, item in enumerate(obj[:5]):
                            scan_timer(item, prefix + str(idx) + ".")
                scan_timer(msg)
                payload["timer_keys_found"] = timer_keys[:20]

            print("GHOSTLY_DEBUG_UPDATE", json.dumps(payload, ensure_ascii=False), flush=True)
        except Exception as exc:
            print("GHOSTLY_DEBUG_UPDATE_FAILED", repr(exc), flush=True)



    def debug_media_update(self, update: dict[str, Any]) -> None:
        """Safe media-only diagnostic log.

        Prints no message text/caption. Shows whether Telegram actually sends
        timer media to the bot as business_message/message and whether a file_id
        is present. This is the only reliable way to know why a timer media was
        not delivered.
        """
        try:
            payload: dict[str, Any] = {"update_id": update.get("update_id"), "keys": sorted(list(update.keys()))}
            msg_key = None
            msg = None
            for key in ("business_message", "edited_business_message", "message", "deleted_business_messages"):
                if key in update:
                    msg_key = key
                    msg = update.get(key)
                    break
            payload["kind"] = msg_key
            if isinstance(msg, dict):
                payload["message_id"] = msg.get("message_id")
                payload["business_connection_id"] = msg.get("business_connection_id")
                chat = msg.get("chat") or {}
                payload["chat_id"] = chat.get("id") if isinstance(chat, dict) else None
                payload["chat_type"] = chat.get("type") if isinstance(chat, dict) else None
                if msg_key == "deleted_business_messages":
                    payload["deleted_ids"] = msg.get("message_ids")
                media = {}
                for media_key in ("photo", "video", "video_note", "animation", "document", "audio", "voice", "sticker"):
                    if media_key not in msg:
                        continue
                    data = msg.get(media_key)
                    if media_key == "photo" and isinstance(data, list) and data:
                        media[media_key] = {
                            "count": len(data),
                            "has_file_id": bool((data[-1] or {}).get("file_id")),
                            "file_size": (data[-1] or {}).get("file_size"),
                        }
                    elif isinstance(data, dict):
                        media[media_key] = {
                            "has_file_id": bool(data.get("file_id")),
                            "file_size": data.get("file_size"),
                            "mime_type": data.get("mime_type"),
                            "keys": sorted(list(data.keys())),
                        }
                payload["media"] = media
                payload["has_caption"] = bool(msg.get("caption"))
                payload["has_media_group_id"] = bool(msg.get("media_group_id"))
                payload["timer_hint"] = self.raw_update_has_timer_hint(msg) if hasattr(self, "raw_update_has_timer_hint") else False
            print("GHOSTLY_MEDIA_DEBUG", json.dumps(payload, ensure_ascii=False), flush=True)
        except Exception as exc:
            print("GHOSTLY_MEDIA_DEBUG_FAILED", repr(exc), flush=True)


    async def handle_update(self, update: dict[str, Any]) -> None:
        if os.getenv("GHOSTLY_MEDIA_DEBUG", "true").lower() in {"1", "true", "yes", "on"}:
            self.debug_media_update(update)
        if os.getenv("GHOSTLY_DEBUG_UPDATES", "false").lower() in {"1", "true", "yes", "on"}:
            self.debug_telegram_update(update)
        try:
            if "message" in update:
                await self.handle_message(update["message"])
            elif "callback_query" in update:
                await self.handle_callback(update["callback_query"])
            elif "pre_checkout_query" in update:
                await self.handle_pre_checkout_query(update["pre_checkout_query"])
            elif "business_connection" in update:
                await self.handle_business_connection(update["business_connection"])
            elif "business_message" in update:
                await self.handle_business_message(update["business_message"])
            elif "edited_business_message" in update:
                await self.handle_edited_business_message(update["edited_business_message"])
            elif "deleted_business_messages" in update:
                await self.handle_deleted_business_messages(update["deleted_business_messages"])
            elif "my_chat_member" in update:
                await self.handle_my_chat_member(update["my_chat_member"])
        except Exception as exc:
            print("Update handling error:", repr(exc), json.dumps(update, ensure_ascii=False)[:2000])

    async def user_lang(self, tg_id: int) -> str:
        user = await self.db.get_user(tg_id)
        return str(user.get("lang") if user else self.settings.default_lang)


    def message_has_media(self, msg: dict[str, Any]) -> bool:
        return any(msg.get(k) for k in ("photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker"))

    async def handle_direct_media_backup_message(self, tg_id: int, lang: str, msg: dict[str, Any], is_admin: bool = False) -> bool:
        """Backup media sent to the bot directly.

        In Railway logs, some timer tests arrive as a normal `message` update,
        not as `business_message`. The old code ignored such media and only
        showed the menu. This handler saves/sends direct media immediately too.
        """
        if not self.message_has_media(msg):
            return False

        if not is_admin and not await self.db.active_subscription(tg_id):
            await self.safe_send(
                tg_id,
                "🔒 <b>Медіа-бекап доступний у Pro.</b>\n\nПідключи Pro або Telegram Business, щоб VERTUU SPY BOT зберігав медіа автоматично."
                if lang == "uk"
                else "🔒 <b>Медиа-бэкап доступен в Pro.</b>\n\nПодключи Pro или Telegram Business, чтобы VERTUU SPY BOT сохранял медиа автоматически."
                if lang == "ru"
                else "🔒 <b>Media backup is available in Pro.</b>\n\nEnable Pro or Telegram Business so VERTUU SPY BOT can save media automatically.",
                plans_keyboard(lang, await self.db.plans(True)),
            )
            return True

        kind, _text, caption, file_id = extract_message_content(msg)
        file_name, declared_size, mime_type, is_disappearing = extract_file_metadata(msg)
        if not file_id:
            print("Direct media backup skipped: no file_id", {"kind": kind, "message_id": msg.get("message_id"), "keys": sorted(list(msg.keys()))}, flush=True)
            await self.safe_send(
                tg_id,
                "⚠️ Telegram не передав file_id для цього медіа, тому я не зміг його зберегти."
                if lang == "uk"
                else "⚠️ Telegram не передал file_id для этого медиа, поэтому я не смог его сохранить."
                if lang == "ru"
                else "⚠️ Telegram did not provide file_id for this media, so I could not save it.",
            )
            return True

        max_bytes = self.media_cache_max_bytes()
        try:
            info = await self.bot.get_file(str(file_id))
            size = info.get("file_size") or declared_size
            if size and int(size) > max_bytes:
                await self.safe_send(
                    tg_id,
                    f"⚠️ Файл занадто великий для бекапу: {int(size)} bytes."
                    if lang == "uk"
                    else f"⚠️ Файл слишком большой для бэкапа: {int(size)} bytes."
                    if lang == "ru"
                    else f"⚠️ File is too large for backup: {int(size)} bytes.",
                )
                return True
            file_path = str(info.get("file_path") or "")
            if not file_path:
                raise RuntimeError("Telegram returned empty file_path")
            content = await self.bot.download_file(file_path, max_bytes=max_bytes)

            fake_cached = {
                "id": 0,
                "content_type": kind,
                "file_id": file_id,
                "file_bytes": content,
                "file_name": file_name or f"vertuu_direct_{kind}.bin",
                "file_size": len(content),
                "mime_type": mime_type,
                "caption": caption,
                "chat_title": "Direct bot chat",
                "chat_id": tg_id,
                "sender_name": (msg.get("from") or {}).get("first_name") or tg_id,
                "sender_id": tg_id,
                "message_id": msg.get("message_id"),
            }

            title = (
                "🔥 <b>Медіа одразу збережено</b>"
                if lang == "uk"
                else "🔥 <b>Медиа сразу сохранено</b>"
                if lang == "ru"
                else "🔥 <b>Media saved instantly</b>"
            )
            note = (
                "Я отримав це як звичайне повідомлення в боті, тому одразу зробив копію."
                if lang == "uk"
                else "Я получил это как обычное сообщение в боте, поэтому сразу сделал копию."
                if lang == "ru"
                else "I received this as a direct bot message, so I backed it up immediately."
            )
            await self.safe_send(
                tg_id,
                f"{title}\n\n📎 <b>Тип:</b> {e(media_kind_label(kind, lang))}\n"
                f"💾 <b>Розмір:</b> {len(content)} bytes\n\n{e(note)}"
            )
            delivered = await self.send_deleted_media_copy(tg_id, lang, kind, str(file_id), caption, fake_cached)
            print("Direct media backup result", {"kind": kind, "bytes": len(content), "delivered": delivered, "timer_hint": bool(is_disappearing)}, flush=True)
            return True
        except Exception as exc:
            print("Direct media backup failed:", repr(exc), {"kind": kind, "message_id": msg.get("message_id")}, flush=True)
            await self.safe_send(
                tg_id,
                "⚠️ Не вийшло зберегти це медіа. Я записав помилку в Railway logs."
                if lang == "uk"
                else "⚠️ Не получилось сохранить это медиа. Я записал ошибку в Railway logs."
                if lang == "ru"
                else "⚠️ Could not save this media. I logged the error in Railway logs.",
            )
            return True



    async def handle_direct_timer_media_message(self, tg_id: int, lang: str, msg: dict[str, Any], is_admin: bool = False) -> bool:
        """Handle timer-like media if Telegram sends it as a normal message update.

        This does not process voice/audio/documents/stickers and uses the same
        timer-only detector as Business messages.
        """
        if os.getenv("DIRECT_TIMER_MEDIA_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
            return False
        if not self.message_has_media(msg):
            return False

        kind, _text, caption, file_id = extract_message_content(msg)
        if kind not in {"photo", "video", "video_note"}:
            return False
        if caption or msg.get("media_group_id"):
            return False

        fake_cached = {
            "id": 0,
            "owner_tg_id": tg_id,
            "business_connection_id": "direct",
            "chat_id": tg_id,
            "message_id": int(msg.get("message_id") or 0),
            "content_type": kind,
            "file_id": file_id,
            "caption": caption,
            "chat_title": "Direct bot chat",
            "sender_name": (msg.get("from") or {}).get("first_name") or tg_id,
            "sender_id": tg_id,
            "is_disappearing": self.raw_update_has_timer_hint(msg),
            "media_backup_sent_at": None,
        }
        if not await self.is_timer_media_candidate(fake_cached, msg):
            return False
        if not file_id:
            print("Direct timer media skipped: no file_id", {"kind": kind, "message_id": msg.get("message_id")}, flush=True)
            return True

        try:
            file_name, declared_size, mime_type, _is_disappearing = extract_file_metadata(msg)
            info = await self.bot.get_file(str(file_id))
            file_path = str(info.get("file_path") or "")
            if not file_path:
                raise RuntimeError("Telegram returned empty file_path")
            content = await self.bot.download_file(file_path, max_bytes=self.media_cache_max_bytes())
            fake_cached.update({
                "file_bytes": content,
                "file_name": file_name or f"vertuu_timer_{kind}.bin",
                "file_size": len(content),
                "mime_type": mime_type,
            })
            if lang == "ru":
                title = "🔥 <b>Таймерное медиа сохранено</b>"
            elif lang == "en":
                title = "🔥 <b>Timer media saved</b>"
            else:
                title = "🔥 <b>Таймерове медіа збережено</b>"
            await self.safe_send(tg_id, f"{title}\n\n📎 <b>{'Тип' if lang != 'en' else 'Type'}:</b> {e(media_kind_label(kind, lang))}")
            delivered = await self.send_deleted_media_copy(tg_id, lang, kind, str(file_id), caption, fake_cached)
            print("Direct timer media delivery result", {"kind": kind, "bytes": len(content), "delivered": delivered}, flush=True)
            return True
        except Exception as exc:
            print("Direct timer media failed:", repr(exc), {"kind": kind, "message_id": msg.get("message_id")}, flush=True)
            return True


    async def handle_message(self, msg: dict[str, Any]) -> None:
        chat = msg.get("chat") or {}
        # The bot's private UI only makes sense in 1:1 chats. Group/supergroup
        # messages go to the keyword-monitoring path instead of the menu UI.
        if chat.get("type") and chat.get("type") != "private":
            await self.handle_group_message(msg)
            return
        user_obj = msg.get("from") or {}
        user = await self.db.upsert_user(user_obj)
        if not user:
            return
        tg_id = int(user["tg_id"])
        lang = str(user.get("lang") or self.settings.default_lang)

        if msg.get("successful_payment"):
            await self.handle_stars_successful_payment(tg_id, lang, msg)
            return

        text = (msg.get("text") or "").strip()
        is_admin = await self.db.is_admin(tg_id)

        state = await self.db.get_state(tg_id)
        if state:
            state_name = str(state.get("state") or "")
            if text in {"/start", "/cancel"}:
                await self.db.clear_state(tg_id)
                await self.show_start(tg_id, lang, is_admin)
                return
            if state_name == "manual_payment_proof" and not text.startswith("/"):
                await self.handle_payment_proof_message(tg_id, lang, msg, state, is_admin)
                return
            if state_name == "admin_upload_connect_video" and is_admin and not text.startswith("/"):
                await self.handle_admin_upload_connect_video(tg_id, lang, msg, state)
                return
            if state_name == "admin_upload_guide_video" and is_admin and not text.startswith("/"):
                await self.handle_admin_upload_guide_video(tg_id, lang, msg, state)
                return
            if state_name == "admin_broadcast_template" and is_admin and not text.startswith("/"):
                await self.handle_broadcast_template_message(tg_id, lang, msg, state)
                return
            if state_name == "admin_userbroadcast_template" and is_admin and not text.startswith("/"):
                await self.handle_user_broadcast_template_message(tg_id, lang, msg, state)
                return
            if state_name == "admin_broadcast_add" and is_admin and not text.startswith("/"):
                # Forwarded message from the target chat (may carry no text).
                if msg.get("forward_from_chat") or (msg.get("forward_origin") or {}).get("chat"):
                    await self.handle_broadcast_add_message(tg_id, lang, msg, state)
                    return
            if state_name == "admin_edit_message" and is_admin:
                # A fresh "/edit" reply to another bot message starts a NEW edit
                # of THAT message instead of being swallowed as replacement
                # content for the previous one. (Plain replacement text may still
                # accidentally start with /edit — that is handled in
                # handle_admin_edit_content via strip_accidental_edit_prefix.)
                if msg.get("reply_to_message") and re.match(r"^/edit(?:@\w+)?(?:\s|$)", text):
                    await self.db.clear_state(tg_id)
                    # fall through to the /edit command dispatch below
                else:
                    await self.handle_admin_edit_content(tg_id, lang, msg, state)
                    return
            if not text.startswith("/"):
                if text:
                    await self.handle_state_input(tg_id, lang, text, state, is_admin)
                    return
                await self.bot.send_message(tg_id, state_prompt(lang, state_name, state.get("payload") or {}), cancel_keyboard(lang, "admin" if is_admin else "menu"))
                return
            await self.db.clear_state(tg_id)

        if await self.handle_direct_timer_media_message(tg_id, lang, msg, is_admin):
            return

        if self.message_has_media(msg) and os.getenv("DIRECT_MEDIA_BACKUP_ENABLED", "false").lower() in {"1", "true", "yes", "on"}:
            if await self.handle_direct_media_backup_message(tg_id, lang, msg, is_admin):
                return

        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            if len(parts) > 1 and parts[1].startswith("ref_"):
                try:
                    referrer_id = int(parts[1].split("_", 1)[1])
                    referred_is_premium = bool(user_obj.get("is_premium"))
                    result = await self.db.process_referral(tg_id, referrer_id, referred_is_premium)
                    if result:
                        await self.notify_referral_result(referrer_id, result)
                except Exception as exc:
                    print("Referral processing error:", repr(exc), flush=True)
            await self.show_start(tg_id, lang, is_admin)
        elif text in {"/language", "/lang"}:
            await self.show_language_screen(tg_id, lang)
        elif text in {"/status"}:
            await self.show_status(tg_id, lang)
        elif text in {"/plans"}:
            await self.show_plans(tg_id, lang)
        elif text in {"/support", "/donate"}:
            await self.show_support(tg_id, lang)
        elif text == "/keywords":
            await self.show_keywords(tg_id, lang)
        elif text.startswith("/add_keyword "):
            kw = text.split(maxsplit=1)[1].strip()
            await self.db.add_keyword(tg_id, kw)
            await self.bot.send_message(tg_id, f"✅ Keyword added: <code>{e(kw[:80])}</code>")
            await self.show_keywords(tg_id, lang)
        elif text.startswith("/del_keyword "):
            kw = text.split(maxsplit=1)[1].strip()
            await self.db.delete_keyword(tg_id, kw)
            await self.bot.send_message(tg_id, f"✅ Keyword removed: <code>{e(kw[:80])}</code>")
            await self.show_keywords(tg_id, lang)
        elif text == "/last_deleted":
            await self.show_last_deleted(tg_id, lang)
        elif text in {"/admin"}:
            await self.show_admin(tg_id, lang)
        elif text == "/forget_me":
            await self.db.forget_user(tg_id)
            await self.bot.send_message(tg_id, tr(lang, "forgotten"), main_menu(lang, is_admin))
        elif text.startswith("/edit") and is_admin:
            await self.handle_edit_command(tg_id, lang, msg)
        elif text.startswith("/") and is_admin:
            await self.handle_admin_command(tg_id, text, lang)
        elif text.startswith("/"):
            await self.bot.send_message(tg_id, tr(lang, "unknown_command"), main_menu(lang, is_admin))
        else:
            await self.show_menu_screen(tg_id, lang, is_admin)

    async def resolve_edit_template_key(self, target: dict[str, Any], lang: str, chat_id: int | None = None) -> str | None:
        # 1. Deterministic resolution: did this bot send this exact message as a
        # known template? This is reliable even when the screen text was heavily
        # customized with Premium emoji, and it fixes editing the wrong screen.
        message_id = target.get("message_id")
        if chat_id is not None and message_id:
            recorded = await self.db.get_sent_template_key(chat_id, int(message_id))
            if recorded:
                return recorded

        # 2. Fallback: heuristic detection for old messages sent before tracking
        # existed, or messages the bot never recorded.
        key = detect_template_from_target(target, lang)

        # Manual payment screens must be editable per payment method.
        # Otherwise editing TON would accidentally change card/TRC20/BEP20 too.
        if key == f"payment_manual_{lang}":
            cb = first_callback_with_prefix(target.get("reply_markup"), "manual_paid:")
            if cb:
                try:
                    payment_id = int(cb.split(":", 1)[1])
                    payment = await self.db.get_payment(payment_id)
                    provider = str((payment or {}).get("provider") or "").strip()
                    if provider and provider != "cryptobot":
                        return f"payment_manual_{provider}_{lang}"
                except Exception:
                    pass
        return key


    async def handle_edit_command(self, tg_id: int, lang: str, msg: dict[str, Any]) -> None:
        if not await self.db.is_admin(tg_id):
            await self.bot.send_message(tg_id, tr(lang, "not_admin"))
            return

        target = msg.get("reply_to_message")
        if not target or not target.get("message_id"):
            await self.bot.send_message(
                tg_id,
                "✏️ <b>/edit</b> працює тільки відповіддю на повідомлення бота.\n\n"
                "Як користуватись:\n"
                "1. Відповідай на потрібне повідомлення командою <code>/edit</code>.\n"
                "2. Потім надішли новий текст або фото/відео/GIF/файл з підписом.\n\n"
                "Швидкий варіант для тексту: <code>/edit Новий текст</code>\n"
                "Я сам визначу шаблон: start / connect / privacy / business / payment / referrals.",
            )
            return

        target_from = target.get("from") or {}
        if target_from and target_from.get("is_bot") is False:
            await self.bot.send_message(tg_id, "⚠️ Я можу редагувати тільки повідомлення, які надіслав цей бот.")
            return

        target_chat_id = int((msg.get("chat") or {}).get("id", tg_id))
        new_text, entities, _ = command_payload_from_message(msg)
        template_key, new_text, entities = parse_template_prefix(new_text, entities, lang)
        auto_template_key = await self.resolve_edit_template_key(target, lang, chat_id=target_chat_id)
        if not template_key:
            template_key = auto_template_key
        payload = {
            "target_chat_id": target_chat_id,
            "target_message_id": int(target["message_id"]),
            "mode": target_edit_mode(target),
            "reply_markup": target.get("reply_markup"),
            "template_key": template_key,
            "auto_template_key": auto_template_key,
        }

        if not new_text.strip():
            await self.db.set_state(tg_id, "admin_edit_message", payload)
            editable = ""
            if template_key:
                extra = f"\n\n🧩 <b>Я визначив цей екран як шаблон:</b> <code>{e(template_key)}</code>. Новий контент збережу назавжди."
                current_tpl = await self.db.get_template(template_key)
                editable = str((current_tpl or {}).get("text") or target.get("text") or target.get("caption") or "")
                if not editable and str(template_key).startswith("prompt_keyword_add_"):
                    editable = state_prompt(lang, "keyword_add", {})
                if not editable and str(template_key).startswith("prompt_manual_payment_proof_"):
                    editable = state_prompt(lang, "manual_payment_proof", {})
                if str(template_key).startswith("msg_"):
                    trkey = message_key_to_tr(template_key)
                    raw = str((current_tpl or {}).get("text") or strip_visible_html_tags(tr_template(lang, trkey)))
                    editable = raw
                    msg_vars = re.findall(r"\{(\w+)\}", raw)
                    extra += (
                        "\n\n🎨 <b>Редагуй будь-який текст і емодзі</b> (зокрема Premium emoji) — як хочеш."
                    )
                    if msg_vars:
                        extra += (
                            "\n\n📊 <b>Змінні в {дужках} — бот підставляє сам.</b> Лиши їх, де треба авто-дані:\n"
                            f"{message_legend(lang, msg_vars)}"
                        )
                    else:
                        extra += "\n\nℹ️ У цьому повідомленні немає змінних — можеш переписати його повністю."
                elif is_dynamic_template_key(template_key):
                    base = template_base(template_key)
                    raw = str((current_tpl or {}).get("text") or dynamic_template_default(base, lang))
                    # Show old saved templates in the modern decomposed form so the
                    # emoji/labels that used to be locked in a value become editable.
                    editable = migrate_dynamic_text(base, raw, lang)
                    # If the admin previously baked a live value into the saved
                    # text (e.g. copied the rendered access date / TON address),
                    # turn it back into its {placeholder} so it auto-updates again.
                    for var, val in (await self.live_values_for_edit(base, lang, tg_id, target)).items():
                        val = str(val or "")
                        token = "{" + var + "}"
                        if len(val) >= 6 and val in editable and token not in editable:
                            editable = editable.replace(val, token)
                    legend = dynamic_legend(base, lang)
                    extra += (
                        "\n\n🎨 <b>Редагуй будь-який текст і емодзі</b> (зокрема Premium emoji) — як хочеш."
                    )
                    if legend:
                        extra += (
                            "\n\n📊 <b>Змінні в {дужках} — бот підставляє сам.</b> Не чіпай ті, що вже є; "
                            "а будь-яку з цих можеш вставити туди, де хочеш авто-дані (напр. дату, суму, лічильник):\n"
                            f"{legend}"
                        )
            else:
                extra = "\n\nℹ️ Це буде разове редагування конкретного повідомлення."
                # Show the current text too, so a one-off message is just as easy
                # to tweak to perfection as a saved template.
                editable = str(target.get("text") or target.get("caption") or "")
            # The prompt itself is always short, so it never hits the message
            # limit. The current text is sent separately (and chunked) below so
            # the admin always sees ALL of it, even for very long screens.
            await self.bot.send_message(
                tg_id,
                f"✏️ <b>Режим редагування увімкнено.</b> <code>build: {e(BUILD)}</code>\n\n"
                "Тепер надішли <b>новий контент</b> одним повідомленням — без /edit на початку.\n"
                "Це може бути текст або фото/відео/GIF/файл з підписом. Premium emoji, жирний/курсивний текст, посилання і перенос рядків збережуться."
                f"{extra}\n\n"
                "Скасувати: /start",
            )
            await self.send_current_text_for_copy(
                tg_id, editable,
                title="📋 Копіюй, редагуй і надсилай назад. Усе можна міняти, окрім того, що у {дужках}:",
            )
            # For reference, also show the screen exactly as it looks right now
            # with every {placeholder} filled in, so it is clear what the brackets
            # become. (Editing this version and sending it back would freeze the
            # data — the template above is the one to edit.)
            onscreen = str(target.get("text") or target.get("caption") or "")
            if onscreen.strip() and onscreen.strip() != (editable or "").strip():
                await self.send_current_text_for_copy(
                    tg_id, onscreen,
                    title="🔎 Для довідки — так екран виглядає зараз, із підставленими даними:",
                )
            return

        await self.perform_admin_edit(tg_id, lang, payload, new_text, entities)

    async def send_current_text_for_copy(self, tg_id: int, editable: str, title: str | None = None) -> None:
        """Send the FULL current text as copyable <pre> blocks.

        Long screens exceed Telegram's per-message limit, so the text is split
        into as many chunks as needed. This guarantees the admin always sees the
        whole editable text — not a cut-off preview — and can copy it to tweak.
        """
        editable = editable or ""
        if not editable.strip():
            return
        base_title = title or "📋 Поточний текст — копіюй і редагуй:"
        chunks = split_escaped_for_pre(editable)
        total = len(chunks)
        for idx, chunk in enumerate(chunks, 1):
            header = (
                f"<b>{e(base_title)}</b> ({idx}/{total})\n"
                if total > 1
                else f"<b>{e(base_title)}</b>\n"
            )
            try:
                await self.bot.send_message(tg_id, f"{header}<pre>{e(chunk)}</pre>")
            except Exception as exc:
                print("send_current_text_for_copy chunk failed:", repr(exc), flush=True)

    async def handle_admin_edit_content(self, tg_id: int, lang: str, msg: dict[str, Any], state_row: dict[str, Any]) -> None:
        payload = state_row.get("payload") or {}
        text, entities, media = edit_content_from_message(msg)
        text, entities = strip_accidental_edit_prefix(text, entities)
        if not text.strip() and not media:
            await self.bot.send_message(tg_id, state_prompt(lang, "admin_edit_message", payload), cancel_keyboard(lang, "admin"))
            return
        await self.perform_admin_edit(tg_id, lang, payload, text, entities, media)

    async def perform_admin_edit(
        self,
        tg_id: int,
        lang: str,
        payload: dict[str, Any],
        text: str,
        entities: list[dict[str, Any]] | None,
        media: dict[str, Any] | None = None,
    ) -> None:
        target_chat_id = int(payload.get("target_chat_id") or tg_id)
        target_message_id = int(payload.get("target_message_id") or 0)
        mode = str(payload.get("mode") or "text")
        reply_markup = payload.get("reply_markup")
        template_key = payload.get("template_key")
        if not target_message_id and not template_key:
            await self.db.clear_state(tg_id)
            await self.bot.send_message(tg_id, "❌ Не знайшов повідомлення для редагування. Спробуй ще раз: reply → /edit")
            return

        # Dynamic screens can now be edited visually too. If the admin keeps
        # variables like {plan_name}, they remain live. If he removes them, the
        # screen becomes a static custom design. This is intentional: the admin
        # asked for simple reply -> /edit -> send new Premium emoji text without
        # needing the separate admin panel.

        try:
            # If admin sends media, Telegram cannot reliably convert an existing text
            # message into a media message. We replace the visible screen cleanly:
            # delete old bot message and send a new media/text screen with the same buttons.
            if media:
                if target_message_id:
                    try:
                        await self.bot.delete_message(target_chat_id, target_message_id)
                    except Exception:
                        pass
                await self.send_template_content(tg_id, text, entities or [], media, reply_markup, track_key=str(template_key) if template_key else None)
            else:
                if mode == "caption" and template_key:
                    # Admin is turning a media screen back into a text-only template.
                    # Delete the old media message and send a clean text message with buttons.
                    try:
                        await self.bot.delete_message(target_chat_id, target_message_id)
                    except Exception:
                        pass
                    await self.send_template_content(tg_id, text, entities or [], None, reply_markup, track_key=str(template_key))
                elif mode == "caption":
                    await self.bot.edit_message_caption(target_chat_id, target_message_id, text, reply_markup=reply_markup, caption_entities=entities or [])
                    if template_key:
                        await self.db.record_sent_template(target_chat_id, target_message_id, str(template_key))
                else:
                    await self.bot.edit_message_text(target_chat_id, target_message_id, text, reply_markup=reply_markup, entities=entities or [])
                    if template_key:
                        await self.db.record_sent_template(target_chat_id, target_message_id, str(template_key))

            if template_key:
                await self.db.set_template(str(template_key), text, entities or [], media)
            await self.db.clear_state(tg_id)
            media_line = "\n📎 <b>Медіа збережено разом із шаблоном.</b>" if media else ""
            saved_line = (
                f"\n\n🧩 <b>Шаблон збережено:</b> <code>{e(template_key)}</code>. Тепер /start або відповідний розділ буде показувати саме цей контент."
                if template_key else "\n\nℹ️ Це було разове редагування. Для постійного збереження відповідай на екран /start або пиши <code>/edit start</code>."
            )
            await self.bot.send_message(
                tg_id,
                "✅ <b>Повідомлення оновлено.</b>"
                f"{saved_line}{media_line}\n\n"
                "Premium emoji, форматування, фото/відео збережені, якщо Telegram дозволив їх використати для цього бота.",
            )
        except Exception as exc:
            await self.db.clear_state(tg_id)
            await self.bot.send_message(
                tg_id,
                "❌ <b>Не вдалося відредагувати повідомлення.</b>\n\n"
                "Можливі причини:\n"
                "• це повідомлення надіслав не цей бот;\n"
                "• воно занадто старе або Telegram не дозволяє його редагувати;\n"
                "• текст/emoji має некоректне форматування;\n"
                "• caption під медіа довший за ліміт Telegram, тоді я спробую відправити медіа + текст окремо;\n"
                "• ти відповів не на те повідомлення.\n\n"
                f"Технічна помилка:\n<code>{e(repr(exc))}</code>",
            )

    async def handle_state_input(self, tg_id: int, lang: str, text: str, state_row: dict[str, Any], is_admin: bool) -> None:
        state = state_row.get("state")
        payload = state_row.get("payload") or {}
        try:
            if state == "keyword_add":
                await self.db.add_keyword(tg_id, text)
                await self.db.clear_state(tg_id)
                done = "✅ Ключове слово додано." if lang == "uk" else "✅ Ключевое слово добавлено." if lang == "ru" else "✅ Keyword added."
                await self.bot.send_message(tg_id, done)
                await self.show_keywords(tg_id, lang)
                return

            if state == "support_stars_amount":
                cleaned = text.strip().replace("⭐", "").replace(" ", "")
                if not cleaned.isdigit():
                    raise ValueError("Надішли тільки число, наприклад: 100")
                stars = int(cleaned)
                await self.validate_support_stars_amount(stars)
                await self.db.clear_state(tg_id)
                await self.create_support_stars_invoice(tg_id, lang, stars)
                return

            if not is_admin:
                await self.db.clear_state(tg_id)
                await self.bot.send_message(tg_id, tr(lang, "not_admin"))
                return

            if state == "admin_create_plan":
                parts = text.split(maxsplit=3)
                if len(parts) < 3:
                    raise ValueError("Format: code price days Назва")
                code = parts[0]
                price = parts[1]
                days = int(parts[2])
                name = parts[3] if len(parts) > 3 else code
                plan = await self.db.create_plan(code, price, days, name)
                await self.db.clear_state(tg_id)
                await self.bot.send_message(tg_id, f"✅ Створено тариф #{plan['id']} <code>{e(plan['code'])}</code>.")
                await self.show_admin_plan(tg_id, lang, int(plan["id"]))
                return

            if state == "admin_set_plan":
                plan_id = int(payload["plan_id"])
                field = str(payload["field"])
                await self.db.update_plan_field(plan_id, field, text)
                await self.db.clear_state(tg_id)
                await self.bot.send_message(tg_id, f"✅ Тариф #{plan_id}: <code>{e(field)}</code> оновлено.")
                await self.show_admin_plan(tg_id, lang, plan_id)
                return

            if state == "admin_set_method":
                code = str(payload["code"])
                field = str(payload["field"])
                await self.db.update_method_field(code, field, text)
                await self.db.clear_state(tg_id)
                await self.bot.send_message(tg_id, f"✅ Метод <code>{e(code)}</code>: <code>{e(field)}</code> оновлено.")
                await self.show_admin_method(tg_id, lang, code)
                return

            if state == "admin_set_setting":
                key = str(payload["key"])
                try:
                    value: Any = json.loads(text)
                except Exception:
                    value = int(text) if text.strip().lstrip("-").isdigit() else text
                await self.db.set_setting(key, value)
                await self.db.clear_state(tg_id)
                await self.bot.send_message(tg_id, f"✅ Налаштування <code>{e(key)}</code> оновлено: <code>{e(value)}</code>")
                await self.show_admin_settings(tg_id, lang)
                return

            if state == "admin_grant":
                parts = text.replace(",", " ").split()
                target = int(parts[0])
                days = int(parts[1]) if len(parts) > 1 else 30
                until = await self.db.grant_subscription(target, days)
                await self.db.clear_state(tg_id)
                await self.bot.send_message(tg_id, f"✅ Видано {days} днів для <code>{target}</code>. До {dt(until)}", admin_menu(lang))
                user_lang = await self.user_lang(target)
                await self.safe_send(target, tr(user_lang, "crypto_paid", date=dt(until)), main_menu(user_lang, False))
                return

            if state == "admin_revoke":
                target = int(text.split()[0])
                await self.db.revoke_subscription(target)
                await self.db.clear_state(tg_id)
                await self.bot.send_message(tg_id, f"✅ Доступ забрано у <code>{target}</code>.", admin_menu(lang))
                return

            if state == "admin_ref_bonus":
                parts = text.replace(",", " ").split()
                target = int(parts[0])
                days = int(parts[1]) if len(parts) > 1 else 0
                until = await self.db.add_manual_referral_bonus(target, days, admin_id=tg_id, note="admin panel")
                await self.db.clear_state(tg_id)
                await self.bot.send_message(tg_id, f"✅ Нараховано {days} дн. користувачу <code>{target}</code>. Доступ до {dt(until)}", admin_menu(lang))
                return

            if state == "admin_broadcast_interval":
                minutes = int(text.strip())
                chat_id = int(payload["chat_id"])
                await self.db.set_broadcast_interval(chat_id, minutes * 60)
                await self.db.clear_state(tg_id)
                await self.bot.send_message(tg_id, f"✅ Інтервал для чату <code>{chat_id}</code>: {minutes} хв.")
                await self.show_broadcast_chat(tg_id, lang, chat_id)
                return

            if state == "admin_broadcast_add":
                # Text path: a numeric chat_id was sent (the forward path is handled
                # earlier in handle_message because it may carry no text).
                raw = text.strip().split()[0]
                chat_id = int(raw)
                await self.db.add_broadcast_chat(chat_id, added_by=tg_id)
                await self.db.clear_state(tg_id)
                await self.bot.send_message(tg_id, f"✅ Чат <code>{chat_id}</code> додано до розсилок.")
                await self.show_broadcasts(tg_id, lang)
                return

            await self.db.clear_state(tg_id)
            await self.show_menu_screen(tg_id, lang, is_admin)
        except Exception as exc:
            await self.bot.send_message(tg_id, f"❌ Помилка:\n<code>{e(repr(exc))}</code>", cancel_keyboard(lang, "admin" if is_admin else "menu"))

    async def show_start(self, tg_id: int, lang: str, is_admin: bool) -> None:
        # First-ever launch grants a one-time free trial. The DB call is atomic
        # and idempotent, so it is safe to call on every /start.
        try:
            granted = await self.db.grant_trial_if_new(tg_id)
            if granted:
                await self.editable_send(tg_id, "trial_granted", lang, {"days": granted})
        except Exception as exc:
            print("Trial grant error:", repr(exc), flush=True)
        key = f"start_{lang}"
        tpl = await self.db.get_template(key)
        if tpl:
            await self.send_template_screen(tg_id, tpl, main_menu(lang, is_admin), track_key=key)
        else:
            result = await self.bot.send_message(tg_id, tr(lang, "start", app=e(self.settings.app_name), bot_username=e(self.bot_username())), main_menu(lang, is_admin))
            await self.track_sent(result, tg_id, key)
        # If the trial/subscription has lapsed, gently prompt to subscribe.
        if not is_admin and not await self.db.active_subscription(tg_id):
            await self.editable_send(tg_id, "access_locked", lang, keyboard=plans_keyboard(lang, await self.db.plans(True)))

    async def notify_referral_result(self, referrer_id: int, result: dict[str, Any]) -> None:
        """Tell the referrer they earned bonus days (or hit the normal limit)."""
        try:
            lang = await self.user_lang(referrer_id)
            if result.get("kind") == "premium":
                key, values = "ref_earned_premium", {"days": result.get("bonus_days", 0)}
            elif result.get("limit_reached"):
                key, values = "ref_limit_reached", {}
            elif result.get("bonus_days"):
                key, values = "ref_earned_normal", {"days": result.get("bonus_days", 0)}
            else:
                return
            await self.editable_send(referrer_id, key, lang, values)
        except Exception as exc:
            print("notify_referral_result error:", repr(exc), flush=True)

    async def maybe_nudge_subscription(self, owner_id: int, lang: str) -> None:
        """Send a subscription prompt at most once per 12h to a locked user."""
        try:
            key = f"sub_nudge_{owner_id}"
            now_ts = int(datetime.now(timezone.utc).timestamp())
            last = int(await self.db.get_setting(key, 0) or 0)
            if now_ts - last < 12 * 3600:
                return
            await self.db.set_setting(key, now_ts)
            await self.safe_send(owner_id, tr(lang, "access_locked"), plans_keyboard(lang, await self.db.plans(True)))
        except Exception as exc:
            print("maybe_nudge_subscription error:", repr(exc), flush=True)

    def support_text(self, lang: str) -> str:
        if lang == "ru":
            return (
                "⭐ <b>Поддержать проект</b>\n\n"
                "Можно отправить любое количество Telegram Stars. "
                "Оплата проходит прямо внутри Telegram и зачисляется на баланс бота.\n\n"
                "Выбери быстрый вариант ниже или введи своё количество."
            )
        if lang == "en":
            return (
                "⭐ <b>Support the project</b>\n\n"
                "You can send any amount of Telegram Stars. "
                "The payment is processed directly inside Telegram and goes to the bot balance.\n\n"
                "Choose a quick amount below or enter your own amount."
            )
        return (
            "⭐ <b>Підтримати проект</b>\n\n"
            "Можна відправити будь-яку кількість Telegram Stars. "
            "Оплата проходить прямо в Telegram і зараховується на баланс бота.\n\n"
            "Обери швидкий варіант нижче або введи свою кількість."
        )

    async def show_support(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        key = f"support_{lang}"
        tpl = await self.db.get_template(key)
        if tpl:
            await self.send_template_screen(tg_id, tpl, support_keyboard(lang), edit, track_key=key)
            return
        await self._send_or_edit(tg_id, self.support_text(lang), support_keyboard(lang), edit, track_key=key)

    async def validate_support_stars_amount(self, stars: int) -> None:
        # Telegram accepts integer Stars. Keep a sane configurable range so users
        # cannot accidentally create extreme invoices.
        min_stars = int(await self.db.get_setting("support_stars_min", 1))
        max_stars = int(await self.db.get_setting("support_stars_max", 2500))
        if stars < min_stars:
            raise ValueError(f"Minimum: {min_stars} Stars")
        if stars > max_stars:
            raise ValueError(f"Maximum: {max_stars} Stars")

    async def create_support_stars_invoice(self, tg_id: int, lang: str, stars: int) -> None:
        await self.validate_support_stars_amount(stars)
        amount_usd = (Decimal(stars) * Decimal("0.013")).quantize(Decimal("0.01"))
        payload = f"stars:support:{tg_id}:{stars}:{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        await self.db.create_payment(
            tg_id,
            None,
            "stars_support",
            amount_usd,
            currency="XTR",
            external_id=payload,
            raw={"kind": "support", "stars": stars, "estimated_usd": str(amount_usd)},
        )
        title = (
            f"{self.settings.app_name} — підтримка"
            if lang == "uk" else
            f"{self.settings.app_name} — поддержка"
            if lang == "ru" else
            f"{self.settings.app_name} — support"
        )
        desc = (
            "Підтримка проекту Telegram Stars. Підписка не активується."
            if lang == "uk" else
            "Поддержка проекта Telegram Stars. Подписка не активируется."
            if lang == "ru" else
            "Telegram Stars project support. This does not activate a subscription."
        )
        await self.bot.send_stars_invoice(tg_id, title, desc, payload, stars)
        await self.editable_send(tg_id, "invoice_stars_support", lang, {"stars": stars}, back_menu(lang, "support"))


    async def show_menu_screen(self, tg_id: int, lang: str, is_admin: bool, edit: tuple[int, int] | None = None) -> None:
        key = f"menu_{lang}"
        tpl = await self.db.get_template(key)
        if tpl:
            await self.send_template_screen(tg_id, tpl, main_menu(lang, is_admin), edit, track_key=key)
            return
        await self._send_or_edit(tg_id, tr(lang, "menu", app=e(self.settings.app_name)), main_menu(lang, is_admin), edit, track_key=key)

    async def show_language_screen(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        key = f"choose_lang_{lang}"
        tpl = await self.db.get_template(key)
        if tpl:
            await self.send_template_screen(tg_id, tpl, lang_keyboard(), edit, track_key=key)
            return
        await self._send_or_edit(tg_id, tr(lang, "choose_lang"), lang_keyboard(), edit, track_key=key)


    async def send_connect_card(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> bool:
        try:
            assets = Path(__file__).with_name("assets")
            asset_path: Path | None = None
            for ext in ("png", "jpg", "jpeg"):
                p = assets / f"connect_{lang}.{ext}"
                if p.exists():
                    asset_path = p
                    break
            if asset_path is None:
                for ext in ("png", "jpg", "jpeg"):
                    p = assets / f"connect_uk.{ext}"
                    if p.exists():
                        asset_path = p
                        break
            if asset_path is None:
                return False
            if edit:
                chat_id, message_id = edit
                try:
                    await self.bot.delete_message(chat_id, message_id)
                except Exception:
                    pass
            full_caption = tr(lang, "connect", app=e(self.settings.app_name), bot_username=e(self.bot_username()))
            # The image already shows the title with correct branding.
            # Strip the first line so wrong APP_NAME env never leaks into the caption.
            parts = full_caption.split("\n\n", 1)
            caption = parts[1] if len(parts) > 1 else full_caption
            content = asset_path.read_bytes()
            try:
                result = await self.bot.send_media_bytes(
                    tg_id, "photo", asset_path.name, content, caption[:1024], connect_keyboard(lang),
                )
            except Exception as kb_exc:
                # Some clients/Bot API builds reject the tg:// deep-link button.
                # Never let that break the connect screen — fall back to Back only.
                print("connect_keyboard send failed, retrying without deep-link:", repr(kb_exc), flush=True)
                result = await self.bot.send_media_bytes(
                    tg_id, "photo", asset_path.name, content, caption[:1024], back_menu(lang),
                )
            await self.track_sent(result, tg_id, f"connect_{lang}")
            return True
        except Exception as exc:
            print("send_connect_card failed:", repr(exc), flush=True)
            return False


    async def show_connect(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        video_url = await self.db.get_setting("connect_video_url", "")
        uah_rate = await self.db.get_setting("uah_rate", 42)
        video_file_id = await self.db.get_setting("connect_video_file_id", "")
        video_kind = await self.db.get_setting("connect_video_kind", "video")
        key = f"connect_{lang}"
        tpl = await self.db.get_template(key)
        if tpl:
            # Custom connect template may include its own photo/video.
            if video_url and not tpl.get("media"):
                label = "🎬 Video guide" if lang == "en" else "🎬 Видео-инструкция" if lang == "ru" else "🎬 Відео-інструкція"
                tpl = dict(tpl)
                tpl["text"] = f"{tpl.get('text') or ''}\n\n{label}: {e(video_url)}"
                tpl["entities"] = []
            try:
                await self.send_template_screen(tg_id, tpl, connect_keyboard(lang), edit, track_key=key)
            except Exception as exc:
                print("connect template send failed, retrying without deep-link:", repr(exc), flush=True)
                await self.send_template_screen(tg_id, tpl, back_menu(lang), edit, track_key=key)
        else:
            if await self.send_connect_card(tg_id, lang, edit):
                return
            text = tr(lang, "connect", app=e(self.settings.app_name), bot_username=e(self.bot_username()))
            entities = None
            if video_url:
                label = "🎬 Video guide" if lang == "en" else "🎬 Видео-инструкция" if lang == "ru" else "🎬 Відео-інструкція"
                text += f"\n\n{label}: {e(video_url)}"
                entities = None
            try:
                await self._send_or_edit(tg_id, text, connect_keyboard(lang), edit, entities=entities, track_key=key)
            except Exception as exc:
                print("connect text send failed, retrying without deep-link:", repr(exc), flush=True)
                await self._send_or_edit(tg_id, text, back_menu(lang), edit, entities=entities, track_key=key)
        if video_file_id:
            caption = "🎬 Video guide" if lang == "en" else "🎬 Видео-инструкция" if lang == "ru" else "🎬 Відео-інструкція"
            try:
                await self.bot.send_cached_media(tg_id, str(video_kind), str(video_file_id), caption)
            except Exception as exc:
                print("Send connect guide media error:", repr(exc))

    async def show_status(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        user = await self.db.get_user(tg_id)
        async with self.db._pool().acquire() as con:
            saved = await con.fetchval("SELECT COUNT(*) FROM cached_messages WHERE owner_tg_id=$1", tg_id) or 0
            deleted = await con.fetchval("SELECT COUNT(*) FROM deleted_events WHERE owner_tg_id=$1", tg_id) or 0
        sub_until = user.get("subscription_until") if user else None
        sub_active = bool(sub_until and sub_until > datetime.now(timezone.utc))
        sub_status = tr(lang, "sub_active", date=dt(sub_until)) if sub_active else tr(lang, "sub_free")
        has_business = await self.db.user_has_business(tg_id)
        business_status = tr(lang, "business_on") if has_business else tr(lang, "business_off")
        hint = tr(lang, "status_hint_ok") if has_business else tr(lang, "status_hint_connect")

        values = {
            "plan_name": sub_status,
            "business_status": business_status,
            "saved_count": str(saved),
            "deleted_count": str(deleted),
            "status_hint": hint,
        }
        await self.render_dynamic_screen(
            tg_id, "status", lang, values, back_menu(lang), edit, key=f"status_{lang}",
        )

    def access_status_line(self, user: dict[str, Any] | None, lang: str) -> str:
        sub_until = user.get("subscription_until") if user else None
        if sub_until and sub_until > datetime.now(timezone.utc):
            if lang == "en":
                return f"✅ Access until: <b>{dt(sub_until)}</b>"
            if lang == "uk":
                return f"✅ Доступ до: <b>{dt(sub_until)}</b>"
            return f"✅ Доступ до: <b>{dt(sub_until)}</b>"
        if lang == "en":
            return "🔒 No active subscription"
        if lang == "uk":
            return "🔒 Немає активної підписки"
        return "🔒 Нет активной подписки"

    async def show_plans(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        try:
            plans = await self.db.plans(active_only=True)
            if not plans:
                no_plans = (
                    "🔒 Активних тарифів поки немає. Поверніться пізніше."
                    if lang == "uk" else
                    "🔒 Активных тарифов пока нет. Вернитесь позже."
                    if lang == "ru" else
                    "🔒 No active plans yet. Check back later."
                )
                await self._send_or_edit(tg_id, no_plans, back_menu(lang), edit)
                return
            user = await self.db.get_user(tg_id)
            access_line = self.access_status_line(user, lang)
            # The full plan list (name, price, Stars) lives on the buttons, so the
            # text stays minimal: a short title and the user's current access.
            values = {"plans_list": access_line}
            await self.render_dynamic_screen(
                tg_id, "plans", lang, values, plans_keyboard(lang, plans), edit, key=f"plans_{lang}",
            )
        except Exception as exc:
            print("show_plans error:", repr(exc), flush=True)
            await self.safe_send(tg_id, "❌ Не вдалося завантажити тарифи. Спробуй /plans ще раз або напиши підтримці.")

    async def show_admin(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        if not await self.db.is_admin(tg_id):
            await self.bot.send_message(tg_id, tr(lang, "not_admin"))
            return
        await self._send_or_edit(tg_id, tr(lang, "admin"), admin_menu(lang), edit)

    async def show_keywords(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        words = await self.db.list_keywords(tg_id)
        monitored = await self.db.list_monitored_chats(tg_id)
        title = "🔎 <b>Keyword alerts</b>" if lang == "en" else "🔎 <b>Оповещения по ключевым словам</b>" if lang == "ru" else "🔎 <b>Сповіщення за ключовими словами</b>"
        empty = "No keywords yet." if lang == "en" else "Ключевых слов пока нет." if lang == "ru" else "Ключових слів поки немає."
        body = "\n".join([f"• <code>{e(w)}</code>" for w in words]) if words else empty

        # Group monitoring summary + how-to.
        groups_title = "📡 Monitored groups:" if lang == "en" else "📡 Группы на мониторинге:" if lang == "ru" else "📡 Групи на моніторингу:"
        if monitored:
            groups_body = "\n".join([f"• {e(c.get('title') or c.get('chat_id'))}" for c in monitored])
        else:
            groups_body = ("— none yet" if lang == "en" else "— пока нет" if lang == "ru" else "— поки немає")
        how_to = (
            "Add me to a group (as admin) and send <code>/watch</code> there. I'll DM you when your keywords appear. <code>/unwatch</code> to stop."
            if lang == "en" else
            "Добавь меня в группу (админом) и отправь там <code>/watch</code>. Я напишу в личку, когда встретятся твои слова. <code>/unwatch</code> — выключить."
            if lang == "ru" else
            "Додай мене в групу (адміном) і надішли там <code>/watch</code>. Я напишу в особисті, коли зʼявляться твої слова. <code>/unwatch</code> — вимкнути."
        )
        hint = f"{groups_title}\n{groups_body}\n\n{how_to}"

        values = {
            "keywords_list": body,
            "keywords_count": str(len(words)),
            "monitored_groups": groups_body,
            # Kept so older saved templates using {keywords_hint} still render.
            "keywords_hint": hint,
        }
        await self.render_dynamic_screen(
            tg_id, "keywords", lang, values, keywords_keyboard(lang, words, monitored), edit, key=f"keywords_{lang}",
        )

    async def show_keyword_delete_menu(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        words = await self.db.list_keywords(tg_id)
        text = "🗑 Choose keyword to delete:" if lang == "en" else "🗑 Выбери слово для удаления:" if lang == "ru" else "🗑 Обери слово для видалення:"
        await self._send_or_edit(tg_id, text, keyword_delete_keyboard(lang, words), edit)

    async def show_last_deleted(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        track_own = await self.db.get_track_own_messages(tg_id)
        async with self.db._pool().acquire() as con:
            # When "track own" is off, hide the owner's own deleted messages so the
            # list matches what the bot now forwards.
            own_filter = "" if track_own else " AND (cm.sender_id IS NULL OR cm.sender_id <> de.owner_tg_id)"
            rows = await con.fetch(
                f"""SELECT cm.chat_title, cm.sender_name, cm.text, cm.caption, cm.content_type, de.created_at
                   FROM deleted_events de
                   LEFT JOIN cached_messages cm ON cm.id=de.cached_message_id
                   WHERE de.owner_tg_id=$1{own_filter}
                   ORDER BY de.created_at DESC LIMIT 10""",
                tg_id,
            )
        rows = [dict(r) for r in rows]
        if not rows:
            deleted_list = "No deleted messages yet." if lang == "en" else "Удалённых сообщений пока нет." if lang == "ru" else "Видалених повідомлень поки немає."
        else:
            item_lines = []
            for r in rows:
                body = r.get("text") or r.get("caption") or f"[{r.get('content_type') or 'unknown'}]"
                item_lines.append(f"<b>{e(r.get('chat_title') or '')}</b> — {e(r.get('sender_name') or '')}\n{e(body)[:500]}\n<code>{dt(r.get('created_at'))}</code>")
            deleted_list = "\n\n".join(item_lines)

        values = {"deleted_messages_list": deleted_list, "deleted_count": str(len(rows))}
        await self.render_dynamic_screen(
            tg_id, "deleted", lang, values, last_deleted_keyboard(lang, track_own), edit, key=f"deleted_{lang}",
        )

    def disappearing_guide_text(self, lang: str) -> str:
        if lang == "ru":
            return (
                "👻 <b>Исчезающие сообщения — как это работает</b>\n\n"
                "Бот автоматически сохраняет исчезающие фото, видео, кружки и голосовые, "
                "как только они приходят в подключённый чат. Ничего нажимать не нужно.\n\n"
                "Как пользоваться:\n"
                "1️⃣ Подключи бота через <b>Telegram Business → Чат-боты</b>.\n"
                "2️⃣ Когда собеседник пришлёт исчезающее медиа, бот сразу пришлёт тебе копию сюда.\n"
                "3️⃣ Копия остаётся у тебя, даже если оригинал исчез или его удалили.\n\n"
                "💡 Удалённые сообщения смотри в разделе «Последние удалённые»."
            )
        if lang == "en":
            return (
                "👻 <b>Disappearing messages — how it works</b>\n\n"
                "The bot automatically saves disappearing photos, videos, video notes and voice "
                "messages the moment they arrive in a connected chat. You don't have to tap anything.\n\n"
                "How to use it:\n"
                "1️⃣ Connect the bot via <b>Telegram Business → Chatbots</b>.\n"
                "2️⃣ When someone sends disappearing media, the bot instantly forwards a copy to you here.\n"
                "3️⃣ The copy stays with you even after the original self-destructs or is deleted.\n\n"
                "💡 See deleted messages in the “Last deleted” section."
            )
        return (
            "👻 <b>Зникаючі повідомлення — як це працює</b>\n\n"
            "Бот автоматично зберігає зникаючі фото, відео, кружки та голосові одразу, "
            "щойно вони приходять у підключений чат. Нічого натискати не треба.\n\n"
            "Як користуватись:\n"
            "1️⃣ Підключи бота через <b>Telegram Business → Чат-боти</b>.\n"
            "2️⃣ Коли співрозмовник надішле зникаюче медіа, бот одразу пришле копію тобі сюди.\n"
            "3️⃣ Копія залишається в тебе, навіть якщо оригінал зник або його видалили.\n\n"
            "💡 Видалені повідомлення дивись у розділі «Останні видалені»."
        )

    async def show_disappearing_guide(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        video_url = await self.db.get_setting("guide_video_url", "")
        video_file_id = await self.db.get_setting("guide_video_file_id", "")
        video_kind = await self.db.get_setting("guide_video_kind", "video")
        key = f"disappearing_guide_{lang}"
        tpl = await self.db.get_template(key)
        if tpl:
            await self.send_template_screen(tg_id, tpl, back_menu(lang, "last_deleted"), edit, track_key=key)
        else:
            text = self.disappearing_guide_text(lang)
            if video_url:
                label = "🎬 Video guide" if lang == "en" else "🎬 Видео-инструкция" if lang == "ru" else "🎬 Відео-інструкція"
                text += f"\n\n{label}: {e(video_url)}"
            await self._send_or_edit(tg_id, text, back_menu(lang, "last_deleted"), edit, track_key=key)
        if video_file_id:
            caption = "🎬 Video guide" if lang == "en" else "🎬 Видео-инструкция" if lang == "ru" else "🎬 Відео-інструкція"
            try:
                await self.bot.send_cached_media(tg_id, str(video_kind), str(video_file_id), caption)
            except Exception as exc:
                print("Send disappearing guide media error:", repr(exc))



    def bot_username(self) -> str:
        return str(getattr(self.settings, "bot_username", None) or "vertuuSpyBot").lstrip("@")

    def referral_link(self, tg_id: int) -> str:
        return f"https://t.me/{self.bot_username()}?start=ref_{int(tg_id)}"

    async def show_referrals(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        stats = await self.db.referral_user_stats(tg_id)
        normal_days = await self.db.get_setting("ref_normal_days", 2)
        normal_limit = await self.db.get_setting("ref_normal_limit", 3)
        premium_days = await self.db.get_setting("ref_premium_days", 5)
        sub_until = stats.get("subscription_until")
        access_left = dt(sub_until) if sub_until and sub_until > datetime.now(timezone.utc) else ("—" if lang != "en" else "—")
        values = {
            "referral_link": self.referral_link(tg_id),
            "normal_count": str(stats.get("normal_count") or 0),
            "premium_count": str(stats.get("premium_count") or 0),
            "bonus_days_total": str(stats.get("bonus_days") or 0),
            "access_left": access_left,
            "normal_days": str(normal_days),
            "normal_limit": str(normal_limit),
            "premium_days": str(premium_days),
        }
        keyboard = referral_keyboard(lang, self.bot_username(), tg_id)
        await self.render_dynamic_screen(
            tg_id, "referrals", lang, values, keyboard, edit, key=f"referrals_{lang}",
        )

    async def track_sent(self, result: Any, fallback_chat_id: int, track_key: str | None) -> None:
        """Record (chat_id, message_id) -> template_key for deterministic /edit.

        Telegram send methods return the created message, so we always know the
        real message_id. This lets reply -> /edit resolve the exact template
        without guessing from the message text.
        """
        if not track_key or not isinstance(result, dict):
            return
        try:
            message_id = result.get("message_id")
            if not message_id:
                return
            chat = result.get("chat") or {}
            chat_id = chat.get("id") if isinstance(chat, dict) else None
            await self.db.record_sent_template(chat_id or fallback_chat_id, int(message_id), track_key)
        except Exception as exc:
            print("track_sent failed:", repr(exc))

    async def _send_or_edit(
        self,
        tg_id: int,
        text: str,
        keyboard: dict[str, Any] | None = None,
        edit: tuple[int, int] | None = None,
        entities: list[dict[str, Any]] | None = None,
        track_key: str | None = None,
    ) -> None:
        if edit:
            chat_id, message_id = edit
            try:
                await self.bot.edit_message_text(chat_id, message_id, text, keyboard, entities=entities)
                if track_key:
                    await self.db.record_sent_template(chat_id, message_id, track_key)
                else:
                    # This message was edited into a different screen with no
                    # template identity — drop any stale mapping so reply -> /edit
                    # does not resolve the previous screen's template.
                    await self.db.clear_sent_template(chat_id, message_id)
                return
            except Exception:
                pass
        result = await self.bot.send_message(tg_id, text, keyboard, entities=entities)
        await self.track_sent(result, tg_id, track_key)

    async def send_template_content(
        self,
        tg_id: int,
        text: str,
        entities: list[dict[str, Any]] | None,
        media: dict[str, Any] | None,
        keyboard: dict[str, Any] | None = None,
        track_key: str | None = None,
    ) -> None:
        """Send a reusable content screen.

        If the template has media and the text is short, we use a polished single
        media card with caption + buttons. If caption is too long for Telegram,
        we send media first and the rich text with buttons as a second message.
        """
        entities = entities or []
        if media and media.get("file_id") and media.get("kind"):
            kind = str(media.get("kind"))
            file_id = str(media.get("file_id"))
            # Best case: one clean media card. This also supports media-only
            # templates with inline buttons and no caption at all.
            if not text:
                try:
                    result = await self.bot.send_cached_media(tg_id, kind, file_id, None, keyboard)
                    await self.track_sent(result, tg_id, track_key)
                    return
                except Exception as exc:
                    print("send media-only template failed:", repr(exc))
            # Telegram captions are limited. Keep a single card when possible.
            if text and len(text) <= 1024:
                try:
                    result = await self.bot.send_cached_media(tg_id, kind, file_id, text, keyboard, caption_entities=entities)
                    await self.track_sent(result, tg_id, track_key)
                    return
                except Exception as exc:
                    print("send media template with caption failed:", repr(exc))
            # Fallback for long captions or unsupported formatting: send media
            # first and then the rich text with buttons separately.
            try:
                media_result = await self.bot.send_cached_media(tg_id, kind, file_id)
                # Track the media message too so reply -> /edit works on either part.
                await self.track_sent(media_result, tg_id, track_key)
            except Exception as exc:
                print("send media template failed:", repr(exc))
            if text:
                result = await self.bot.send_message(tg_id, text, keyboard, entities=entities)
                await self.track_sent(result, tg_id, track_key)
            elif keyboard:
                # Last-resort fallback. Normally media-only templates should be
                # sent as one card above; this is only here if Telegram rejects it.
                result = await self.bot.send_message(tg_id, "Відкрити нижче ⤵️", keyboard)
                await self.track_sent(result, tg_id, track_key)
            return
        result = await self.bot.send_message(tg_id, text or "—", keyboard, entities=entities)
        await self.track_sent(result, tg_id, track_key)

    async def send_template_screen(
        self,
        tg_id: int,
        tpl: dict[str, Any],
        keyboard: dict[str, Any] | None = None,
        edit: tuple[int, int] | None = None,
        track_key: str | None = None,
    ) -> None:
        media = tpl.get("media")
        text = str(tpl.get("text") or "")
        entities = tpl.get("entities") or []
        if media:
            if edit:
                chat_id, message_id = edit
                try:
                    await self.bot.delete_message(chat_id, message_id)
                except Exception:
                    pass
            await self.send_template_content(tg_id, text, entities, media, keyboard, track_key=track_key)
            return
        await self._send_or_edit(tg_id, text, keyboard, edit, entities=entities, track_key=track_key)

    async def handle_callback(self, cb: dict[str, Any]) -> None:
        cb_id = cb.get("id")
        from_user = cb.get("from") or {}
        user = await self.db.upsert_user(from_user)
        if not user:
            return
        tg_id = int(user["tg_id"])
        lang = str(user.get("lang") or self.settings.default_lang)
        data = cb.get("data") or ""
        msg = cb.get("message") or {}
        edit = (int(msg.get("chat", {}).get("id", tg_id)), int(msg.get("message_id"))) if msg.get("message_id") else None
        if cb_id:
            try:
                await self.bot.answer_callback_query(cb_id)
            except Exception:
                pass

        if data.startswith("cancel:"):
            await self.db.clear_state(tg_id)
            target = data.split(":", 1)[1]
            if target == "admin":
                await self.show_admin(tg_id, lang, edit)
            elif target == "keywords":
                await self.show_keywords(tg_id, lang, edit)
            elif target == "admin_settings":
                await self.show_admin_settings(tg_id, lang, edit)
            elif target == "admin_broadcast":
                await self.show_broadcasts(tg_id, lang, edit)
            elif target == "admin_userbroadcast":
                await self.show_user_broadcast(tg_id, lang, edit)
            elif target.startswith("admin_plan:"):
                await self.show_admin_plan(tg_id, lang, int(target.split(":", 1)[1]), edit)
            elif target.startswith("admin_method:"):
                await self.show_admin_method(tg_id, lang, target.split(":", 1)[1], edit)
            else:
                await self.show_menu_screen(tg_id, lang, await self.db.is_admin(tg_id), edit)
            return

        if data == "menu":
            await self.show_menu_screen(tg_id, lang, await self.db.is_admin(tg_id), edit)
        elif data == "status":
            await self.show_status(tg_id, lang, edit)
        elif data == "plans":
            await self.show_plans(tg_id, lang, edit)
        elif data == "connect":
            await self.show_connect(tg_id, lang, edit)
        elif data == "privacy":
            key = f"privacy_{lang}"
            tpl = await self.db.get_template(key)
            if tpl:
                await self.send_template_screen(tg_id, tpl, back_menu(lang), edit, track_key=key)
            else:
                await self._send_or_edit(tg_id, tr(lang, "privacy"), back_menu(lang), edit, track_key=key)
        elif data == "lang":
            await self.show_language_screen(tg_id, lang, edit)
        elif data == "last_deleted":
            await self.show_last_deleted(tg_id, lang, edit)
        elif data == "referrals":
            await self.show_referrals(tg_id, lang, edit)
        elif data == "support":
            await self.show_support(tg_id, lang, edit)
        elif data == "disappearing_guide":
            await self.show_disappearing_guide(tg_id, lang, edit)
        elif data == "toggle_own":
            new_val = not await self.db.get_track_own_messages(tg_id)
            await self.db.set_track_own_messages(tg_id, new_val)
            await self.show_last_deleted(tg_id, lang, edit)
        elif data == "support_custom":
            await self.db.set_state(tg_id, "support_stars_amount", {})
            await self._send_or_edit(tg_id, state_prompt(lang, "support_stars_amount", {}), back_menu(lang, "support"), edit)
        elif data.startswith("support_amount:"):
            stars = int(data.split(":", 1)[1])
            await self.validate_support_stars_amount(stars)
            await self.create_support_stars_invoice(tg_id, lang, stars)
        elif data == "keywords":
            await self.show_keywords(tg_id, lang, edit)
        elif data == "kw_add":
            await self.db.set_state(tg_id, "keyword_add", {})
            key = f"prompt_keyword_add_{lang}"
            tpl = await self.db.get_template(key)
            if tpl:
                await self.send_template_screen(tg_id, tpl, cancel_keyboard(lang, "keywords"), edit, track_key=key)
            else:
                await self._send_or_edit(tg_id, state_prompt(lang, "keyword_add", {}), cancel_keyboard(lang, "keywords"), edit, track_key=key)
        elif data == "kw_delete_menu":
            await self.show_keyword_delete_menu(tg_id, lang, edit)
        elif data.startswith("kw_del:"):
            words = await self.db.list_keywords(tg_id)
            idx = int(data.split(":", 1)[1])
            if 0 <= idx < len(words):
                await self.db.delete_keyword(tg_id, words[idx])
            await self.show_keywords(tg_id, lang, edit)
        elif data.startswith("kwchat_del:"):
            await self.db.remove_monitored_chat(int(data.split(":", 1)[1]), tg_id)
            await self.show_keywords(tg_id, lang, edit)
        elif data.startswith("setlang:"):
            new_lang = data.split(":", 1)[1]
            await self.db.set_lang(tg_id, new_lang)
            await self.show_menu_screen(tg_id, new_lang, await self.db.is_admin(tg_id), edit)
        elif data.startswith("buy:"):
            await self.callback_buy(tg_id, lang, int(data.split(":", 1)[1]), edit)
        elif data.startswith("pay:"):
            _, plan_id_s, method_code = data.split(":", 2)
            await self.callback_pay(tg_id, lang, int(plan_id_s), method_code, edit)
        elif data.startswith("check:"):
            await self.callback_check_crypto(tg_id, lang, int(data.split(":", 1)[1]), edit)
        elif data.startswith("manual_paid:"):
            await self.callback_manual_paid(tg_id, lang, int(data.split(":", 1)[1]))
        elif data.startswith("admin_approve:"):
            await self.admin_approve_callback(tg_id, lang, int(data.split(":", 1)[1]), approved=True)
        elif data.startswith("admin_reject:"):
            await self.admin_approve_callback(tg_id, lang, int(data.split(":", 1)[1]), approved=False)
        elif data == "admin":
            await self.show_admin(tg_id, lang, edit)
        elif data.startswith("admin_") or data.startswith("adm_") or data.startswith("bc_") or data.startswith("ub_"):
            await self.handle_admin_callback(tg_id, lang, data, edit)

    async def render_dynamic_screen(
        self,
        tg_id: int,
        base: str,
        lang: str,
        values: dict[str, str],
        keyboard: dict[str, Any] | None,
        edit: tuple[int, int] | None,
        *,
        key: str,
        fallback_key: str | None = None,
    ) -> None:
        """Render a dynamic screen from a single source of truth.

        Live screens and the /edit preview now both come from the same template
        (the saved one if it exists, otherwise the built-in default), so what the
        admin is asked to edit always matches what is actually on screen.
        """
        tpl = await self.db.get_template(key)
        if tpl is None and fallback_key:
            tpl = await self.db.get_template(fallback_key)
        src = str((tpl or {}).get("text") or dynamic_template_default(base, lang))
        src_ents = (tpl or {}).get("entities") or []
        rendered, ents = render_dynamic_template(src, src_ents, values)
        media = (tpl or {}).get("media")
        if media:
            if edit:
                try:
                    await self.bot.delete_message(edit[0], edit[1])
                except Exception:
                    pass
            await self.send_template_content(tg_id, rendered, ents, media, keyboard, track_key=key)
        else:
            await self._send_or_edit(tg_id, rendered, keyboard, edit, entities=ents, track_key=key)

    async def live_values_for_edit(
        self, base: str, lang: str, tg_id: int, target: dict[str, Any]
    ) -> dict[str, Any]:
        """Current live values for a dynamic screen, used to turn baked-in text
        back into {placeholders} in the /edit preview."""
        out: dict[str, Any] = {}
        try:
            if base == "plans":
                user = await self.db.get_user(tg_id)
                out["plans_list"] = html_to_plain(self.access_status_line(user, lang))
            elif base == "payment_manual":
                cb = first_callback_with_prefix(target.get("reply_markup"), "manual_paid:")
                if cb:
                    payment = await self.db.get_payment(int(cb.split(":", 1)[1]))
                    if payment:
                        method = await self.db.get_payment_method(str(payment.get("provider") or ""))
                        if method:
                            out["instructions"] = method_instructions(method, lang)
                        if payment.get("plan_id"):
                            plan = await self.db.get_plan(payment.get("plan_id"))
                            if plan:
                                out["plan_name"] = plan_name(plan, lang)
        except Exception as exc:
            print("live_values_for_edit failed:", base, repr(exc), flush=True)
        return out

    async def editable_send(
        self,
        tg_id: int,
        key: str,
        lang: str,
        values: dict[str, Any] | None = None,
        keyboard: dict[str, Any] | None = None,
        edit: tuple[int, int] | None = None,
    ) -> dict[str, Any] | None:
        """Send a one-off bot message that the admin can edit forever via /edit.

        Any message routed through here becomes a saved template under
        ``msg_<key>_<lang>``: an admin override (text + Premium-emoji entities +
        optional media) is used if present, otherwise the built-in i18n text.
        Dynamic data is passed as ``values`` and substituted into {placeholders},
        so it stays live. The sent message is recorded so reply -> /edit resolves
        exactly this message. ``edit`` replaces an existing message in place.
        """
        values = values or {}
        tkey = f"msg_{key}_{lang}"
        tpl = await self.db.get_template(tkey)
        try:
            if tpl:
                rendered, ents = render_dynamic_template(
                    str(tpl.get("text") or ""), tpl.get("entities") or [], values
                )
                media = tpl.get("media")
                if media:
                    if edit:
                        try:
                            await self.bot.delete_message(edit[0], edit[1])
                        except Exception:
                            pass
                    await self.send_template_content(tg_id, rendered, ents, media, keyboard, track_key=tkey)
                    return None
                await self._send_or_edit(tg_id, rendered, keyboard, edit, entities=ents, track_key=tkey)
                return None
            # Default i18n text uses HTML, so escape the live values for it.
            text = tr(lang, key, **{k: e(v) for k, v in values.items()})
            if edit:
                try:
                    await self.bot.edit_message_text(edit[0], edit[1], text, keyboard)
                    await self.db.record_sent_template(edit[0], edit[1], tkey)
                    return None
                except Exception:
                    pass
            result = await self.bot.send_message(tg_id, text, keyboard)
            await self.track_sent(result, tg_id, tkey)
            return result
        except Exception as exc:
            print("editable_send failed:", key, repr(exc), flush=True)
            return None

    async def callback_buy(self, tg_id: int, lang: str, plan_id: int, edit: tuple[int, int] | None) -> None:
        plan = await self.db.get_plan(plan_id)
        if not plan or not plan.get("is_active"):
            await self.show_plans(tg_id, lang, edit)
            return
        methods = await self.db.payment_methods(active_only=True)
        uah_rate = await self.db.get_setting("uah_rate", 42)
        amount_uah = plan_price_uah(plan, uah_rate)
        values = {
            "plan_name": plan_name(plan, lang),
            "amount_usd": str(plan["price_usd"]),
            "amount_uah": str(amount_uah) if amount_uah is not None else "",
            # Kept so older saved templates using {amount_uah_line} still render.
            "amount_uah_line": amount_uah_line(amount_uah, lang),
        }
        await self.render_dynamic_screen(
            tg_id, "choose_payment", lang, values,
            payment_methods_keyboard(lang, plan_id, methods), edit,
            key=f"choose_payment_{lang}",
        )

    async def callback_pay(self, tg_id: int, lang: str, plan_id: int, method_code: str, edit: tuple[int, int] | None) -> None:
        plan = await self.db.get_plan(plan_id)
        method = await self.db.get_payment_method(method_code)
        if not plan or not method or not method.get("is_active"):
            await self.show_plans(tg_id, lang, edit)
            return
        amount = Decimal(str(plan["price_usd"]))
        uah_rate = await self.db.get_setting("uah_rate", 42)
        amount_uah = plan_price_uah(plan, uah_rate)
        if method_code == "telegram_stars":
            try:
                stars = plan_price_stars(plan)
                payload = f"stars:{tg_id}:{plan_id}:{int(datetime.now(timezone.utc).timestamp())}"
                payment = await self.db.create_payment(tg_id, plan_id, "telegram_stars", amount, currency="XTR", external_id=payload, raw={"stars": stars})
                title = f"{self.settings.app_name} — {plan_name(plan, lang)}"
                desc = (
                    "Підписка активується автоматично після оплати зірками." if lang == "uk"
                    else "Подписка активируется автоматически после оплаты звёздами." if lang == "ru"
                    else "Your subscription activates automatically after paying with Stars."
                )
                await self.bot.send_stars_invoice(tg_id, title, desc, payload, stars)
                await self.editable_send(tg_id, "invoice_stars_plan", lang, {"stars": stars}, back_menu(lang, "plans"))
            except Exception as exc:
                print("Stars payment error:", repr(exc))
                await self.editable_send(tg_id, "payment_error", lang, keyboard=back_menu(lang))
            return

        if method_code == "cryptobot":
            try:
                invoice = await self.crypto.create_invoice(amount, f"{self.settings.app_name}: {plan_name(plan, 'en')}", f"user:{tg_id}:plan:{plan_id}")
                external_id = str(invoice.get("invoice_id"))
                url = invoice.get("bot_invoice_url") or invoice.get("mini_app_invoice_url") or invoice.get("web_app_invoice_url") or invoice.get("pay_url")
                payment = await self.db.create_payment(tg_id, plan_id, "cryptobot", amount, external_id=external_id, invoice_url=url, raw=invoice)
                await self.editable_send(
                    tg_id, "payment_crypto_created", lang,
                    {"amount": amount, "url": url or ""},
                    crypto_payment_keyboard(lang, int(payment["id"]), url or "https://t.me/CryptoBot"),
                    edit=edit,
                )
            except Exception as exc:
                print("Crypto payment error:", repr(exc))
                await self.editable_send(tg_id, "payment_error", lang, keyboard=back_menu(lang))
            return

        raw_payment = {"method": method_code}
        if method_code == "ua_card" and amount_uah is not None:
            raw_payment["amount_uah"] = str(amount_uah)
            raw_payment["uah_rate"] = str(uah_rate)
        payment = await self.db.create_payment(tg_id, plan_id, method_code, amount, raw=raw_payment)
        values = {
            "plan_name": plan_name(plan, lang),
            "amount_usd": str(amount),
            "amount_uah": str(amount_uah) if (method_code == "ua_card" and amount_uah is not None) else "",
            # Kept so older saved templates using these variables still render.
            "amount_uah_line": amount_uah_line(amount_uah, lang) if method_code == "ua_card" else "",
            "payment_amount_lines": payment_amount_lines(amount, amount_uah, method_code, lang),
            "instructions": method_instructions(method, lang),
        }
        # Per-method key so editing the TON screen does not change card/TRC20/BEP20.
        key = f"payment_manual_{method_code}_{lang}"
        await self.render_dynamic_screen(
            tg_id, "payment_manual", lang, values,
            manual_payment_keyboard(lang, int(payment["id"])), edit,
            key=key, fallback_key=f"payment_manual_{lang}",
        )

    async def callback_check_crypto(self, tg_id: int, lang: str, payment_id: int, edit: tuple[int, int] | None) -> None:
        payment = await self.db.get_payment(payment_id)
        if not payment or int(payment["user_id"]) != tg_id or payment["provider"] != "cryptobot":
            await self.editable_send(tg_id, "payment_error", lang)
            return
        if payment["status"] == "paid":
            await self.editable_send(tg_id, "crypto_paid", lang, {"date": dt(payment.get("paid_until") or (await self.db.get_user(tg_id) or {}).get("subscription_until"))})
            return
        try:
            invoice = await self.crypto.get_invoice(str(payment["external_id"]))
            if invoice and invoice.get("status") == "paid":
                paid = await self.db.mark_payment_paid(payment_id, raw=invoice)
                await self.editable_send(tg_id, "crypto_paid", lang, {"date": dt(paid.get("paid_until") if paid else None)}, main_menu(lang, await self.db.is_admin(tg_id)))
            else:
                await self.editable_send(tg_id, "crypto_not_paid", lang, keyboard=crypto_payment_keyboard(lang, payment_id, payment.get("invoice_url") or "https://t.me/CryptoBot"))
        except Exception as exc:
            print("Crypto check error:", repr(exc))
            await self.editable_send(tg_id, "payment_error", lang, keyboard=back_menu(lang))

    async def handle_pre_checkout_query(self, query: dict[str, Any]) -> None:
        query_id = str(query.get("id") or "")
        payload = str(query.get("invoice_payload") or "")
        if not query_id:
            return
        try:
            if payload.startswith("stars:"):
                payment = await self.db.get_payment_by_external_id(payload)
                if payment and payment.get("status") == "pending":
                    await self.bot.answer_pre_checkout_query(query_id, True)
                    return
            await self.bot.answer_pre_checkout_query(query_id, False, "Payment session is outdated. Please create a new invoice.")
        except Exception as exc:
            print("PreCheckout error:", repr(exc))
            try:
                await self.bot.answer_pre_checkout_query(query_id, False, "Payment check failed. Please try again.")
            except Exception:
                pass

    async def handle_stars_successful_payment(self, tg_id: int, lang: str, msg: dict[str, Any]) -> None:
        sp = msg.get("successful_payment") or {}
        payload = str(sp.get("invoice_payload") or "")
        if not payload.startswith("stars:"):
            return
        payment = await self.db.get_payment_by_external_id(payload)
        if not payment:
            await self.editable_send(tg_id, "payment_error", lang, keyboard=back_menu(lang))
            return
        raw = decode_json(payment.get("raw"), {}) or {}
        if not isinstance(raw, dict):
            raw = {"raw": raw}
        raw["successful_payment"] = sp
        raw["telegram_payment_charge_id"] = sp.get("telegram_payment_charge_id")
        raw["total_amount"] = sp.get("total_amount")
        raw["currency"] = sp.get("currency")

        if str(payment.get("provider") or "") == "stars_support":
            paid = await self.db.mark_support_payment_paid(int(payment["id"]), raw=raw)
            original_raw = decode_json(payment.get("raw"), {}) or {}
            stars = int(sp.get("total_amount") or original_raw.get("stars") or 0)
            text = (
                f"✅ <b>Дякую за підтримку!</b>\n\nТи відправив: <b>{stars} ⭐</b>\nЗірки зараховані на баланс бота."
                if lang == "uk" else
                f"✅ <b>Спасибо за поддержку!</b>\n\nТы отправил: <b>{stars} ⭐</b>\nЗвёзды зачислены на баланс бота."
                if lang == "ru" else
                f"✅ <b>Thanks for supporting!</b>\n\nYou sent: <b>{stars} ⭐</b>\nStars were added to the bot balance."
            )
            await self.bot.send_message(tg_id, text, main_menu(lang, await self.db.is_admin(tg_id)))
            user_obj = msg.get("from") or {}
            username = ("@" + user_obj.get("username")) if user_obj.get("username") else ""
            admin_text = (
                "⭐ <b>Support Stars received</b>\n\n"
                f"User: <code>{tg_id}</code> {e(username)}\n"
                f"Amount: <b>{stars} ⭐</b>\n"
                f"Payment ID: <code>{int(payment['id'])}</code>"
            )
            for admin_id in self.settings.admin_ids:
                if int(admin_id) != int(tg_id):
                    await self.safe_send(int(admin_id), admin_text)
            return

        paid = await self.db.mark_payment_paid(int(payment["id"]), raw=raw)
        text = (
            f"✅ <b>Оплату зірками прийнято.</b>\n\nДоступ активовано до: <b>{e(dt(paid.get('paid_until') if paid else None))}</b>"
            if lang == "uk" else
            f"✅ <b>Оплата звёздами принята.</b>\n\nДоступ активирован до: <b>{e(dt(paid.get('paid_until') if paid else None))}</b>"
            if lang == "ru" else
            f"✅ <b>Stars payment received.</b>\n\nAccess active until: <b>{e(dt(paid.get('paid_until') if paid else None))}</b>"
        )
        await self.bot.send_message(tg_id, text, main_menu(lang, await self.db.is_admin(tg_id)))

    async def callback_manual_paid(self, tg_id: int, lang: str, payment_id: int) -> None:
        payment = await self.db.get_payment(payment_id)
        if not payment or int(payment["user_id"]) != tg_id:
            await self.editable_send(tg_id, "payment_error", lang)
            return
        await self.db.set_state(tg_id, "manual_payment_proof", {"payment_id": payment_id})
        key = f"prompt_manual_payment_proof_{lang}"
        tpl = await self.db.get_template(key)
        if tpl:
            await self.send_template_screen(tg_id, tpl, cancel_keyboard(lang, "plans"), track_key=key)
        else:
            result = await self.bot.send_message(tg_id, state_prompt(lang, "manual_payment_proof", {"payment_id": payment_id}), cancel_keyboard(lang, "plans"))
            await self.track_sent(result, tg_id, key)

    async def notify_admin_payment(self, payment_id: int) -> None:
        payment = await self.db.get_payment(payment_id)
        if not payment:
            return
        user_id = int(payment["user_id"]) if payment.get("user_id") else 0
        user = await self.db.get_user(user_id) if user_id else None
        plan = await self.db.get_plan(int(payment["plan_id"])) if payment.get("plan_id") else None
        raw = decode_json(payment.get("raw"), {}) or {}
        proof = raw.get("proof") if isinstance(raw, dict) else None
        admin_text = (
            f"💳 <b>Manual payment request</b>\n\n"
            f"Payment ID: <code>{payment_id}</code>\n"
            f"User: <code>{user_id}</code> @{e((user or {}).get('username') or '')}\n"
            f"Provider: <b>{e(payment['provider'])}</b>\n"
            f"Plan: <b>{e(plan_name(plan, 'en'))}</b>\n"
            f"Amount: <b>${e(payment['amount_usd'])}</b>\n"
            f"Proof: <b>{e(proof_summary(proof))}</b>"
        )
        for admin_id in self.settings.admin_ids:
            try:
                await self.bot.send_message(admin_id, admin_text, admin_payment_keyboard(payment_id))
                if proof and proof.get("source_chat_id") and proof.get("source_message_id"):
                    await self.bot.copy_message(admin_id, int(proof["source_chat_id"]), int(proof["source_message_id"]))
            except Exception as exc:
                print("Notify admin error", admin_id, repr(exc))

    async def handle_payment_proof_message(self, tg_id: int, lang: str, msg: dict[str, Any], state_row: dict[str, Any], is_admin: bool) -> None:
        payload = state_row.get("payload") or {}
        payment_id = int(payload.get("payment_id") or 0)
        payment = await self.db.get_payment(payment_id)
        if not payment or int(payment.get("user_id") or 0) != tg_id:
            await self.db.clear_state(tg_id)
            await self.editable_send(tg_id, "payment_error", lang, keyboard=main_menu(lang, is_admin))
            return
        proof = extract_message_attachment(msg)
        proof.update({
            "source_chat_id": int(msg.get("chat", {}).get("id", tg_id)),
            "source_message_id": int(msg.get("message_id")),
            "from_user_id": tg_id,
            "date": msg.get("date"),
        })
        await self.db.add_payment_proof(payment_id, proof)
        await self.db.clear_state(tg_id)
        await self.editable_send(tg_id, "paid_wait_admin", lang, keyboard=main_menu(lang, is_admin))
        await self.notify_admin_payment(payment_id)

    async def handle_admin_upload_connect_video(self, tg_id: int, lang: str, msg: dict[str, Any], state_row: dict[str, Any]) -> None:
        proof = extract_message_attachment(msg)
        if not proof.get("file_id") or proof.get("kind") not in {"video", "document", "animation", "photo"}:
            await self.bot.send_message(tg_id, "❌ Надішли саме відео/файл/анімацію або фото з інструкцією.", cancel_keyboard(lang, "admin_settings"))
            return
        await self.db.set_setting("connect_video_file_id", proof["file_id"])
        await self.db.set_setting("connect_video_kind", proof["kind"])
        await self.db.clear_state(tg_id)
        await self.bot.send_message(tg_id, f"✅ Відео/медіа інструкцію збережено. Тип: <code>{e(proof['kind'])}</code>", admin_settings_keyboard(lang))

    async def handle_admin_upload_guide_video(self, tg_id: int, lang: str, msg: dict[str, Any], state_row: dict[str, Any]) -> None:
        proof = extract_message_attachment(msg)
        if not proof.get("file_id") or proof.get("kind") not in {"video", "document", "animation", "photo"}:
            await self.bot.send_message(tg_id, "❌ Надішли саме відео/файл/анімацію або фото з інструкцією.", cancel_keyboard(lang, "admin_settings"))
            return
        await self.db.set_setting("guide_video_file_id", proof["file_id"])
        await self.db.set_setting("guide_video_kind", proof["kind"])
        await self.db.clear_state(tg_id)
        await self.bot.send_message(tg_id, f"✅ Відео-інструкцію для зникаючих повідомлень збережено. Тип: <code>{e(proof['kind'])}</code>", admin_settings_keyboard(lang))

    async def admin_approve_callback(self, admin_id: int, lang: str, payment_id: int, approved: bool) -> None:
        if not await self.db.is_admin(admin_id):
            await self.bot.send_message(admin_id, tr(lang, "not_admin"))
            return
        payment = await self.db.get_payment(payment_id)
        if not payment:
            await self.bot.send_message(admin_id, "Payment not found")
            return
        user_id = int(payment["user_id"])
        user_lang = await self.user_lang(user_id)
        if approved:
            paid = await self.db.mark_payment_paid(payment_id, admin_id=admin_id)
            await self.bot.send_message(admin_id, f"✅ Payment {payment_id} approved. Access until {dt(paid.get('paid_until') if paid else None)}", admin_menu(lang))
            await self.bot.send_message(user_id, tr(user_lang, "crypto_paid", date=dt(paid.get("paid_until") if paid else None)), main_menu(user_lang, False))
        else:
            await self.db.mark_payment_status(payment_id, "rejected", admin_id=admin_id)
            await self.bot.send_message(admin_id, f"❌ Payment {payment_id} rejected.", admin_menu(lang))
            await self.bot.send_message(user_id, "❌ Payment rejected / Оплату відхилено / Оплата отклонена.")

    async def handle_admin_callback(self, tg_id: int, lang: str, data: str, edit: tuple[int, int] | None) -> None:
        if not await self.db.is_admin(tg_id):
            await self._send_or_edit(tg_id, tr(lang, "not_admin"), back_menu(lang), edit)
            return
        if data == "admin_stats":
            await self.show_admin_stats(tg_id, lang, edit)
        elif data == "admin_pending":
            await self.show_admin_pending(tg_id, lang, edit)
        elif data == "admin_referrals":
            await self.show_admin_referrals(tg_id, lang, edit)
        elif data == "adm_ref_bonus":
            await self.db.set_state(tg_id, "admin_ref_bonus", {})
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_ref_bonus", {}), cancel_keyboard(lang, "admin_referrals"), edit)
        elif data == "admin_broadcast":
            await self.db.clear_state(tg_id)
            await self.show_broadcasts(tg_id, lang, edit)
        elif data == "bc_template":
            await self.db.set_state(tg_id, "admin_broadcast_template", {})
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_broadcast_template", {}), cancel_keyboard(lang, "admin_broadcast"), edit)
        elif data == "bc_add":
            await self.db.set_state(tg_id, "admin_broadcast_add", {})
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_broadcast_add", {}), cancel_keyboard(lang, "admin_broadcast"), edit)
        elif data.startswith("bc_chat:"):
            await self.show_broadcast_chat(tg_id, lang, int(data.split(":", 1)[1]), edit)
        elif data.startswith("bc_int_custom:"):
            chat_id = int(data.split(":", 1)[1])
            await self.db.set_state(tg_id, "admin_broadcast_interval", {"chat_id": chat_id})
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_broadcast_interval", {}), cancel_keyboard(lang, "admin_broadcast"), edit)
        elif data.startswith("bc_int:"):
            _, chat_id_s, sec_s = data.split(":", 2)
            await self.db.set_broadcast_interval(int(chat_id_s), int(sec_s))
            await self.show_broadcast_chat(tg_id, lang, int(chat_id_s), edit)
        elif data.startswith("bc_toggle:"):
            chat_id = int(data.split(":", 1)[1])
            c = await self.db.get_broadcast_chat(chat_id)
            if c:
                await self.db.set_broadcast_active(chat_id, not c.get("is_active"))
            await self.show_broadcast_chat(tg_id, lang, chat_id, edit)
        elif data.startswith("bc_remove:"):
            await self.db.remove_broadcast_chat(int(data.split(":", 1)[1]))
            await self.show_broadcasts(tg_id, lang, edit)
        elif data == "bc_send_now":
            sent = await self.broadcast_send_now()
            await self._send_or_edit(tg_id, f"🚀 Розіслано в <b>{sent}</b> чат(ів).", back_menu(lang, "admin_broadcast"), edit)
        elif data == "admin_userbroadcast":
            await self.db.clear_state(tg_id)
            await self.show_user_broadcast(tg_id, lang, edit)
        elif data == "ub_template":
            await self.db.set_state(tg_id, "admin_userbroadcast_template", {})
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_userbroadcast_template", {}), cancel_keyboard(lang, "admin_userbroadcast"), edit)
        elif data == "ub_send_now":
            await self.user_broadcast_send_now(tg_id, lang, edit)
        elif data.startswith("admin_payment:"):
            await self.show_admin_payment(tg_id, lang, int(data.split(":", 1)[1]), edit)
        elif data.startswith("admin_proof:"):
            await self.send_payment_proof_to_admin(tg_id, lang, int(data.split(":", 1)[1]))
        elif data == "admin_plans":
            await self.show_admin_plans(tg_id, lang, edit)
        elif data == "adm_create_plan":
            await self.db.set_state(tg_id, "admin_create_plan", {})
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_create_plan", {}), cancel_keyboard(lang, "admin_plans"), edit)
        elif data.startswith("admin_plan:"):
            await self.show_admin_plan(tg_id, lang, int(data.split(":", 1)[1]), edit)
        elif data.startswith("adm_set_plan:"):
            _, plan_id_s, field = data.split(":", 2)
            payload = {"plan_id": int(plan_id_s), "field": field}
            await self.db.set_state(tg_id, "admin_set_plan", payload)
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_set_plan", payload), cancel_keyboard(lang, f"admin_plan:{plan_id_s}"), edit)
        elif data.startswith("adm_toggle_plan:"):
            plan_id = int(data.split(":", 1)[1])
            plan = await self.db.get_plan(plan_id)
            if plan:
                await self.db.update_plan_field(plan_id, "is_active", "0" if plan.get("is_active") else "1")
            await self.show_admin_plan(tg_id, lang, plan_id, edit)
        elif data == "admin_methods":
            await self.show_admin_methods(tg_id, lang, edit)
        elif data.startswith("admin_method:"):
            await self.show_admin_method(tg_id, lang, data.split(":", 1)[1], edit)
        elif data.startswith("adm_set_method:"):
            _, code, field = data.split(":", 2)
            payload = {"code": code, "field": field}
            await self.db.set_state(tg_id, "admin_set_method", payload)
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_set_method", payload), cancel_keyboard(lang, f"admin_method:{code}"), edit)
        elif data.startswith("adm_toggle_method:"):
            code = data.split(":", 1)[1]
            method = await self.db.get_payment_method(code)
            if method:
                await self.db.update_method_field(code, "is_active", "0" if method.get("is_active") else "1")
            await self.show_admin_method(tg_id, lang, code, edit)
        elif data == "admin_grant":
            await self.db.set_state(tg_id, "admin_grant", {})
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_grant", {}), cancel_keyboard(lang, "admin"), edit)
        elif data == "admin_revoke":
            await self.db.set_state(tg_id, "admin_revoke", {})
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_revoke", {}), cancel_keyboard(lang, "admin"), edit)
        elif data == "admin_settings":
            await self.show_admin_settings(tg_id, lang, edit)
        elif data.startswith("adm_set_setting:"):
            key = data.split(":", 1)[1]
            payload = {"key": key}
            await self.db.set_state(tg_id, "admin_set_setting", payload)
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_set_setting", payload), cancel_keyboard(lang, "admin_settings"), edit)
        elif data == "adm_upload_connect_video":
            await self.db.set_state(tg_id, "admin_upload_connect_video", {})
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_upload_connect_video", {}), cancel_keyboard(lang, "admin_settings"), edit)
        elif data == "adm_upload_guide_video":
            await self.db.set_state(tg_id, "admin_upload_guide_video", {})
            await self._send_or_edit(tg_id, state_prompt(lang, "admin_upload_guide_video", {}), cancel_keyboard(lang, "admin_settings"), edit)
        elif data == "admin_cashout":
            await self.show_cashout_confirm(tg_id, lang, edit)
        elif data == "admin_cashout_confirm":
            await self.perform_cashout(tg_id, lang, edit)
        elif data == "admin_cleanup":
            deleted = await self.db.cleanup_old_messages()
            await self._send_or_edit(tg_id, f"🧹 Cleanup done. Deleted rows: <b>{deleted}</b>", admin_settings_keyboard(lang), edit)
        elif data == "admin_users":
            await self.show_admin_users(tg_id, lang, edit)

    async def send_payment_proof_to_admin(self, admin_id: int, lang: str, payment_id: int) -> None:
        payment = await self.db.get_payment(payment_id)
        if not payment:
            await self.bot.send_message(admin_id, "Заявку не знайдено.")
            return
        raw = decode_json(payment.get("raw"), {}) or {}
        proof = raw.get("proof") if isinstance(raw, dict) else None
        if not proof:
            await self.bot.send_message(admin_id, "📎 Доказ оплати ще не додано.")
            return
        await self.bot.send_message(admin_id, f"📎 Доказ для заявки <code>#{payment_id}</code>: <b>{e(proof_summary(proof))}</b>")
        if proof.get("source_chat_id") and proof.get("source_message_id"):
            try:
                await self.bot.copy_message(admin_id, int(proof["source_chat_id"]), int(proof["source_message_id"]))
            except Exception as exc:
                await self.bot.send_message(admin_id, f"Не вийшло скопіювати доказ: <code>{e(repr(exc))}</code>")

    async def show_admin_stats(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        from datetime import datetime, timezone
        s = await self.db.extended_stats()
        now = datetime.now(timezone.utc).strftime("%d.%m %H:%M")
        ref = s.get("referrals") or {}
        plans = s.get("plans_breakdown") or []

        def fmt_usd(val: object) -> str:
            try:
                return f"{float(val):.2f}"
            except Exception:
                return "0.00"

        def fmt_uah(val: object) -> str:
            try:
                return f"{float(val):,.0f}".replace(",", " ")
            except Exception:
                return "0"

        def fmt_int(val: object) -> str:
            try:
                return f"{int(round(float(val)))}"
            except Exception:
                return "0"

        lines = [
            f"📊 <b>СТАТИСТИКА VERTUU SPY BOT</b> | {now}",
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️",
            "",
            "👥 <b>КОРИСТУВАЧІ:</b>",
            f"🚀 Всього: <b>{e(s.get('users_total', 0))}</b>",
            f"🆕 Нових сьогодні: <b>+{e(s.get('users_today', 0))}</b>",
            f"🌗 За 7 днів: <b>+{e(s.get('users_7d', 0))}</b>",
            f"☀️ За 30 днів: <b>+{e(s.get('users_30d', 0))}</b>",
            f"🔌 Активних підключень: <b>{e(s.get('connections_active', 0))}</b>",
            "",
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️",
            "",
            "💎 <b>ПІДПИСКИ:</b>",
            f"✅ Активних Pro: <b>{e(s.get('subs_active', 0))}</b>",
            f"⌛ Закінчились: <b>{e(s.get('subs_expired', 0))}</b>",
            f"📊 Всього куплено: <b>{e(s.get('payments_paid_count', 0))}</b>",
            "",
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️",
            "",
            "💰 <b>БАЛАНС</b> (до виплати, за валютою):",
            f"🇺🇦 Гривня: <b>{fmt_uah(s.get('revenue_uah', 0))} ₴</b> · {e(s.get('payments_uah_count', 0))} оплат",
            f"⭐ Stars (підписки): <b>{fmt_int(s.get('revenue_stars_subs', 0))} ⭐</b> · {e(s.get('payments_stars_subs_count', 0))} оплат",
            f"💝 Stars (підтримка): <b>{fmt_int(s.get('revenue_stars_support', 0))} ⭐</b> · {e(s.get('payments_stars_support_count', 0))} донатів",
            f"💲 Крипта (USDT/CryptoBot): <b>${fmt_usd(s.get('revenue_crypto_usd', 0))}</b> · {e(s.get('payments_crypto_count', 0))} оплат",
        ]
        if int(s.get("payments_ton_count", 0) or 0) > 0:
            lines.append(f"💎 TON: <b>${fmt_usd(s.get('revenue_ton_usd', 0))}</b> · {e(s.get('payments_ton_count', 0))} оплат")
        lines += [
            "",
            f"📊 Оплат до виплати: <b>{e(s.get('payments_uncashed_count', 0))}</b> (всього за весь час: {e(s.get('payments_paid_count', 0))})",
            f"⏳ Очікують перевірки: <b>{e(s.get('payments_pending', 0))}</b>",
            f"❌ Відхилено: <b>{e(s.get('payments_rejected', 0))}</b>",
            "💸 Виплата: <code>/cashout</code>",
            "",
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️",
            "",
            "📬 <b>ПОВІДОМЛЕННЯ:</b>",
            f"💬 Збережено: <b>{e(s.get('messages_total', 0))}</b>",
            f"👁 Видалень зафіксовано: <b>{e(s.get('deletions_total', 0))}</b>",
            f"✅ Доставлено власнику: <b>{e(s.get('deletions_delivered', 0))}</b>",
            f"🔥 Зникаючих медіа: <b>{e(s.get('messages_disappearing', 0))}</b>",
            "",
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️",
            "",
            "🔎 <b>КЛЮЧОВІ СЛОВА:</b>",
            f"📝 Активних фраз: <b>{e(s.get('keywords_active', 0))}</b>",
            f"👤 Користувачів з моніторингом: <b>{e(s.get('keywords_users', 0))}</b>",
        ]

        if plans:
            lines += ["", "〰️〰️〰️〰️〰️〰️〰️〰️〰️", "", "📋 <b>ТАРИФИ (продажі):</b>"]
            for p in plans:
                lines.append(f"💎 {e(p.get('name') or '—')}: <b>{e(p.get('cnt', 0))}</b> шт.")

        if ref:
            lines += [
                "",
                "〰️〰️〰️〰️〰️〰️〰️〰️〰️",
                "",
                "🤝 <b>РЕФЕРАЛИ:</b>",
                f"👥 Всього рефералів: <b>{e(ref.get('total_referrals', 0))}</b>",
                f"🟢 Звичайних: <b>{e(ref.get('normal_referrals', 0))}</b>",
                f"💎 Premium: <b>{e(ref.get('premium_referrals', 0))}</b>",
                f"🎁 Нараховано днів: <b>{e(ref.get('bonus_days_total', 0))}</b>",
            ]

        stats_kb = inline([
            [("💸 Виплата (cashout)", "admin_cashout")],
            [(btn(lang, "back"), "admin")],
        ])
        await self._send_or_edit(tg_id, "\n".join(lines), stats_kb, edit)

    def _balance_lines(self, b: dict[str, Any]) -> list[str]:
        def fmt_uah(v: object) -> str:
            try:
                return f"{float(v):,.0f}".replace(",", " ")
            except Exception:
                return "0"

        def fmt_int(v: object) -> str:
            try:
                return f"{int(round(float(v)))}"
            except Exception:
                return "0"

        def fmt_usd(v: object) -> str:
            try:
                return f"{float(v):.2f}"
            except Exception:
                return "0.00"

        lines = [
            f"🇺🇦 Гривня: <b>{fmt_uah(b.get('uah', 0))} ₴</b>",
            f"⭐ Stars (підписки): <b>{fmt_int(b.get('stars_subs', 0))} ⭐</b>",
            f"💝 Stars (підтримка): <b>{fmt_int(b.get('stars_support', 0))} ⭐</b>",
            f"💲 Крипта (USDT/CryptoBot): <b>${fmt_usd(b.get('crypto_usd', 0))}</b>",
        ]
        if int(b.get("ton_count", 0) or 0) > 0:
            lines.append(f"💎 TON: <b>${fmt_usd(b.get('ton_usd', 0))}</b>")
        return lines

    async def show_cashout_confirm(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        b = await self.db.current_balance()
        count = int(b.get("total_count", 0) or 0)
        if count <= 0:
            await self._send_or_edit(tg_id, "💸 <b>Виплата</b>\n\nНемає накопичених коштів до виплати.", back_menu(lang, "admin"), edit)
            return
        lines = [
            "💸 <b>Виплата (cashout)</b>",
            "",
            "Поточний баланс до виплати:",
            *self._balance_lines(b),
            "",
            f"Оплат у балансі: <b>{count}</b>",
            "",
            "⚠️ Підтвердження обнулить баланс у статистиці (позначить ці оплати як виплачені). Історія платежів збережеться.",
        ]
        kb = inline([
            [("✅ Підтвердити виплату", "admin_cashout_confirm")],
            [(btn(lang, "back"), "admin")],
        ])
        await self._send_or_edit(tg_id, "\n".join(lines), kb, edit)

    async def perform_cashout(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        result = await self.db.cashout_all(admin_id=tg_id)
        count = int(result.get("payments_count", 0) or 0)
        if count <= 0:
            await self._send_or_edit(tg_id, "💸 Немає коштів до виплати — баланс уже порожній.", back_menu(lang, "admin"), edit)
            return
        lines = [
            "✅ <b>Виплату виконано.</b>",
            "",
            "Знято з балансу:",
            *self._balance_lines(result),
            "",
            f"Позначено оплат як виплачені: <b>{count}</b>",
            "",
            "Баланс у статистиці обнулено. 💰",
        ]
        await self._send_or_edit(tg_id, "\n".join(lines), back_menu(lang, "admin"), edit)

    async def show_admin_referrals(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        s = await self.db.admin_referral_overview()
        lines = [
            "🤝 <b>Реферальна система</b>",
            "",
            f"👤 Рефоводів: <b>{e(s.get('referrers') or 0)}</b>",
            f"👥 Всього рефералів: <b>{e(s.get('total_referrals') or 0)}</b>",
            f"🟢 Звичайних: <b>{e(s.get('normal_referrals') or 0)}</b>",
            f"💎 Premium: <b>{e(s.get('premium_referrals') or 0)}</b>",
            f"🎁 Нараховано днів: <b>{e(s.get('bonus_days_total') or 0)}</b>",
            "",
            "🏆 <b>Топ рефоводів:</b>",
        ]
        top = s.get("top") or []
        if not top:
            lines.append("— поки немає даних")
        for row in top:
            name = display_name(row) or str(row.get("tg_id"))
            lines.append(
                f"• <code>{e(row.get('tg_id'))}</code> @{e(row.get('username') or '')} {e(name)}\n"
                f"  🟢 {e(row.get('normal_count') or 0)} | 💎 {e(row.get('premium_count') or 0)} | 🎁 {e(row.get('bonus_days') or 0)} дн."
            )
        lines += ["", "✏️ Ручне коригування: <code>/ref_bonus &lt;user_id&gt; &lt;днів&gt;</code>"]
        keyboard = inline([
            [("✏️ Нарахувати дні", "adm_ref_bonus")],
            [(btn(lang, "back"), "admin")],
        ])
        await self._send_or_edit(tg_id, "\n".join(lines), keyboard, edit)

    async def show_admin_plans(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        plans = await self.db.plans(active_only=False)
        text = "💎 <b>Конструктор тарифів</b>\n\nОбери тариф, щоб змінити ціну, тривалість, назву, опис або активність."
        await self._send_or_edit(tg_id, text, admin_plans_keyboard(lang, plans), edit)

    async def show_admin_plan(self, tg_id: int, lang: str, plan_id: int, edit: tuple[int, int] | None = None) -> None:
        p = await self.db.get_plan(plan_id)
        if not p:
            await self._send_or_edit(tg_id, "Тариф не знайдено.", back_menu(lang, "admin_plans"), edit)
            return
        text = (
            f"💎 <b>Тариф #{p['id']} — {e(p['code'])}</b>\n\n"
            f"Статус: {'✅ активний' if p.get('is_active') else '⛔️ вимкнений'}\n"
            f"Ціна: <b>${e(p['price_usd'])}</b>\n"
            f"Stars: <b>{e(plan_price_stars(p))} ⭐</b>\n"
            f"Тривалість: <b>{e(plan_duration_label(p.get('duration_days'), lang))}</b>\n"
            f"Позиція: <b>{e(p['position'])}</b>\n\n"
            f"🇺🇦 {e(p['name_uk'])}\n{e(p['features_uk'])}\n\n"
            f"🇷🇺 {e(p['name_ru'])}\n{e(p['features_ru'])}\n\n"
            f"🇬🇧 {e(p['name_en'])}\n{e(p['features_en'])}"
        )
        await self._send_or_edit(tg_id, text[:3900], admin_plan_keyboard(lang, plan_id, bool(p.get("is_active"))), edit)

    async def show_admin_methods(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        methods = await self.db.payment_methods(active_only=False)
        text = "🏦 <b>Конструктор методів оплати</b>\n\nОбери метод, щоб змінити назву, реквізити або вимкнути/увімкнути його."
        await self._send_or_edit(tg_id, text, admin_methods_keyboard(lang, methods), edit)

    async def show_admin_method(self, tg_id: int, lang: str, code: str, edit: tuple[int, int] | None = None) -> None:
        m = await self.db.get_payment_method(code)
        if not m:
            await self._send_or_edit(tg_id, "Метод не знайдено.", back_menu(lang, "admin_methods"), edit)
            return
        text = (
            f"🏦 <b>Метод оплати: <code>{e(code)}</code></b>\n\n"
            f"Статус: {'✅ активний' if m.get('is_active') else '⛔️ вимкнений'}\n"
            f"Позиція: <b>{e(m.get('position'))}</b>\n\n"
            f"🇺🇦 <b>{e(m['title_uk'])}</b>\n{e(m['instructions_uk'])}\n\n"
            f"🇷🇺 <b>{e(m['title_ru'])}</b>\n{e(m['instructions_ru'])}\n\n"
            f"🇬🇧 <b>{e(m['title_en'])}</b>\n{e(m['instructions_en'])}"
        )
        await self._send_or_edit(tg_id, text[:3900], admin_method_keyboard(lang, code, bool(m.get("is_active"))), edit)

    async def show_admin_pending(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        payments = await self.db.pending_payments(10)
        if not payments:
            await self._send_or_edit(tg_id, "✅ Немає ручних заявок на перевірку.", back_menu(lang, "admin"), edit)
            return
        text = "💳 <b>Ручні заявки на оплату</b>\n\nОбери заявку, щоб підтвердити або відхилити."
        await self._send_or_edit(tg_id, text, admin_pending_keyboard(lang, payments), edit)

    async def show_admin_payment(self, tg_id: int, lang: str, payment_id: int, edit: tuple[int, int] | None = None) -> None:
        p = await self.db.get_payment(payment_id)
        if not p:
            await self._send_or_edit(tg_id, "Заявку не знайдено.", back_menu(lang, "admin_pending"), edit)
            return
        user = await self.db.get_user(int(p["user_id"])) if p.get("user_id") else None
        plan = await self.db.get_plan(int(p["plan_id"])) if p.get("plan_id") else None
        p_raw = decode_json(p.get("raw"), {}) or {}
        p_proof = p_raw.get("proof") if isinstance(p_raw, dict) else None
        text = (
            f"💳 <b>Заявка #{p['id']}</b>\n\n"
            f"Статус: <b>{e(p['status'])}</b>\n"
            f"Користувач: <code>{e(p['user_id'])}</code> @{e((user or {}).get('username') or '')}\n"
            f"Тариф: <b>{e(plan_name(plan, 'uk'))}</b>\n"
            f"Метод: <b>{e(p['provider'])}</b>\n"
            f"Сума: <b>${e(p['amount_usd'])}</b>\n"
            f"Створено: <code>{dt(p.get('created_at'))}</code>\n"
            f"Доказ: <b>{e(proof_summary(p_proof))}</b>"
        )
        await self._send_or_edit(tg_id, text, admin_single_payment_keyboard(lang, payment_id), edit)

    async def show_admin_settings(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        free_limit = await self.db.get_setting("free_deleted_limit_per_day", self.settings.free_deleted_limit_per_day)
        free_hours = await self.db.get_setting("free_retention_hours", self.settings.free_retention_hours)
        paid_days = await self.db.get_setting("message_retention_days", self.settings.message_retention_days)
        video_url = await self.db.get_setting("connect_video_url", "")
        uah_rate = await self.db.get_setting("uah_rate", 42)
        video_file_id = await self.db.get_setting("connect_video_file_id", "")
        text = (
            "⚙️ <b>Налаштування</b>\n\n"
            f"🎁 Free deleted/day: <b>{e(free_limit)}</b>\n"
            f"🧹 Free retention hours: <b>{e(free_hours)}</b>\n"
            f"🗄 Paid retention days: <b>{e(paid_days)}</b>\n"
            f"🎬 Guide video file: <b>{'✅' if video_file_id else '—'}</b>\n"
            f"🔗 Guide video URL: <b>{e(video_url or '—')}</b>\n\n"
            "Натисни потрібну кнопку і надішли нове значення."
        )
        await self._send_or_edit(tg_id, text, admin_settings_keyboard(lang), edit)

    async def show_admin_users(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        users = await self.db.recent_users(10)
        lines = ["👥 <b>Останні користувачі</b>"]
        for u in users:
            name = display_name(u) or "—"
            sub = "✅" if u.get("subscription_until") and u["subscription_until"] > datetime.now(timezone.utc) else "—"
            lines.append(f"{sub} <code>{u['tg_id']}</code> {e(name)} @{e(u.get('username') or '')}\n<code>{dt(u.get('created_at'))}</code>")
        await self._send_or_edit(tg_id, "\n\n".join(lines), back_menu(lang, "admin"), edit)

    # ===================== Broadcast system =====================

    @staticmethod
    def interval_label(seconds: int) -> str:
        seconds = int(seconds or 0)
        if seconds % 3600 == 0 and seconds >= 3600:
            return f"{seconds // 3600} год"
        return f"{max(1, seconds // 60)} хв"

    async def show_broadcasts(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        if not await self.db.is_admin(tg_id):
            await self._send_or_edit(tg_id, tr(lang, "not_admin"), back_menu(lang), edit)
            return
        chats = await self.db.list_broadcast_chats()
        tpl = await self.db.get_setting("broadcast_template", None)
        has_tpl = bool(isinstance(tpl, dict) and tpl.get("message_ids"))
        lines = [
            "📢 <b>Автоматичні розсилки</b>",
            "",
            f"📝 Шаблон: <b>{'✅ збережено' if has_tpl else '— не задано'}</b>",
            f"💬 Чатів підключено: <b>{len(chats)}</b>",
        ]
        if chats:
            lines.append("")
            for c in chats:
                status = "✅" if c.get("is_active") else "⏸"
                title = e(c.get("title") or str(c.get("chat_id")))
                last = dt(c.get("last_sent_at")) if c.get("last_sent_at") else "—"
                lines.append(f"{status} <b>{title}</b>\n   ⏱ {e(self.interval_label(c.get('interval_seconds')))} · остання: {last}")
        else:
            lines += ["", "Зроби бота адміністратором у групі — він додасться автоматично, або натисни «➕ Додати чат»."]
        lines += ["", "ℹ️ Перед кожною новою розсилкою бот видаляє своє попереднє повідомлення в чаті."]
        await self._send_or_edit(tg_id, "\n".join(lines), broadcast_menu_keyboard(lang, chats, has_tpl), edit)

    async def show_broadcast_chat(self, tg_id: int, lang: str, chat_id: int, edit: tuple[int, int] | None = None) -> None:
        c = await self.db.get_broadcast_chat(chat_id)
        if not c:
            await self.show_broadcasts(tg_id, lang, edit)
            return
        text = (
            f"💬 <b>{e(c.get('title') or chat_id)}</b>\n"
            f"<code>{e(chat_id)}</code>\n\n"
            f"Статус: <b>{'✅ активний' if c.get('is_active') else '⏸ пауза'}</b>\n"
            f"Інтервал: <b>{e(self.interval_label(c.get('interval_seconds')))}</b>\n"
            f"Остання розсилка: <b>{dt(c.get('last_sent_at')) if c.get('last_sent_at') else '—'}</b>\n\n"
            "Обери інтервал або керуй чатом:"
        )
        await self._send_or_edit(tg_id, text, broadcast_chat_keyboard(lang, chat_id, bool(c.get("is_active"))), edit)

    async def handle_broadcast_template_message(self, tg_id: int, lang: str, msg: dict[str, Any], state_row: dict[str, Any]) -> None:
        mid = msg.get("message_id")
        if not mid:
            return
        mgid = msg.get("media_group_id")
        now_ts = int(datetime.now(timezone.utc).timestamp())
        existing = await self.db.get_setting("broadcast_template", None)
        # Album parts arrive as separate updates with the same media_group_id;
        # collect them into one template within a short window.
        if (
            mgid
            and isinstance(existing, dict)
            and existing.get("media_group_id") == str(mgid)
            and existing.get("chat_id") == tg_id
            and now_ts - int(existing.get("ts") or 0) < 20
        ):
            ids = list(existing.get("message_ids") or [])
            if int(mid) not in ids:
                ids.append(int(mid))
            await self.db.set_setting("broadcast_template", {"chat_id": tg_id, "message_ids": ids, "media_group_id": str(mgid), "ts": now_ts})
            return  # stay silent for extra album parts
        tpl = {"chat_id": tg_id, "message_ids": [int(mid)], "media_group_id": str(mgid) if mgid else None, "ts": now_ts}
        await self.db.set_setting("broadcast_template", tpl)
        done_kb = inline([[("✅ Готово", "admin_broadcast")]])
        await self.bot.send_message(
            tg_id,
            "✅ <b>Шаблон збережено.</b>\nЦе повідомлення буде розсилатися в підключені чати.\n\n"
            "Для альбому перешли решту частин зараз. Коли готово — натисни кнопку нижче.",
            done_kb,
        )

    async def handle_broadcast_add_message(self, tg_id: int, lang: str, msg: dict[str, Any], state_row: dict[str, Any]) -> None:
        chat_obj = msg.get("forward_from_chat") or (msg.get("forward_origin") or {}).get("chat") or {}
        if not chat_obj or not chat_obj.get("id"):
            await self.bot.send_message(tg_id, "⚠️ Не вдалося визначити чат. Перешли повідомлення саме з потрібної групи/каналу або надішли числовий chat_id.")
            return
        chat_id = int(chat_obj["id"])
        await self.db.add_broadcast_chat(chat_id, title=chat_obj.get("title"), chat_type=chat_obj.get("type"), added_by=tg_id)
        await self.db.clear_state(tg_id)
        await self.bot.send_message(tg_id, f"✅ Чат <b>{e(chat_obj.get('title') or chat_id)}</b> додано до розсилок.")
        await self.show_broadcasts(tg_id, lang)

    async def broadcast_to_chat(self, chat: dict[str, Any], template: dict[str, Any]) -> bool:
        """Delete the bot's previous broadcast in the chat, then post the template.

        Returns True if a new message was posted.
        """
        chat_id = int(chat["chat_id"])
        from_chat = int(template.get("chat_id"))
        message_ids = [int(x) for x in (template.get("message_ids") or [])]
        if not message_ids:
            return False
        # Delete the previous broadcast message(s) so only one stays in the chat.
        prev = await self.db.get_setting(f"bc_last_{chat_id}", []) or []
        for pmid in prev:
            try:
                await self.bot.delete_message(chat_id, int(pmid))
            except Exception:
                pass
        try:
            sent = await self.bot.copy_messages(chat_id, from_chat, message_ids)
            new_ids = [int(m["message_id"]) for m in sent if isinstance(m, dict) and m.get("message_id")]
            await self.db.set_setting(f"bc_last_{chat_id}", new_ids)
            await self.db.update_broadcast_sent(chat_id, new_ids[0] if new_ids else None)
            return True
        except Exception as exc:
            text = repr(exc)
            print("Broadcast send failed:", chat_id, text, flush=True)
            # If the bot lost access / rights, pause the chat to stop log spam.
            if any(t in text for t in ("chat not found", "bot was kicked", "not enough rights", "CHAT_ADMIN_REQUIRED", "have no rights", "blocked")):
                try:
                    await self.db.set_broadcast_active(chat_id, False)
                except Exception:
                    pass
            # Still bump the timer so a broken chat does not get retried every tick.
            await self.db.update_broadcast_sent(chat_id, None)
            return False

    async def run_due_broadcasts(self) -> int:
        if not await self.db.get_setting_bool("broadcast_enabled", True):
            return 0
        template = await self.db.get_setting("broadcast_template", None)
        if not isinstance(template, dict) or not template.get("message_ids"):
            return 0
        sent = 0
        for chat in await self.db.due_broadcast_chats():
            if await self.broadcast_to_chat(chat, template):
                sent += 1
        return sent

    async def broadcast_send_now(self) -> int:
        template = await self.db.get_setting("broadcast_template", None)
        if not isinstance(template, dict) or not template.get("message_ids"):
            return 0
        sent = 0
        for chat in await self.db.list_broadcast_chats(active_only=True):
            if await self.broadcast_to_chat(chat, template):
                sent += 1
        return sent

    # ===================== In-bot broadcast (to all users) =====================

    async def show_user_broadcast(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        tpl = await self.db.get_setting("user_broadcast_template", None)
        has_tpl = isinstance(tpl, dict) and bool(tpl.get("message_ids"))
        total = await self.db.count_users()
        lines = [
            "📨 <b>Розсилка в боті</b>",
            "",
            f"📝 Повідомлення: <b>{'✅ збережено' if has_tpl else '— не задано'}</b>",
            f"👤 Користувачів у базі: <b>{total}</b>",
            "",
            "Задай повідомлення і натисни «Розіслати всім» — бот надішле його кожному в особисті.",
        ]
        await self._send_or_edit(tg_id, "\n".join(lines), user_broadcast_menu_keyboard(lang, has_tpl), edit)

    async def handle_user_broadcast_template_message(self, tg_id: int, lang: str, msg: dict[str, Any], state_row: dict[str, Any]) -> None:
        mid = msg.get("message_id")
        if not mid:
            return
        mgid = msg.get("media_group_id")
        now_ts = int(datetime.now(timezone.utc).timestamp())
        existing = await self.db.get_setting("user_broadcast_template", None)
        # Album parts arrive as separate updates with the same media_group_id;
        # collect them into one template within a short window.
        if (
            mgid
            and isinstance(existing, dict)
            and existing.get("media_group_id") == str(mgid)
            and existing.get("chat_id") == tg_id
            and now_ts - int(existing.get("ts") or 0) < 20
        ):
            ids = list(existing.get("message_ids") or [])
            if int(mid) not in ids:
                ids.append(int(mid))
            await self.db.set_setting("user_broadcast_template", {"chat_id": tg_id, "message_ids": ids, "media_group_id": str(mgid), "ts": now_ts})
            return  # stay silent for extra album parts
        tpl = {"chat_id": tg_id, "message_ids": [int(mid)], "media_group_id": str(mgid) if mgid else None, "ts": now_ts}
        await self.db.set_setting("user_broadcast_template", tpl)
        # Keep the state so extra album parts (separate updates with the same
        # media_group_id) are still collected. State is cleared when the admin
        # opens the menu or sends. The send/back buttons handle navigation.
        done_kb = inline([[("🚀 Розіслати всім", "ub_send_now")], [("⬅️ Назад", "admin_userbroadcast")]])
        await self.bot.send_message(
            tg_id,
            "✅ <b>Повідомлення збережено.</b>\nВоно буде надіслано всім користувачам бота.\n\n"
            "Для альбому перешли решту частин зараз. Коли готово — натисни «Розіслати всім».",
            done_kb,
        )

    async def user_broadcast_send_now(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        await self.db.clear_state(tg_id)
        template = await self.db.get_setting("user_broadcast_template", None)
        if not isinstance(template, dict) or not template.get("message_ids"):
            await self._send_or_edit(tg_id, "⚠️ Спочатку задай повідомлення для розсилки.", user_broadcast_menu_keyboard(lang, False), edit)
            return
        # Run the delivery loop in the background so the webhook callback returns
        # immediately and Telegram does not retry/timeout on large user bases.
        await self._send_or_edit(tg_id, "🚀 Розсилаю… Звіт надішлю, коли завершу.", back_menu(lang, "admin_userbroadcast"), edit)
        asyncio.create_task(self._run_user_broadcast(tg_id, lang, template))

    async def _run_user_broadcast(self, admin_id: int, lang: str, template: dict[str, Any]) -> None:
        from_chat = int(template.get("chat_id"))
        message_ids = [int(x) for x in (template.get("message_ids") or [])]
        sent = 0
        failed = 0
        try:
            for uid in await self.db.all_user_ids():
                try:
                    await self.bot.copy_messages(uid, from_chat, message_ids)
                    sent += 1
                except Exception as exc:
                    failed += 1
                    print("User broadcast send failed:", uid, repr(exc), flush=True)
                # Telegram allows ~30 messages/sec to different users. Throttle
                # gently to stay under the limit and avoid 429s on large bases.
                await asyncio.sleep(0.05)
        except Exception as exc:
            print("User broadcast loop crashed:", repr(exc), flush=True)
        try:
            await self.bot.send_message(
                admin_id,
                f"✅ <b>Розсилку завершено.</b>\n\nДоставлено: <b>{sent}</b>\nНе вдалося (блок/видалили бота): <b>{failed}</b>",
                back_menu(lang, "admin_userbroadcast"),
            )
        except Exception as exc:
            print("User broadcast report failed:", repr(exc), flush=True)

    async def handle_my_chat_member(self, upd: dict[str, Any]) -> None:
        """Auto-register/unregister broadcast chats as the bot's admin status changes."""
        chat = upd.get("chat") or {}
        chat_id = chat.get("id")
        ctype = chat.get("type")
        new_member = upd.get("new_chat_member") or {}
        status = new_member.get("status")
        if not chat_id or ctype not in {"group", "supergroup", "channel"}:
            return
        if status == "administrator":
            await self.db.add_broadcast_chat(int(chat_id), title=chat.get("title"), chat_type=ctype)
            for admin_id in self.settings.admin_ids:
                try:
                    await self.bot.send_message(int(admin_id), f"📢 Бот став адміном у <b>{e(chat.get('title') or chat_id)}</b> — чат додано до розсилок.")
                except Exception:
                    pass
        elif status in {"left", "kicked"}:
            await self.db.remove_broadcast_chat(int(chat_id))
        elif status == "member":
            # Demoted from admin: cannot delete messages, so pause broadcasting.
            existing = await self.db.get_broadcast_chat(int(chat_id))
            if existing:
                await self.db.set_broadcast_active(int(chat_id), False)

    # ===================== Group keyword monitoring =====================

    async def handle_group_message(self, msg: dict[str, Any]) -> None:
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if not chat_id:
            return
        from_user = msg.get("from") or {}
        text = (msg.get("text") or "").strip()
        # /watch and /unwatch are delivered even with privacy mode on, so users
        # can register a chat without making the bot read everything first.
        cmd0 = text.split()[0].split("@")[0] if text else ""
        if cmd0 in {"/watch", "/unwatch"}:
            await self.handle_group_watch_command(msg, chat, from_user, cmd0)
            return
        # Keyword matching for every user monitoring this chat.
        body = msg.get("text") or msg.get("caption") or ""
        if not body:
            return
        owners = await self.db.monitor_owners_for_chat(int(chat_id))
        if not owners:
            return
        sender_id = int(from_user["id"]) if from_user.get("id") else None
        sender_name = display_name(from_user) or (msg.get("sender_chat") or {}).get("title") or "—"
        chat_title = chat.get("title") or str(chat_id)
        for o in owners:
            owner_id = int(o["owner_tg_id"])
            if sender_id and owner_id == sender_id:
                continue  # never alert a user about their own message
            if not await self.db.active_subscription(owner_id):
                continue
            try:
                matches = await self.db.match_keywords(owner_id, body)
            except Exception:
                matches = []
            if not matches:
                continue
            lang = await self.user_lang(owner_id)
            title = (
                "🔎 <b>Keyword in group</b>" if lang == "en"
                else "🔎 <b>Ключевое слово в группе</b>" if lang == "ru"
                else "🔎 <b>Ключове слово в групі</b>"
            )
            await self.safe_send(
                owner_id,
                f"{title}: {', '.join(e(m) for m in matches)}\n\n"
                f"<b>{tr(lang, 'chat')}:</b> {e(chat_title)}\n"
                f"<b>{tr(lang, 'from')}:</b> {e(sender_name)}\n\n{e(body)[:2500]}",
            )

    async def handle_group_watch_command(self, msg: dict[str, Any], chat: dict[str, Any], from_user: dict[str, Any], cmd: str) -> None:
        chat_id = int(chat["id"])
        chat_title = chat.get("title") or str(chat_id)
        if not from_user or not from_user.get("id"):
            return
        await self.db.upsert_user(from_user)
        uid = int(from_user["id"])
        lang = await self.user_lang(uid)

        if cmd == "/unwatch":
            removed = await self.db.remove_monitored_chat(chat_id, uid)
            reply = (
                ("🛑 Monitoring of this chat is off." if removed else "This chat was not monitored.") if lang == "en"
                else ("🛑 Мониторинг этого чата выключен." if removed else "Этот чат не отслеживался.") if lang == "ru"
                else ("🛑 Моніторинг цього чату вимкнено." if removed else "Цей чат не був у моніторингу.")
            )
            await self._reply_in_group(chat_id, reply)
            return

        # /watch — gated by subscription/trial like the rest of the features.
        if not await self.db.active_subscription(uid):
            locked = (
                "🔒 Active subscription required. Open the bot in DM: /start" if lang == "en"
                else "🔒 Нужна активная подписка. Открой бота в личке: /start" if lang == "ru"
                else "🔒 Потрібна активна підписка. Відкрий бота в особистих: /start"
            )
            await self._reply_in_group(chat_id, locked)
            return
        kws = await self.db.list_keywords(uid)
        await self.db.add_monitored_chat(chat_id, uid, chat_title)
        no_kw = (
            "\n⚠️ You have no keywords yet — add them in the bot: 🔎 Keywords." if lang == "en"
            else "\n⚠️ У тебя ещё нет ключевых слов — добавь их в боте: 🔎 Ключевые слова." if lang == "ru"
            else "\n⚠️ У тебе ще немає ключових слів — додай їх у боті: 🔎 Ключові слова."
        ) if not kws else ""
        group_ok = (
            "✅ Watching this chat for your keywords. Alerts go to our DM.\nℹ️ Make me admin (or disable Privacy Mode) so I can read all messages." if lang == "en"
            else "✅ Слежу за этим чатом по твоим ключевым словам. Уведомления придут в наш личный чат.\nℹ️ Сделай меня админом (или выключи Privacy Mode), чтобы я видел все сообщения." if lang == "ru"
            else "✅ Стежу за цим чатом за твоїми ключовими словами. Сповіщення прийдуть у наш особистий чат.\nℹ️ Зроби мене адміном (або вимкни Privacy Mode), щоб я бачив усі повідомлення."
        )
        await self._reply_in_group(chat_id, group_ok + no_kw)
        dm = (
            f"✅ Monitoring of group <b>{e(chat_title)}</b> is on. Keyword alerts will arrive here." if lang == "en"
            else f"✅ Мониторинг группы <b>{e(chat_title)}</b> включён. Уведомления о ключевых словах будут приходить сюда." if lang == "ru"
            else f"✅ Моніторинг групи <b>{e(chat_title)}</b> увімкнено. Сповіщення про ключові слова приходитимуть сюди."
        )
        try:
            await self.bot.send_message(uid, dm)
        except Exception:
            pass

    async def _reply_in_group(self, chat_id: int, text: str) -> None:
        try:
            await self.bot.send_message(chat_id, text)
        except Exception as exc:
            print("group reply failed:", repr(exc), flush=True)

    async def handle_business_connection(self, data: dict[str, Any]) -> None:
        conn = await self.db.upsert_business_connection(data)
        if not conn or not conn.get("owner_tg_id"):
            return
        owner_id = int(conn["owner_tg_id"])
        lang = await self.user_lang(owner_id)
        try:
            if conn.get("is_enabled"):
                key = f"business_connected_{lang}"
                tpl = await self.db.get_template(key)
                if tpl:
                    await self.send_template_screen(owner_id, tpl, main_menu(lang, await self.db.is_admin(owner_id)), track_key=key)
                else:
                    result = await self.bot.send_message(owner_id, tr(lang, "business_connected"), main_menu(lang, await self.db.is_admin(owner_id)))
                    await self.track_sent(result, owner_id, key)
            else:
                await self.bot.send_message(owner_id, tr(lang, "business_disabled"), main_menu(lang, await self.db.is_admin(owner_id)))
        except Exception as exc:
            print("Business connection notify error:", repr(exc))


    def media_cache_max_bytes(self) -> int:
        try:
            return int(os.getenv("MEDIA_CACHE_MAX_BYTES", "25000000"))
        except Exception:
            return 25_000_000

    async def cache_media_file_bytes_from_message(self, cached: dict[str, Any], msg: dict[str, Any]) -> None:
        """Immediately download media bytes while Telegram still allows getFile.

        This is important for disappearing/timer media: after Telegram removes it,
        a normal file_id resend/getFile may fail. If Bot API provides file_id at
        receive time, we save a small binary copy in PostgreSQL.
        """
        kind = str(cached.get("content_type") or "unknown")
        file_id = cached.get("file_id")
        cached_id = cached.get("id")
        if not cached_id or not file_id:
            # If timer media is hidden from Business Bot API, Telegram may send no
            # file_id at all. Log raw keys so we can verify in Railway logs.
            if kind in {"photo", "video", "voice", "video_note", "audio", "animation", "document", "sticker", "unknown"}:
                print("Media cache skipped: no file_id", {"kind": kind, "message_id": msg.get("message_id"), "keys": sorted(list(msg.keys()))}, flush=True)
            return
        if kind not in {"photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker"}:
            return
        if cached.get("file_bytes"):
            return

        file_name, declared_size, mime_type, is_disappearing = extract_file_metadata(msg)
        max_bytes = self.media_cache_max_bytes()
        try:
            if declared_size and int(declared_size) > max_bytes:
                print("Media cache skipped: file too large", {"kind": kind, "size": declared_size, "max": max_bytes}, flush=True)
                return
            info = await self.bot.get_file(str(file_id))
            telegram_size = info.get("file_size")
            if telegram_size and int(telegram_size) > max_bytes:
                print("Media cache skipped: Telegram file too large", {"kind": kind, "size": telegram_size, "max": max_bytes}, flush=True)
                return
            file_path = str(info.get("file_path") or "")
            if not file_path:
                print("Media cache skipped: empty file_path", {"kind": kind, "file_id": str(file_id)[:20]}, flush=True)
                return
            content = await self.bot.download_file(file_path, max_bytes=max_bytes)
            await self.db.set_cached_file_bytes(
                int(cached_id),
                content,
                file_name=file_name,
                file_size=len(content),
                mime_type=mime_type,
                is_disappearing=bool(is_disappearing),
            )
            print("Media cached bytes", {"kind": kind, "bytes": len(content), "message_id": msg.get("message_id"), "timer_hint": bool(is_disappearing)}, flush=True)
        except Exception as exc:
            print("Media cache bytes failed:", repr(exc), json.dumps({"kind": kind, "message_id": msg.get("message_id"), "keys": sorted(list(msg.keys()))}, ensure_ascii=False)[:1000], flush=True)

    def only_live_location_changed(self, old: dict[str, Any] | None, new: dict[str, Any], msg: dict[str, Any]) -> bool:
        """Ignore live-location coordinate updates so the bot doesn't spam edit alerts."""
        if not msg.get("location"):
            return False
        if str(new.get("content_type") or "") != "location":
            return False
        old_body = (old.get("text") or old.get("caption")) if old else None
        new_body = new.get("text") or new.get("caption")
        # For location messages our DB stores JSON in text. Telegram edits the
        # coordinates every few seconds. Treat it as technical update, not content edit.
        return True




    def raw_update_has_timer_hint(self, value: Any) -> bool:
        """Detect explicit timer/self-destruct hints in raw Telegram update."""
        if isinstance(value, dict):
            for key, val in value.items():
                low = str(key).lower()
                if any(marker in low for marker in (
                    "ttl",
                    "self_destruct",
                    "self-destruct",
                    "selfdestruct",
                    "destruct",
                    "disappear",
                    "disappearing",
                    "expire",
                    "expires",
                    "timer",
                    "auto_delete",
                    "autodelete",
                )):
                    return True
                if isinstance(val, str) and any(marker in val.lower() for marker in (
                    "ttl", "timer", "self_destruct", "self-destruct", "disappear"
                )):
                    return True
                if self.raw_update_has_timer_hint(val):
                    return True
        elif isinstance(value, list):
            return any(self.raw_update_has_timer_hint(x) for x in value)
        return False

    async def is_timer_media_candidate(self, cached: dict[str, Any], msg: dict[str, Any]) -> bool:
        """Timer-only immediate delivery detector.

        Telegram does not always expose a perfect `is_timer_media` flag to bots.
        This function therefore uses two layers:
        1) explicit raw timer/self-destruct/ttl hints => always timer;
        2) fallback candidate mode => only captionless photo/video/video_note,
           never voice/audio/document/sticker, never albums, never text/caption.

        This keeps ordinary voice/docs from being sent instantly while still
        catching the common disappearing photo/video cases.
        """
        if not cached:
            return False

        kind = str(cached.get("content_type") or "")
        if kind not in {"photo", "video", "video_note"}:
            return False

        # Never instantly forward albums or media with captions/text. A normal
        # photo/video with a caption is not treated as timer media.
        if msg.get("caption") or msg.get("text") or msg.get("media_group_id"):
            return False

        _file_name, _file_size, _mime_type, explicit_hint = extract_file_metadata(msg)
        explicit_hint = bool(explicit_hint or self.raw_update_has_timer_hint(msg))

        # Telegram marks 1-view (view-once) photos and videos with has_protected_content=True.
        # In private chats this reliably identifies view-once media — the bot must save it
        # immediately since no "open" event exists and the deletion event may not fire.
        # We skip this check for groups where has_protected_content can be set for all
        # messages when group-forwarding is disabled by the admin.
        if not explicit_hint and msg.get("has_protected_content"):
            chat_type = (msg.get("chat") or {}).get("type", "private")
            if chat_type == "private":
                explicit_hint = True

        if explicit_hint:
            return True

        # IMPORTANT — DO NOT proactively forward ordinary media.
        # Beyond the confirmed disappearing signals handled above (has_protected_content
        # for 1-view media + explicit TTL/self-destruct hints), we must NOT auto-send
        # media just because it arrived without a caption. Capturing every captionless
        # photo/video/circle from a contact floods the owner with normal, non-disappearing
        # media — exactly the false positive being reported.
        #
        # Genuine disappearing media that Telegram does not flag is instead captured via
        # the reply mechanism (handle_reply_reveals_timer_media): the owner replies to the
        # message BEFORE opening it and the bot extracts the file then. That path is the
        # reliable way to view disappearing media and is fully preserved.
        #
        # The block below remains only as an OPT-IN power-user fallback. It is OFF by
        # default for every media type and never fires for the owner's own outgoing media.
        sender_id = int((msg.get("from") or {}).get("id") or 0)
        owner_id_val = int(cached.get("owner_tg_id") or 0)
        if not sender_id or not owner_id_val or sender_id == owner_id_val:
            return False

        fallback_enabled = os.getenv("TIMER_MEDIA_CAPTIONLESS_INSTANT", "false").lower() in {"1", "true", "yes", "on"}
        if not fallback_enabled:
            return False

        # Optional hard override through DB settings. The rebuild seed forces it
        # to true, but env false still wins above.
        try:
            db_enabled = await self.db.get_setting_bool("timer_media_candidate_instant", True)
            if not db_enabled:
                return False
        except Exception:
            pass

        try:
            allowed = await self.db.get_setting("timer_media_candidate_types", ["photo", "video", "video_note"])
            if isinstance(allowed, list) and kind not in {str(x) for x in allowed}:
                return False
        except Exception:
            pass

        return True

    async def maybe_send_timer_media_candidate_immediately(self, cached: dict[str, Any], msg: dict[str, Any]) -> None:
        """Immediately send timer-like media to the protected user's bot chat.

        Important: this is NOT used for voice/audio/documents/stickers. Those are
        cached silently and only sent if a deletion event comes later.
        """
        if not cached or not cached.get("owner_tg_id"):
            return
        if not await self.is_timer_media_candidate(cached, msg):
            kind_for_log = str(cached.get("content_type") or "unknown")
            if kind_for_log in {"photo", "video", "video_note"}:
                print("Timer media instant not triggered", {
                    "cached_id": cached.get("id"),
                    "message_id": cached.get("message_id"),
                    "kind": kind_for_log,
                    "has_caption": bool(msg.get("caption")),
                    "has_media_group_id": bool(msg.get("media_group_id")),
                    "raw_timer_hint": self.raw_update_has_timer_hint(msg),
                    "has_file_id": bool(cached.get("file_id")),
                    "has_bytes": cached.get("file_bytes") is not None,
                }, flush=True)
            return

        kind = str(cached.get("content_type") or "unknown")
        owner_id = int(cached["owner_tg_id"])
        lang = await self.user_lang(owner_id)

        refreshed = await self.db.find_cached_message(
            str(cached.get("business_connection_id")),
            int(cached.get("chat_id")),
            int(cached.get("message_id")),
        )
        row = refreshed or cached

        if row.get("media_backup_sent_at"):
            print("Timer media instant skipped: already sent", {
                "cached_id": row.get("id"),
                "message_id": row.get("message_id"),
                "kind": kind,
            }, flush=True)
            return

        if not (row.get("file_id") or row.get("file_bytes") is not None):
            print("Timer media instant skipped: no file data", {
                "cached_id": row.get("id"),
                "kind": kind,
                "message_id": row.get("message_id"),
                "keys": sorted(list(msg.keys())),
            }, flush=True)
            return

        explicit = bool(self.raw_update_has_timer_hint(msg))
        try:
            await self.send_media_alert(
                owner_id, lang, "alert_timer_saved",
                row.get("chat_title") or row.get("chat_id"),
                row.get("sender_name") or row.get("sender_id"), kind,
            )
            delivered = await self.send_deleted_media_copy(
                owner_id,
                lang,
                kind,
                str(row.get("file_id") or ""),
                row.get("caption"),
                row,
            )
            print("Timer media instant delivery result", {
                "cached_id": row.get("id"),
                "message_id": row.get("message_id"),
                "kind": kind,
                "explicit_hint": explicit,
                "captionless_fallback": not explicit,
                "has_bytes": row.get("file_bytes") is not None,
                "has_file_id": bool(row.get("file_id")),
                "delivered": delivered,
            }, flush=True)
            if delivered:
                await self.db.mark_media_backup_sent(int(row["id"]))
        except Exception as exc:
            print("Timer media instant delivery failed:", repr(exc), {
                "cached_id": row.get("id"),
                "message_id": row.get("message_id"),
                "kind": kind,
            }, flush=True)

    async def maybe_send_disappearing_media_immediately(self, cached: dict[str, Any], msg: dict[str, Any]) -> None:
        """If Telegram marks media as timer/self-destructing, save/show it immediately.

        Some timer media may not emit deleted_business_messages later. Waiting for
        deletion can therefore miss the moment. If Bot API exposes a timer hint,
        we notify the owner right away after caching bytes.
        """
        if not cached or not cached.get("owner_tg_id"):
            return
        _file_name, _file_size, _mime_type, is_disappearing = extract_file_metadata(msg)
        if not is_disappearing:
            return
        # Don't capture the owner's own outgoing timer media (false positive).
        sender_id = int((msg.get("from") or {}).get("id") or 0)
        owner_id = int(cached["owner_tg_id"])
        if sender_id and sender_id == owner_id:
            return
        print("Explicit disappearing media hint detected; sending immediate backup", {
            "kind": cached.get("content_type"),
            "message_id": cached.get("message_id"),
            "chat_id": cached.get("chat_id"),
        }, flush=True)
        kind = str(cached.get("content_type") or "unknown")
        if kind not in {"photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker"}:
            return
        if not await self.db.can_use_free_deleted(owner_id):
            lang = await self.user_lang(owner_id)
            await self.safe_send(owner_id, tr(lang, "free_limit"), plans_keyboard(lang, await self.db.plans(True)))
            return
        lang = await self.user_lang(owner_id)
        refreshed = await self.db.find_cached_message(str(cached["business_connection_id"]), int(cached["chat_id"]), int(cached["message_id"]))
        row = refreshed or cached
        await self.send_media_alert(
            owner_id, lang, "alert_disappearing_saved",
            row.get("chat_title") or row.get("chat_id"),
            row.get("sender_name") or row.get("sender_id"), kind,
        )
        if row.get("file_id") or row.get("file_bytes"):
            delivered = await self.send_deleted_media_copy(owner_id, lang, kind, str(row.get("file_id") or ""), row.get("caption"), row)
            if delivered:
                await self.db.consume_free_deleted(owner_id)



    async def maybe_send_instant_media_backup(self, cached: dict[str, Any], msg: dict[str, Any]) -> None:
        """Send incoming media to the owner immediately.

        Telegram does not reliably mark timer/self-destruct media in Business API
        (`timer_hint` can be False), and deletion events can arrive with internal
        ids. So the reliable product behavior is: if media comes through Business,
        save it and instantly send a backup to the bot chat. This catches timer
        media even if the user never opens it and even if no delete event arrives.
        """
        if not cached or not cached.get("owner_tg_id"):
            return

        kind = str(cached.get("content_type") or "unknown")
        if kind not in {"photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker"}:
            return
        if cached.get("media_backup_sent_at"):
            return
        if not (cached.get("file_id") or cached.get("file_bytes") is not None):
            print("Instant media backup skipped: no file data", {
                "kind": kind,
                "message_id": cached.get("message_id"),
                "chat_id": cached.get("chat_id"),
            }, flush=True)
            return

        owner_id = int(cached["owner_tg_id"])
        # Don't forward the owner's own outgoing media (false positive).
        sender_id = int((msg.get("from") or {}).get("id") or 0)
        if sender_id and sender_id == owner_id:
            return
        is_admin = await self.db.is_admin(owner_id)
        # For normal users, keep this as a Pro feature. Admin can always test.
        if not is_admin and not await self.db.active_subscription(owner_id):
            return

        lang = await self.user_lang(owner_id)
        # Reload after cache_media_file_bytes_from_message, because `cached` may
        # not contain file_bytes yet.
        refreshed = await self.db.find_cached_message(
            str(cached.get("business_connection_id")),
            int(cached.get("chat_id")),
            int(cached.get("message_id")),
        )
        row = refreshed or cached

        if row.get("media_backup_sent_at"):
            return
        if not (row.get("file_id") or row.get("file_bytes") is not None):
            return

        try:
            await self.send_media_alert(
                owner_id, lang, "alert_media_backup",
                row.get("chat_title") or row.get("chat_id"),
                row.get("sender_name") or row.get("sender_id"), kind,
            )
            delivered = await self.send_deleted_media_copy(
                owner_id,
                lang,
                kind,
                str(row.get("file_id") or ""),
                row.get("caption"),
                row,
            )
            if delivered:
                await self.db.mark_media_backup_sent(int(row["id"]))
                print("Instant media backup sent", {
                    "cached_id": row.get("id"),
                    "kind": kind,
                    "message_id": row.get("message_id"),
                    "has_bytes": row.get("file_bytes") is not None,
                    "has_file_id": bool(row.get("file_id")),
                }, flush=True)
        except Exception as exc:
            print("Instant media backup failed:", repr(exc), {
                "cached_id": row.get("id"),
                "kind": kind,
                "message_id": row.get("message_id"),
            }, flush=True)


    def _extract_reply_media(self, reply_to: dict[str, Any]) -> tuple[str, str]:
        """Return (kind, file_id) for VIEW-ONCE/TIMER media inside a reply_to_message.

        Only extracts when the replied-to message is confirmed to be view-once or
        timer media. Regular captionless photos/videos are intentionally skipped
        to prevent false-positive captures when the owner or a contact replies to
        normal media.
        """
        if reply_to.get("caption"):
            return "", ""

        # Require a hard signal that this is actually view-once or self-destruct media.
        # has_protected_content=True is what Telegram sets on 1-view (view-once) messages.
        # raw_update_has_timer_hint catches explicit TTL/self-destruct fields.
        # Without at least one of these signals we leave regular media alone.
        is_protected = bool(reply_to.get("has_protected_content"))
        has_timer   = self.raw_update_has_timer_hint(reply_to)
        if not is_protected and not has_timer:
            return "", ""

        if reply_to.get("photo"):
            best = max(reply_to["photo"], key=lambda p: p.get("file_size") or 0)
            return "photo", best.get("file_id") or ""
        if reply_to.get("video"):
            return "video", reply_to["video"].get("file_id") or ""
        if reply_to.get("video_note"):
            return "video_note", reply_to["video_note"].get("file_id") or ""
        return "", ""

    async def handle_reply_reveals_timer_media(self, msg: dict[str, Any], cached_reply: dict[str, Any] | None) -> None:
        """Owner replied to a contact's captionless photo/video/video_note.

        When the owner replies to ANY message, Telegram includes the full
        reply_to_message object in the business_message update — with the
        media's file_id intact. For view-once media this is the ONLY
        reliable way to extract the file: the owner replies BEFORE opening,
        which triggers this extraction automatically.
        """
        reply_to = msg.get("reply_to_message")
        if not reply_to:
            return

        kind, file_id = self._extract_reply_media(reply_to)
        if not kind or not file_id:
            return

        # Determine owner from cached reply or from the business connection
        bc_id = msg.get("business_connection_id")
        if cached_reply and cached_reply.get("owner_tg_id"):
            owner_id = int(cached_reply["owner_tg_id"])
        else:
            conn = await self.db.get_business_connection(bc_id) if bc_id else None
            if not conn or not conn.get("owner_tg_id"):
                return
            owner_id = int(conn["owner_tg_id"])

        # Only trigger when the OWNER is the one who replied (they replied to a contact's media)
        sender_id = int((msg.get("from") or {}).get("id") or 0)
        if sender_id != owner_id:
            return

        # The media must be FROM a contact (not the owner's own outgoing message).
        # If replied_from_id is 0 (field missing), we cannot confirm it's a contact
        # — skip to avoid accidentally re-sending the owner's own media.
        replied_from_id = int((reply_to.get("from") or {}).get("id") or 0)
        if not replied_from_id or replied_from_id == owner_id:
            return

        chat = msg.get("chat") or {}
        chat_id = int(chat.get("id") or 0)
        replied_msg_id = int(reply_to.get("message_id") or 0)

        # Skip if we already sent this media (proactive capture already worked)
        existing: dict[str, Any] | None = None
        if bc_id and chat_id and replied_msg_id:
            try:
                existing = await self.db.find_cached_message(bc_id, chat_id, replied_msg_id)
            except Exception:
                pass
        if existing and existing.get("media_backup_sent_at"):
            print("Reply-revealed media already sent proactively, skipping duplicate", {
                "message_id": replied_msg_id,
            }, flush=True)
            return

        if not await self.db.can_use_free_deleted(owner_id):
            lang = await self.user_lang(owner_id)
            await self.safe_send(owner_id, tr(lang, "free_limit"), plans_keyboard(lang, await self.db.plans(True)))
            return

        lang = await self.user_lang(owner_id)
        fr = reply_to.get("from") or {}
        sender_name = " ".join(filter(None, [fr.get("first_name"), fr.get("last_name")])) or str(replied_from_id)

        delivered = False
        try:
            await self.send_media_alert(
                owner_id, lang, "alert_timer_reply",
                chat.get("title") or str(chat_id), sender_name, kind,
            )
            # Try sending by file_id first (works for most media including view-once via reply)
            try:
                await self.bot.send_cached_media(owner_id, kind, file_id)
                delivered = True
            except Exception as exc_fid:
                print("Reply media file_id send failed, attempting download:", repr(exc_fid), flush=True)
                try:
                    file_info = await self.bot.get_file(file_id)
                    file_path_remote = file_info.get("file_path") or ""
                    if file_path_remote:
                        file_bytes = await self.bot.download_file(file_path_remote)
                        ext = {"photo": "jpg", "video": "mp4", "video_note": "mp4"}.get(kind, "bin")
                        await self.bot.send_media_bytes(owner_id, kind, f"media_{replied_msg_id}.{ext}", file_bytes)
                        delivered = True
                except Exception as exc_dl:
                    print("Reply media download also failed:", repr(exc_dl), flush=True)

            if delivered and existing:
                try:
                    await self.db.mark_media_backup_sent(int(existing["id"]))
                except Exception:
                    pass
            await self.db.consume_free_deleted(owner_id)

            print("Reply-revealed timer media", {
                "replied_msg_id": replied_msg_id,
                "kind": kind,
                "owner_id": owner_id,
                "delivered": delivered,
            }, flush=True)
        except Exception as exc:
            print("handle_reply_reveals_timer_media failed:", repr(exc), {
                "replied_msg_id": replied_msg_id,
                "kind": kind,
            }, flush=True)

    async def handle_business_message(self, msg: dict[str, Any]) -> None:
        cached = await self.db.cache_business_message(msg)
        if cached:
            await self.cache_media_file_bytes_from_message(cached, msg)
            try:
                refreshed_cached = await self.db.find_cached_message(
                    str(cached.get("business_connection_id")),
                    int(cached.get("chat_id")),
                    int(cached.get("message_id")),
                )
                if refreshed_cached:
                    cached = refreshed_cached
            except Exception as exc:
                print("Refresh cached after media bytes failed:", repr(exc), flush=True)

            # Timer media must be shown immediately when possible. We only do this
            # for likely timer photo/video/video_note, not for normal voice/doc/audio.
            await self.maybe_send_timer_media_candidate_immediately(cached, msg)

            # Optional experimental mode: forward every incoming media. Default OFF.
            if os.getenv("INSTANT_MEDIA_BACKUP_ALL", "false").lower() in {"1", "true", "yes", "on"}:
                await self.maybe_send_instant_media_backup(cached, msg)
            else:
                await self.maybe_send_disappearing_media_immediately(cached, msg)

        # Reply-based timer media extraction: when owner replies to a contact's
        # captionless photo/video/video_note, grab it from reply_to_message.
        # This is the mechanism used to capture view-once media reliably.
        if msg.get("reply_to_message"):
            await self.handle_reply_reveals_timer_media(msg, cached)

        if not cached or not cached.get("owner_tg_id"):
            return
        owner_id = int(cached["owner_tg_id"])
        body = cached.get("text") or cached.get("caption") or ""
        if not body:
            return
        lang = await self.user_lang(owner_id)
        matches = await self.db.match_keywords(owner_id, body)
        if matches:
            title = "🔎 <b>Keyword alert</b>" if lang == "en" else "🔎 <b>Оповещение по ключевому слову</b>" if lang == "ru" else "🔎 <b>Сповіщення за ключовим словом</b>"
            await self.safe_send(owner_id, f"{title}: {', '.join(e(m) for m in matches)}\n\n<b>{tr(lang, 'chat')}:</b> {e(cached.get('chat_title') or cached.get('chat_id'))}\n<b>{tr(lang, 'from')}:</b> {e(cached.get('sender_name') or cached.get('sender_id'))}\n\n{e(body)[:2500]}")
        if looks_suspicious(body):
            title = "⚠️ <b>Possible scam/phishing</b>" if lang == "en" else "⚠️ <b>Возможный скам/фишинг</b>" if lang == "ru" else "⚠️ <b>Можливий скам/фішинг</b>"
            await self.safe_send(owner_id, f"{title}\n\n<b>{tr(lang, 'chat')}:</b> {e(cached.get('chat_title') or cached.get('chat_id'))}\n<b>{tr(lang, 'from')}:</b> {e(cached.get('sender_name') or cached.get('sender_id'))}\n\n{e(body)[:2500]}")

    async def handle_edited_business_message(self, msg: dict[str, Any]) -> None:
        bc_id = msg.get("business_connection_id")
        chat = msg.get("chat") or {}
        if not bc_id or not chat.get("id") or not msg.get("message_id"):
            return
        old = await self.db.find_cached_message(bc_id, int(chat["id"]), int(msg["message_id"]))
        new = await self.db.cache_edited_message(msg)
        if new:
            await self.cache_media_file_bytes_from_message(new, msg)
        if not new or not new.get("owner_tg_id"):
            return
        owner_id = int(new["owner_tg_id"])
        if self.only_live_location_changed(old, new, msg):
            return
        if old and (old.get("text") or old.get("caption")) == (new.get("text") or new.get("caption")):
            return
        # Owner opted out of seeing their OWN edits: skip messages they sent.
        if new.get("sender_id") and int(new["sender_id"]) == owner_id and not await self.db.get_track_own_messages(owner_id):
            return
        if not await self.db.active_subscription(owner_id):
            return
        lang = await self.user_lang(owner_id)
        old_text = (old.get("text") or old.get("caption")) if old else "—"
        new_text = new.get("text") or new.get("caption") or "—"
        before_label = "Before" if lang == "en" else "Было" if lang == "ru" else "Було"
        after_label = "After" if lang == "en" else "Стало" if lang == "ru" else "Стало"
        text = (
            f"{tr(lang, 'edited_title')}\n\n"
            f"💬 <b>{tr(lang, 'chat')}:</b> {e(new.get('chat_title') or new.get('chat_id'))}\n"
            f"👤 <b>{tr(lang, 'from')}:</b> {e(new.get('sender_name') or new.get('sender_id'))}\n\n"
            f"⬅️ <b>{before_label}:</b>\n{e(old_text)[:1500]}\n\n"
            f"➡️ <b>{after_label}:</b>\n{e(new_text)[:1500]}"
        )
        await self.safe_send(owner_id, text)

    async def handle_deleted_business_messages(self, data: dict[str, Any]) -> None:
        bc_id = data.get("business_connection_id")
        chat = data.get("chat") or {}
        chat_id = int(chat.get("id")) if chat.get("id") else None
        if not bc_id or chat_id is None:
            return
        conn = await self.db.get_business_connection(bc_id)
        owner_id = int(conn["owner_tg_id"]) if conn and conn.get("owner_tg_id") else None
        if not owner_id:
            return
        lang = await self.user_lang(owner_id)
        # Access gate: deleted-message delivery requires an active subscription
        # or the free trial. Locked users get a (rate-limited) subscribe prompt.
        if not await self.db.active_subscription(owner_id):
            await self.maybe_nudge_subscription(owner_id, lang)
            return
        for message_id in data.get("message_ids") or []:
            try:
                cached = await self.db.find_cached_message(bc_id, chat_id, int(message_id))
            except Exception as exc:
                print("Deleted message exact lookup failed:", repr(exc), {"message_id": message_id, "chat_id": chat_id}, flush=True)
                cached = None
            if not cached:
                # Timer/self-destruct media sometimes comes with one message_id in
                # business_message and another one in deleted_business_messages.
                # If exact lookup fails, match the most recent cached media from
                # the same chat instead of losing the saved photo/video.
                try:
                    cached = await self.db.find_recent_cached_media_for_deleted_event(bc_id, owner_id, chat_id, int(message_id), minutes=int(os.getenv('TIMER_MEDIA_MATCH_MINUTES', '2')))
                except Exception as exc:
                    print("Timer media fallback matcher failed:", repr(exc), {"deleted_message_id": int(message_id), "chat_id": chat_id}, flush=True)
                    cached = None
                if cached:
                    print("Timer media fallback matched cached media", {
                        "deleted_message_id": int(message_id),
                        "cached_id": cached.get("id"),
                        "cached_message_id": cached.get("message_id"),
                        "content_type": cached.get("content_type"),
                        "has_bytes": cached.get("file_bytes") is not None,
                        "has_file_id": bool(cached.get("file_id")),
                    }, flush=True)
                else:
                    # Last resort: Telegram sometimes reports timer deletion under
                    # another chat/internal id. If we already saved media for this
                    # owner recently, use it instead of showing unknown_deleted.
                    try:
                        cached = await self.db.find_recent_cached_media_for_owner(
                            owner_id,
                            minutes=int(os.getenv("TIMER_MEDIA_OWNER_MATCH_MINUTES", "2")),
                        )
                    except Exception as exc:
                        print("Owner-wide timer media matcher failed:", repr(exc), flush=True)
                        cached = None

                    if cached:
                        print("Owner-wide timer media fallback matched cached media", {
                            "deleted_message_id": int(message_id),
                            "cached_id": cached.get("id"),
                            "cached_message_id": cached.get("message_id"),
                            "content_type": cached.get("content_type"),
                            "chat_id": cached.get("chat_id"),
                            "has_bytes": cached.get("file_bytes") is not None,
                            "has_file_id": bool(cached.get("file_id")),
                        }, flush=True)
                    else:
                        # Ultra fallback: Telegram timer media sometimes deletes with
                        # totally different internal ids. Search ANY recent cached
                        # media for this owner, not only this chat/bc/message.
                        try:
                            cached = await self.db.find_any_recent_cached_media_for_owner(
                                owner_id,
                                seconds=int(os.getenv("TIMER_MEDIA_ULTRA_MATCH_SECONDS", "90")),
                            )
                        except Exception as exc:
                            print("Ultra timer media matcher failed:", repr(exc), flush=True)
                            cached = None

                        if cached:
                            print("Ultra timer media fallback matched cached media", {
                                "deleted_message_id": int(message_id),
                                "cached_id": cached.get("id"),
                                "cached_message_id": cached.get("message_id"),
                                "cached_chat_id": cached.get("chat_id"),
                                "content_type": cached.get("content_type"),
                                "has_bytes": cached.get("file_bytes") is not None,
                                "has_file_id": bool(cached.get("file_id")),
                            }, flush=True)
                        else:
                            print("Deleted event has no cached match", {
                                "deleted_message_id": int(message_id),
                                "bc_id": bc_id,
                                "chat_id": chat_id,
                                "reason": "no fresh cached media within strict timer window",
                            }, flush=True)
                            await self.db.mark_deleted_event(bc_id, owner_id, chat_id, int(message_id), None, data, False)
                            if await self.db.can_use_free_deleted(owner_id):
                                chat_label = e(chat.get("title") or str(chat_id))
                                msg = (
                                    f"{tr(lang, 'deleted_title')}\n\n"
                                    f"💬 <b>{tr(lang, 'chat')}:</b> {chat_label}\n\n"
                                    f"{tr(lang, 'unknown_deleted')}"
                                )
                                await self.safe_send(owner_id, msg)
                                await self.db.consume_free_deleted(owner_id)
                            continue
            # Owner opted out of seeing their OWN deletions: record but don't forward.
            if cached.get("sender_id") and int(cached["sender_id"]) == owner_id and not await self.db.get_track_own_messages(owner_id):
                await self.db.mark_deleted_event(bc_id, owner_id, chat_id, int(message_id), int(cached["id"]), data, False)
                continue
            print("Deleted event cached match", {
                "deleted_message_id": int(message_id),
                "cached_id": cached.get("id"),
                "cached_message_id": cached.get("message_id"),
                "content_type": cached.get("content_type"),
                "has_bytes": cached.get("file_bytes") is not None,
                "has_file_id": bool(cached.get("file_id")),
            }, flush=True)
            can_send = await self.db.can_use_free_deleted(owner_id)
            if not can_send:
                await self.db.mark_deleted_event(bc_id, owner_id, chat_id, int(message_id), int(cached["id"]), data, False)
                await self.safe_send(owner_id, tr(lang, "free_limit"), plans_keyboard(lang, await self.db.plans(True)))
                continue
            delivered = await self.send_deleted_message(owner_id, lang, cached)
            print("Deleted/timer event delivery result", {
                "deleted_message_id": int(message_id),
                "cached_id": cached.get("id"),
                "content_type": cached.get("content_type"),
                "has_bytes": cached.get("file_bytes") is not None,
                "has_file_id": bool(cached.get("file_id")),
                "delivered": delivered,
            }, flush=True)
            await self.db.mark_deleted_event(bc_id, owner_id, chat_id, int(message_id), int(cached["id"]), data, delivered)
            if delivered:
                await self.db.consume_free_deleted(owner_id)

    async def send_deleted_message(self, owner_id: int, lang: str, cached: dict[str, Any]) -> bool:
        kind = cached.get("content_type") or "unknown"
        body = cached.get("text") or cached.get("caption") or ""
        saved_label = "Saved copy" if lang == "en" else "Сохранённая копия" if lang == "ru" else "Збережена копія"
        service_note = (
            "This copy was saved before the message was deleted."
            if lang == "en"
            else "Эта копия была сохранена до удаления сообщения."
            if lang == "ru"
            else "Цю копію було збережено до видалення повідомлення."
        )
        # The notification structure (title + Chat/From/Time labels) is editable
        # via /edit on msg_alert_deleted_<lang>; the dynamic data goes in
        # {placeholders}. {saved} is the (varying) saved content section.
        if body:
            saved = f"🧾 {saved_label}:\n{str(body)[:3000]}\n\n{service_note}"
        elif cached.get("file_id") or cached.get("file_bytes") is not None:
            kind_label = media_kind_label(kind, lang)
            if lang == "en":
                saved = f"🔥 Deleted/disappearing media saved\n📎 Type: {kind_label}\nI will send the saved file below. If Telegram blocks voice as a voice message, I will send it as MP3 or ZIP."
            elif lang == "ru":
                saved = f"🔥 Сохранено удалённое/исчезающее медиа\n📎 Тип: {kind_label}\nЯ отправлю сохранённый файл ниже. Если Telegram заблокирует голосовое как voice, отправлю MP3 или ZIP."
            else:
                saved = f"🔥 Збережено видалене/зникаюче медіа\n📎 Тип: {kind_label}\nЯ надішлю збережений файл нижче. Якщо Telegram заблокує голосове як voice, надішлю MP3 або ZIP."
        else:
            saved = strip_visible_html_tags(tr(lang, "unknown_deleted"))
        try:
            await self.editable_send(owner_id, "alert_deleted", lang, {
                "chat": cached.get("chat_title") or cached.get("chat_id"),
                "author": cached.get("sender_name") or cached.get("sender_id"),
                "time": dt(cached.get("created_at")),
                "saved": saved,
            })
            if (cached.get("file_id") or cached.get("file_bytes") is not None) and kind in {"photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker"}:
                await self.send_deleted_media_copy(owner_id, lang, kind, str(cached.get("file_id") or ""), cached.get("caption"), cached)
            return True
        except Exception as exc:
            print("Send deleted message error:", repr(exc))
            return False

    async def send_media_alert(self, owner_id: int, lang: str, key: str, chat: Any, author: Any, kind: str) -> None:
        """Send an editable media-saved notification (timer/disappearing/backup).

        Structure (title, Chat/From/Type labels, note) is editable via /edit on
        msg_<key>_<lang>; the chat/author/type are filled into {placeholders}.
        """
        await self.editable_send(owner_id, key, lang, {
            "chat": chat,
            "author": author,
            "type": media_kind_label(kind, lang),
        })

    def convert_audio_to_mp3(self, content: bytes, source_suffix: str = ".ogg") -> bytes | None:
        """Convert Telegram voice/audio bytes to MP3 using ffmpeg.

        Returns None if ffmpeg is unavailable or conversion fails.
        """
        in_path = None
        out_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=source_suffix) as src:
                src.write(content)
                in_path = src.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as dst:
                out_path = dst.name

            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    in_path,
                    "-vn",
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "128k",
                    out_path,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            if result.returncode != 0:
                print("ffmpeg mp3 conversion failed:", result.stderr.decode("utf-8", "ignore")[:1000])
                return None
            with open(out_path, "rb") as f:
                return f.read()
        except Exception as exc:
            print("convert_audio_to_mp3 failed:", repr(exc))
            return None
        finally:
            for path in (in_path, out_path):
                if path:
                    try:
                        os.unlink(path)
                    except Exception:
                        pass



    async def send_saved_bytes_as_best_effort(
        self,
        owner_id: int,
        lang: str,
        kind: str,
        filename: str,
        content: bytes,
        caption: str | None = None,
    ) -> bool:
        """Try hard to deliver saved media bytes.

        For timer media the saved bytes are the most reliable source. Telegram can
        reject one method (sendPhoto/sendVideo/sendAudio), so we also try sending
        the same bytes as a regular document before falling back.
        """
        # Voice is special because users can forbid voice messages. MP3/ZIP already
        # gives much better delivery.
        if kind == "voice":
            mp3_bytes = self.convert_audio_to_mp3(content, ".ogg")
            if mp3_bytes:
                for send_kind, fname in (("audio", "vertuu_deleted_voice.mp3"), ("document", "vertuu_deleted_voice.mp3")):
                    try:
                        await self.bot.send_media_bytes(owner_id, send_kind, fname, mp3_bytes, "🎙 Видалене голосове / Deleted voice")
                        print("Saved voice delivered", {"mode": send_kind, "bytes": len(mp3_bytes)}, flush=True)
                        return True
                    except Exception as exc:
                        print("Saved voice MP3 send failed:", repr(exc), {"mode": send_kind}, flush=True)

            try:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr(filename if filename.endswith(".ogg") else "vertuu_deleted_voice.ogg", content)
                await self.bot.send_media_bytes(owner_id, "document", "vertuu_deleted_voice.zip", zip_buffer.getvalue(), "🎙 Голосове збережено в ZIP / Voice saved in ZIP")
                print("Saved voice delivered", {"mode": "zip", "bytes": len(content)}, flush=True)
                return True
            except Exception as exc:
                print("Saved voice ZIP send failed:", repr(exc), flush=True)
                return False

        # video_note can be hard to re-send as a note; document/video are safer.
        modes: list[tuple[str, str]] = []
        if kind in {"photo", "video", "animation", "audio", "document"}:
            modes.append((kind, filename))
        if kind == "video_note":
            modes.append(("video", filename if filename.endswith(".mp4") else "vertuu_deleted_video_note.mp4"))
        modes.append(("document", filename or f"vertuu_deleted_{kind}.bin"))

        tried = set()
        for send_kind, fname in modes:
            key = (send_kind, fname)
            if key in tried:
                continue
            tried.add(key)
            try:
                await self.bot.send_media_bytes(owner_id, send_kind, fname, content, caption)
                print("Saved media bytes delivered", {"kind": kind, "mode": send_kind, "bytes": len(content), "filename": fname}, flush=True)
                return True
            except Exception as exc:
                print("Saved media bytes send mode failed:", repr(exc), {"kind": kind, "mode": send_kind, "filename": fname}, flush=True)
        return False


    async def send_deleted_media_copy(self, owner_id: int, lang: str, kind: str, file_id: str, caption: str | None = None, cached: dict[str, Any] | None = None) -> bool:
        """Send deleted media as reliably as possible.

        First we try to reuse Telegram file_id. For some Business media, especially
        voice/video notes/stickers, Telegram can reject direct re-sending after the
        original message is deleted. Then we try getFile → download → upload again.
        """
        cached_bytes: bytes | None = None
        if cached and cached.get("file_bytes") is not None:
            raw_bytes = cached.get("file_bytes")
            try:
                cached_bytes = bytes(raw_bytes)
            except Exception:
                cached_bytes = raw_bytes  # type: ignore[assignment]

        if cached_bytes:
            filename = str(cached.get("file_name") or f"vertuu_deleted_{kind}.bin")
            if await self.send_saved_bytes_as_best_effort(owner_id, lang, kind, filename, cached_bytes, caption):
                return True
            print(f"All saved-bytes delivery modes failed kind={kind}; trying file_id fallback", flush=True)

        try:
            await self.bot.send_cached_media(owner_id, kind, file_id, caption)
            return True
        except Exception as exc:
            print(f"Send cached media by file_id failed kind={kind}:", repr(exc))

        # Some users/chats forbid voice messages from bots. In that case Telegram
        # returns VOICE_MESSAGES_FORBIDDEN. We must not retry sendVoice again:
        # upload it as a regular document so the user can still download/listen.
        #
        # video_note and stickers are also safer as documents when re-uploading
        # from deleted Business messages.
        if kind == "voice":
            fallback_kind = "document"
        elif kind in {"photo", "video", "animation", "audio", "document"}:
            fallback_kind = kind
        else:
            fallback_kind = "document"

        ext_map = {
            "photo": "jpg",
            "video": "mp4",
            "animation": "gif",
            "audio": "mp3",
            "voice": "ogg",
            "video_note": "mp4",
            "sticker": "webp",
            "document": "bin",
        }
        filename = f"vertuu_deleted_{kind}.{ext_map.get(kind, 'bin')}"
        try:
            file_info = await self.bot.get_file(file_id)
            file_path = str(file_info.get("file_path") or "")
            if not file_path:
                raise RuntimeError("Telegram returned empty file_path")
            content = await self.bot.download_file(file_path)

            try:
                await self.bot.send_media_bytes(owner_id, fallback_kind, filename, content, caption)
                return True
            except Exception as exc:
                print(f"Direct binary upload fallback failed kind={kind}:", repr(exc))

            # Better UX for deleted voice: convert .ogg/opus to MP3 and send it as
            # a normal Telegram audio track. This is much easier than opening ZIP.
            if kind in {"voice", "audio", "video_note"}:
                mp3_bytes = self.convert_audio_to_mp3(content, "." + ext_map.get(kind, "ogg"))
                if mp3_bytes:
                    mp3_caption = (
                        "🎙 Deleted voice converted to MP3."
                        if lang == "en"
                        else "🎙 Удалённое голосовое конвертировано в MP3."
                        if lang == "ru"
                        else "🎙 Видалене голосове конвертовано в MP3."
                    )
                    try:
                        await self.bot.send_media_bytes(owner_id, "audio", f"vertuu_deleted_{kind}.mp3", mp3_bytes, mp3_caption)
                        return True
                    except Exception as exc:
                        print(f"MP3 audio upload fallback failed kind={kind}:", repr(exc))
                    try:
                        await self.bot.send_media_bytes(owner_id, "document", f"vertuu_deleted_{kind}.mp3", mp3_bytes, mp3_caption)
                        return True
                    except Exception as exc:
                        print(f"MP3 document upload fallback failed kind={kind}:", repr(exc))

                # Last resort: wrap the original file into ZIP. Telegram no longer
                # treats it as a voice message, and the user still receives the file.
                zip_buffer = io.BytesIO()
                inner_name = filename
                with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr(inner_name, content)
                zip_bytes = zip_buffer.getvalue()
                zip_caption = (
                    "🎙 Deleted voice saved inside ZIP. Open the archive and play the .ogg file."
                    if lang == "en"
                    else "🎙 Удалённое голосовое сохранено внутри ZIP. Открой архив и прослушай .ogg файл."
                    if lang == "ru"
                    else "🎙 Видалене голосове збережено всередині ZIP. Відкрий архів і прослухай .ogg файл."
                )
                await self.bot.send_media_bytes(owner_id, "document", f"{filename}.zip", zip_bytes, zip_caption)
                return True

            raise RuntimeError("All non-zip media fallbacks failed")
        except Exception as exc:
            print(f"Download/re-upload media fallback failed kind={kind}:", repr(exc))
            note = (
                "⚠️ I detected deleted media, but Telegram did not allow me to resend the saved file."
                if lang == "en"
                else "⚠️ Я увидел удалённое медиа, но Telegram не разрешил переслать сохранённый файл."
                if lang == "ru"
                else "⚠️ Я побачив видалене медіа, але Telegram не дозволив переслати збережений файл."
            )
            await self.safe_send(owner_id, note)
            return False

    async def safe_send(self, chat_id: int, text: str, keyboard: dict[str, Any] | None = None) -> None:
        try:
            await self.bot.send_message(chat_id, text, keyboard)
        except Exception as exc:
            print("safe_send error:", repr(exc))

    async def handle_admin_command(self, admin_id: int, text: str, lang: str) -> None:
        if not await self.db.is_admin(admin_id):
            await self.bot.send_message(admin_id, tr(lang, "not_admin"))
            return
        parts = text.split(maxsplit=3)
        cmd = parts[0]
        try:
            if cmd == "/stats":
                await self.show_admin_stats(admin_id, lang)
            elif cmd == "/plans_admin":
                await self.show_admin_plans(admin_id, lang)
            elif cmd == "/methods_admin":
                await self.show_admin_methods(admin_id, lang)
            elif cmd == "/grant" and len(parts) >= 3:
                tg_id = int(parts[1])
                days = int(parts[2])
                until = await self.db.grant_subscription(tg_id, days)
                await self.bot.send_message(admin_id, f"✅ Granted {days} days to <code>{tg_id}</code>. Until {dt(until)}")
                user_lang = await self.user_lang(tg_id)
                await self.safe_send(tg_id, tr(user_lang, "crypto_paid", date=dt(until)), main_menu(user_lang, False))
            elif cmd == "/revoke" and len(parts) >= 2:
                tg_id = int(parts[1])
                await self.db.revoke_subscription(tg_id)
                await self.bot.send_message(admin_id, f"✅ Revoked subscription for <code>{tg_id}</code>.")
            elif cmd == "/approve" and len(parts) >= 2:
                payment_id = int(parts[1])
                paid = await self.db.mark_payment_paid(payment_id, admin_id=admin_id)
                if not paid:
                    await self.bot.send_message(admin_id, "Payment not found")
                    return
                await self.bot.send_message(admin_id, f"✅ Approved payment {payment_id}. Until {dt(paid.get('paid_until'))}")
                user_id = int(paid["user_id"])
                user_lang = await self.user_lang(user_id)
                await self.safe_send(user_id, tr(user_lang, "crypto_paid", date=dt(paid.get("paid_until"))), main_menu(user_lang, False))
            elif cmd == "/reject" and len(parts) >= 2:
                payment_id = int(parts[1])
                await self.db.mark_payment_status(payment_id, "rejected", admin_id=admin_id)
                await self.bot.send_message(admin_id, f"❌ Rejected payment {payment_id}.")
            elif cmd == "/set_plan" and len(parts) >= 4:
                sub = text.split(maxsplit=3)
                plan_id = int(sub[1])
                field = sub[2]
                value = sub[3]
                await self.db.update_plan_field(plan_id, field, value)
                await self.bot.send_message(admin_id, f"✅ Plan {plan_id}: {e(field)} updated.")
            elif cmd == "/set_method" and len(parts) >= 4:
                sub = text.split(maxsplit=3)
                code = sub[1]
                field = sub[2]
                value = sub[3]
                await self.db.update_method_field(code, field, value)
                await self.bot.send_message(admin_id, f"✅ Method {e(code)}: {e(field)} updated.")
            elif cmd == "/set_setting" and len(parts) >= 3:
                sub = text.split(maxsplit=2)
                key = sub[1]
                raw_value = sub[2]
                try:
                    value: Any = json.loads(raw_value)
                except Exception:
                    value = raw_value
                await self.db.set_setting(key, value)
                await self.bot.send_message(admin_id, f"✅ Setting {e(key)} updated.")
            elif cmd == "/ref_bonus" and len(parts) >= 3:
                target = int(parts[1])
                days = int(parts[2])
                until = await self.db.add_manual_referral_bonus(target, days, admin_id=admin_id, note="command")
                await self.bot.send_message(admin_id, f"✅ Нараховано {days} дн. користувачу <code>{target}</code>. Доступ до {dt(until)}")
            elif cmd in {"/broadcast", "/broadcasts"}:
                await self.show_broadcasts(admin_id, lang)
            elif cmd == "/broadcast_now":
                sent = await self.broadcast_send_now()
                await self.bot.send_message(admin_id, f"🚀 Розіслано в {sent} чат(ів).")
            elif cmd == "/broadcast_add" and len(parts) >= 2:
                chat_id = int(parts[1])
                await self.db.add_broadcast_chat(chat_id, added_by=admin_id)
                await self.bot.send_message(admin_id, f"✅ Чат {chat_id} додано до розсилок.")
            elif cmd == "/cashout":
                await self.show_cashout_confirm(admin_id, lang)
            elif cmd == "/cleanup":
                deleted = await self.db.cleanup_old_messages()
                await self.bot.send_message(admin_id, f"🧹 Cleanup done. Deleted rows: {deleted}")
            elif cmd == "/reset_connect":
                for lang_code in ("uk", "ru", "en"):
                    await self.db.delete_template(f"connect_{lang_code}")
                await self.bot.send_message(admin_id, "✅ Connect templates cleared. The 'How to connect' button now shows text-only instructions with the current bot username.")
            elif cmd == "/reset_plans":
                for lang_code in ("uk", "ru", "en"):
                    await self.db.delete_template(f"plans_{lang_code}")
                await self.bot.send_message(admin_id, "✅ Plans templates cleared. The subscription screen now shows the default layout.")
            else:
                await self.show_admin(admin_id, lang)
        except Exception as exc:
            await self.bot.send_message(admin_id, f"❌ Admin command error:\n<code>{e(repr(exc))}</code>")
