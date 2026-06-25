from __future__ import annotations

from typing import Any
from urllib.parse import quote

from i18n import btn


def inline(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": text, "callback_data": data} for text, data in row] for row in rows]}


def support_button_text(lang: str) -> str:
    return {
        "uk": "⭐ Підтримати проект",
        "ru": "⭐ Поддержать проект",
        "en": "⭐ Support project",
    }.get(lang, "⭐ Support project")


def main_menu(lang: str, is_admin: bool = False) -> dict[str, Any]:
    # Connect is the primary action — full-width and first so new users reach
    # the connection flow in one tap. The old Status block was removed to keep
    # the home screen clean (access/days are shown on the subscription screen).
    rows = [
        [(btn(lang, "connect"), "connect")],
        [(btn(lang, "plans"), "plans"), (btn(lang, "last_deleted"), "last_deleted")],
        [(btn(lang, "keywords"), "keywords"), (btn(lang, "privacy"), "privacy")],
        [(btn(lang, "referrals"), "referrals"), (btn(lang, "lang"), "lang")],
        [(support_button_text(lang), "support")],
    ]
    if is_admin:
        rows.append([(btn(lang, "admin"), "admin")])
    return inline(rows)


def support_keyboard(lang: str) -> dict[str, Any]:
    custom = {
        "uk": "✍️ Ввести свою кількість",
        "ru": "✍️ Ввести своё количество",
        "en": "✍️ Enter custom amount",
    }.get(lang, "✍️ Enter custom amount")
    return inline([
        [("⭐ 50", "support_amount:50"), ("⭐ 100", "support_amount:100")],
        [("⭐ 250", "support_amount:250"), ("⭐ 500", "support_amount:500")],
        [("⭐ 1000", "support_amount:1000")],
        [(custom, "support_custom")],
        [(btn(lang, "back"), "menu")],
    ])


def lang_keyboard() -> dict[str, Any]:
    return inline([
        [("🇺🇦 Українська", "setlang:uk")],
        [("🏳️ Русский", "setlang:ru")],
        [("🇬🇧 English", "setlang:en")],
    ])


def back_menu(lang: str, to: str = "menu") -> dict[str, Any]:
    return inline([[(btn(lang, "back"), to)]])


def disappearing_guide_button_text(lang: str) -> str:
    return {
        "uk": "👻 Як дивитись зникаючі повідомлення",
        "ru": "👻 Как смотреть исчезающие сообщения",
        "en": "👻 How to view disappearing messages",
    }.get(lang, "👻 How to view disappearing messages")


def last_deleted_keyboard(lang: str) -> dict[str, Any]:
    return inline([
        [(disappearing_guide_button_text(lang), "disappearing_guide")],
        [(btn(lang, "back"), "menu")],
    ])


def connect_keyboard(lang: str) -> dict[str, Any]:
    # tg://settings/edit opens the user's profile/settings editor — the closest
    # point to Telegram Business → Chatbots, where the bot is added (verified to
    # work in the Telegram iOS app). There is no public deep link straight to the
    # Chatbots screen, so this is the best available shortcut; the instruction
    # text guides the last taps.
    open_label = {
        "uk": "🔌 Підключити",
        "ru": "🔌 Подключить",
        "en": "🔌 Connect",
    }.get(lang, "🔌 Connect")
    return {
        "inline_keyboard": [
            [{"text": open_label, "url": "tg://settings/edit"}],
            [{"text": btn(lang, "back"), "callback_data": "menu"}],
        ]
    }


def _plan_stars(plan: dict[str, Any]) -> int | None:
    raw = plan.get("price_stars")
    try:
        if raw is not None and str(raw).strip() not in {"", "0", "None", "null"}:
            return int(raw)
    except Exception:
        pass
    return None


def plans_keyboard(lang: str, plans: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = []
    for plan in plans:
        name = plan.get(f"name_{lang}") or plan.get("name_en") or plan["code"]
        stars = _plan_stars(plan)
        price = f"${plan['price_usd']}"
        label = f"{btn(lang, 'buy')} {name} — {price}"
        if stars:
            label += f" ({stars}⭐️)"
        rows.append([(label, f"buy:{plan['id']}")])
    rows.append([(btn(lang, "back"), "menu")])
    return inline(rows)


def payment_methods_keyboard(lang: str, plan_id: int, methods: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = []
    for method in methods:
        title = method.get(f"title_{lang}") or method.get("title_en") or method["code"]
        rows.append([(title, f"pay:{plan_id}:{method['code']}")])
    rows.append([(btn(lang, "back"), "plans")])
    return inline(rows)


def crypto_payment_keyboard(lang: str, payment_id: int, url: str) -> dict[str, Any]:
    open_text = "💸 Open invoice" if lang == "en" else "💸 Відкрити рахунок" if lang == "uk" else "💸 Открыть счёт"
    return {
        "inline_keyboard": [
            [{"text": open_text, "url": url}],
            [{"text": btn(lang, "check_payment"), "callback_data": f"check:{payment_id}"}],
            [{"text": btn(lang, "back"), "callback_data": "plans"}],
        ]
    }


def manual_payment_keyboard(lang: str, payment_id: int) -> dict[str, Any]:
    return inline([[(btn(lang, "i_paid"), f"manual_paid:{payment_id}")], [(btn(lang, "back"), "plans")]])


def admin_payment_keyboard(payment_id: int) -> dict[str, Any]:
    return inline([[ ("✅ Approve", f"admin_approve:{payment_id}"), ("❌ Reject", f"admin_reject:{payment_id}") ]])


def keywords_keyboard(lang: str, words: list[str], monitored: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = [[(btn(lang, "add_keyword"), "kw_add")]]
    if words:
        rows.append([(btn(lang, "delete_keyword"), "kw_delete_menu")])
    for c in (monitored or [])[:10]:
        title = (c.get("title") or str(c.get("chat_id")))[:30]
        rows.append([(f"🛑 {title}", f"kwchat_del:{c['chat_id']}")])
    rows.append([(btn(lang, "back"), "menu")])
    return inline(rows)


def keyword_delete_keyboard(lang: str, words: list[str]) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = []
    for idx, word in enumerate(words[:30]):
        label = f"❌ {word[:36]}" if len(word) <= 36 else f"❌ {word[:33]}..."
        rows.append([(label, f"kw_del:{idx}")])
    rows.append([(btn(lang, "back"), "keywords")])
    return inline(rows)


def cancel_keyboard(lang: str, to: str = "menu") -> dict[str, Any]:
    return inline([[(btn(lang, "cancel"), f"cancel:{to}")]])




def referral_keyboard(lang: str, bot_username: str, user_id: int) -> dict[str, Any]:
    link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    share_text = (
        "VERTUU SPY BOT saves deleted messages and disappearing media. Join via my link:"
        if lang == "en"
        else "VERTUU SPY BOT сохраняет удалённые сообщения и исчезающие медиа. Заходи по моей ссылке:"
        if lang == "ru"
        else "VERTUU SPY BOT зберігає видалені повідомлення та зникаючі медіа. Заходь за моїм посиланням:"
    )
    # Telegram share URL must be fully URL-encoded. Otherwise Cyrillic text and
    # symbols like % may be sent to chats as ugly %20/%D0... garbage.
    share_url = "https://t.me/share/url?url=" + quote(link, safe="") + "&text=" + quote(share_text, safe="")
    return {
        "inline_keyboard": [
            [{"text": "📤 Share link" if lang == "en" else "📤 Поделиться ссылкой" if lang == "ru" else "📤 Поділитися посиланням", "url": share_url}],
            [{"text": btn(lang, "back"), "callback_data": "menu"}],
        ]
    }

def admin_menu(lang: str) -> dict[str, Any]:
    return inline([
        [(btn(lang, "admin_stats"), "admin_stats"), (btn(lang, "admin_pending"), "admin_pending")],
        [(btn(lang, "admin_plans"), "admin_plans"), (btn(lang, "admin_methods"), "admin_methods")],
        [(btn(lang, "admin_grant"), "admin_grant"), (btn(lang, "admin_revoke"), "admin_revoke")],
        [(btn(lang, "admin_settings"), "admin_settings"), (btn(lang, "admin_users"), "admin_users")],
        [(btn(lang, "admin_referrals"), "admin_referrals"), (btn(lang, "admin_broadcast"), "admin_broadcast")],
        [(btn(lang, "back"), "menu")],
    ])


def broadcast_menu_keyboard(lang: str, chats: list[dict[str, Any]], has_template: bool) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = []
    tpl_label = "📝 Шаблон ✅" if has_template else "📝 Задати шаблон"
    rows.append([(tpl_label, "bc_template"), ("➕ Додати чат", "bc_add")])
    for c in chats:
        status = "✅" if c.get("is_active") else "⛔️"
        title = (c.get("title") or str(c.get("chat_id")))[:24]
        mins = max(1, int(c.get("interval_seconds") or 1800) // 60)
        rows.append([(f"{status} {title} · {mins}хв", f"bc_chat:{c['chat_id']}")])
    rows.append([("🚀 Розіслати зараз", "bc_send_now")])
    rows.append([(btn(lang, "back"), "admin")])
    return inline(rows)


def broadcast_chat_keyboard(lang: str, chat_id: int, is_active: bool) -> dict[str, Any]:
    return inline([
        [("⏱ 5 хв", f"bc_int:{chat_id}:300"), ("⏱ 15 хв", f"bc_int:{chat_id}:900")],
        [("⏱ 30 хв", f"bc_int:{chat_id}:1800"), ("⏱ 1 год", f"bc_int:{chat_id}:3600")],
        [("⏱ 3 год", f"bc_int:{chat_id}:10800"), ("✍️ Свій інтервал", f"bc_int_custom:{chat_id}")],
        [("⏸ Пауза" if is_active else "▶️ Увімкнути", f"bc_toggle:{chat_id}")],
        [("🗑 Видалити чат", f"bc_remove:{chat_id}")],
        [(btn(lang, "back"), "admin_broadcast")],
    ])


def admin_plans_keyboard(lang: str, plans: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = [[("➕ Новий тариф / New plan", "adm_create_plan")]]
    for p in plans:
        status = "✅" if p.get("is_active") else "⛔️"
        rows.append([(f"{status} #{p['id']} {p.get('code')} — ${p.get('price_usd')}", f"admin_plan:{p['id']}")])
    rows.append([(btn(lang, "back"), "admin")])
    return inline(rows)


def admin_plan_keyboard(lang: str, plan_id: int, is_active: bool) -> dict[str, Any]:
    return inline([
        [("💵 USD Price", f"adm_set_plan:{plan_id}:price_usd"), ("₴ UAH Price", f"adm_set_plan:{plan_id}:price_uah")],
        [("⭐ Stars Price", f"adm_set_plan:{plan_id}:price_stars")],
        [("📆 Дні / Days", f"adm_set_plan:{plan_id}:duration_days")],
        [("↕️ Позиція", f"adm_set_plan:{plan_id}:position")],
        [("🇺🇦 Назва", f"adm_set_plan:{plan_id}:name_uk"), ("🏳️ Название", f"adm_set_plan:{plan_id}:name_ru"), ("🇬🇧 Name", f"adm_set_plan:{plan_id}:name_en")],
        [("🇺🇦 Фічі", f"adm_set_plan:{plan_id}:features_uk"), ("🏳️ Фичи", f"adm_set_plan:{plan_id}:features_ru"), ("🇬🇧 Features", f"adm_set_plan:{plan_id}:features_en")],
        [("✅ Увімкнено" if is_active else "⛔️ Вимкнено", f"adm_toggle_plan:{plan_id}")],
        [(btn(lang, "back"), "admin_plans")],
    ])


def admin_methods_keyboard(lang: str, methods: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = []
    for m in methods:
        status = "✅" if m.get("is_active") else "⛔️"
        rows.append([(f"{status} {m.get('code')}", f"admin_method:{m.get('code')}")])
    rows.append([(btn(lang, "back"), "admin")])
    return inline(rows)


def admin_method_keyboard(lang: str, code: str, is_active: bool) -> dict[str, Any]:
    return inline([
        [("🇺🇦 Назва", f"adm_set_method:{code}:title_uk"), ("🏳️ Название", f"adm_set_method:{code}:title_ru"), ("🇬🇧 Title", f"adm_set_method:{code}:title_en")],
        [("🇺🇦 Реквізити", f"adm_set_method:{code}:instructions_uk"), ("🏳️ Реквизиты", f"adm_set_method:{code}:instructions_ru")],
        [("🇬🇧 Instructions", f"adm_set_method:{code}:instructions_en"), ("↕️ Позиція", f"adm_set_method:{code}:position")],
        [("✅ Увімкнено" if is_active else "⛔️ Вимкнено", f"adm_toggle_method:{code}")],
        [(btn(lang, "back"), "admin_methods")],
    ])


def admin_pending_keyboard(lang: str, payments: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = []
    for p in payments:
        rows.append([(f"#{p['id']} @{p.get('username') or p.get('user_id')} ${p.get('amount_usd')}", f"admin_payment:{p['id']}")])
    rows.append([(btn(lang, "back"), "admin")])
    return inline(rows)


def admin_single_payment_keyboard(lang: str, payment_id: int) -> dict[str, Any]:
    return inline([
        [("📎 Доказ оплати", f"admin_proof:{payment_id}")],
        [("✅ Підтвердити", f"admin_approve:{payment_id}"), ("❌ Відхилити", f"admin_reject:{payment_id}")],
        [(btn(lang, "back"), "admin_pending")],
    ])


def admin_settings_keyboard(lang: str) -> dict[str, Any]:
    return inline([
        [("🎁 Trial days", "adm_set_setting:trial_days"), ("🔒 Gating on/off", "adm_set_setting:access_gating_enabled")],
        [("🟢 Ref normal days", "adm_set_setting:ref_normal_days"), ("🔢 Ref normal limit", "adm_set_setting:ref_normal_limit")],
        [("💎 Ref premium days", "adm_set_setting:ref_premium_days")],
        [("₴ UAH/USD rate", "adm_set_setting:uah_rate"), ("🗄 Paid retention days", "adm_set_setting:message_retention_days")],
        [("🎬 Відео: підключення", "adm_upload_connect_video")],
        [("🔗 URL відео: підключення", "adm_set_setting:connect_video_url")],
        [("👻 Відео: зникаючі повідомлення", "adm_upload_guide_video")],
        [("🔗 URL відео: зникаючі", "adm_set_setting:guide_video_url")],
        [("🧽 Cleanup now", "admin_cleanup")],
        [(btn(lang, "back"), "admin")],
    ])
