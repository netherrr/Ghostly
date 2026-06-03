from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from bot_api import BotAPI
from config import Settings
from crypto_pay import CryptoPayClient
from db import Database, display_name
from i18n import btn, tr
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
    cancel_keyboard,
    crypto_payment_keyboard,
    keyword_delete_keyboard,
    keywords_keyboard,
    lang_keyboard,
    main_menu,
    manual_payment_keyboard,
    payment_methods_keyboard,
    plans_keyboard,
)


def e(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def dt(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        return value
    try:
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(value)


def plan_name(plan: dict[str, Any] | None, lang: str) -> str:
    if not plan:
        return "—"
    return str(plan.get(f"name_{lang}") or plan.get("name_en") or plan.get("code"))


def plan_features(plan: dict[str, Any], lang: str) -> str:
    return str(plan.get(f"features_{lang}") or plan.get("features_en") or "")


def method_title(method: dict[str, Any], lang: str) -> str:
    return str(method.get(f"title_{lang}") or method.get("title_en") or method.get("code"))


def method_instructions(method: dict[str, Any], lang: str) -> str:
    return str(method.get(f"instructions_{lang}") or method.get("instructions_en") or "")


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


def state_prompt(lang: str, state: str, payload: dict[str, Any]) -> str:
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
    return "Надішли значення або натисни Скасувати."


class BotHandlers:
    def __init__(self, settings: Settings, db: Database, bot: BotAPI, crypto: CryptoPayClient):
        self.settings = settings
        self.db = db
        self.bot = bot
        self.crypto = crypto

    async def handle_update(self, update: dict[str, Any]) -> None:
        try:
            if "message" in update:
                await self.handle_message(update["message"])
            elif "callback_query" in update:
                await self.handle_callback(update["callback_query"])
            elif "business_connection" in update:
                await self.handle_business_connection(update["business_connection"])
            elif "business_message" in update:
                await self.handle_business_message(update["business_message"])
            elif "edited_business_message" in update:
                await self.handle_edited_business_message(update["edited_business_message"])
            elif "deleted_business_messages" in update:
                await self.handle_deleted_business_messages(update["deleted_business_messages"])
        except Exception as exc:
            print("Update handling error:", repr(exc), json.dumps(update, ensure_ascii=False)[:2000])

    async def user_lang(self, tg_id: int) -> str:
        user = await self.db.get_user(tg_id)
        return str(user.get("lang") if user else self.settings.default_lang)

    async def handle_message(self, msg: dict[str, Any]) -> None:
        user_obj = msg.get("from") or {}
        user = await self.db.upsert_user(user_obj)
        if not user:
            return
        tg_id = int(user["tg_id"])
        lang = str(user.get("lang") or self.settings.default_lang)
        text = (msg.get("text") or "").strip()
        is_admin = await self.db.is_admin(tg_id)

        if text.startswith("/"):
            await self.db.clear_state(tg_id)

        state = await self.db.get_state(tg_id)
        if state and text and not text.startswith("/"):
            await self.handle_state_input(tg_id, lang, text, state, is_admin)
            return

        if text.startswith("/start"):
            await self.show_start(tg_id, lang, is_admin)
        elif text in {"/language", "/lang"}:
            await self.bot.send_message(tg_id, tr(lang, "choose_lang"), lang_keyboard())
        elif text in {"/status"}:
            await self.show_status(tg_id, lang)
        elif text in {"/plans"}:
            await self.show_plans(tg_id, lang)
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
        elif text.startswith("/") and is_admin:
            await self.handle_admin_command(tg_id, text, lang)
        elif text.startswith("/"):
            await self.bot.send_message(tg_id, tr(lang, "unknown_command"), main_menu(lang, is_admin))
        else:
            await self.bot.send_message(tg_id, tr(lang, "menu"), main_menu(lang, is_admin))

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

            if not is_admin:
                await self.db.clear_state(tg_id)
                await self.bot.send_message(tg_id, tr(lang, "not_admin"))
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

            await self.db.clear_state(tg_id)
            await self.bot.send_message(tg_id, tr(lang, "menu"), main_menu(lang, is_admin))
        except Exception as exc:
            await self.bot.send_message(tg_id, f"❌ Помилка:\n<code>{e(repr(exc))}</code>", cancel_keyboard(lang, "admin" if is_admin else "menu"))

    async def show_start(self, tg_id: int, lang: str, is_admin: bool) -> None:
        await self.bot.send_message(tg_id, tr(lang, "start", app=e(self.settings.app_name)), main_menu(lang, is_admin))

    async def show_status(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        user = await self.db.get_user(tg_id)
        async with self.db._pool().acquire() as con:
            saved = await con.fetchval("SELECT COUNT(*) FROM cached_messages WHERE owner_tg_id=$1", tg_id) or 0
            deleted = await con.fetchval("SELECT COUNT(*) FROM deleted_events WHERE owner_tg_id=$1", tg_id) or 0
        sub_until = user.get("subscription_until") if user else None
        sub_status = tr(lang, "sub_active", date=dt(sub_until)) if sub_until and sub_until > datetime.now(timezone.utc) else tr(lang, "sub_free")
        has_business = await self.db.user_has_business(tg_id)
        business_status = tr(lang, "business_on") if has_business else tr(lang, "business_off")
        hint = tr(lang, "status_hint_ok") if has_business else tr(lang, "status_hint_connect")
        text = tr(lang, "status", sub_status=e(sub_status), business_status=e(business_status), saved=saved, deleted=deleted, hint=e(hint))
        await self._send_or_edit(tg_id, text, back_menu(lang), edit)

    async def show_plans(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        plans = await self.db.plans(active_only=True)
        lines = [tr(lang, "plans_title")]
        for p in plans:
            lines.append(tr(lang, "plan_line", name=e(plan_name(p, lang)), price=e(p["price_usd"]), days=p["duration_days"], features=e(plan_features(p, lang)).replace("\n", "\n")))
        await self._send_or_edit(tg_id, "\n\n".join(lines), plans_keyboard(lang, plans), edit)

    async def show_admin(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        if not await self.db.is_admin(tg_id):
            await self.bot.send_message(tg_id, tr(lang, "not_admin"))
            return
        await self._send_or_edit(tg_id, tr(lang, "admin"), admin_menu(lang), edit)

    async def show_keywords(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        words = await self.db.list_keywords(tg_id)
        title = "🔎 <b>Keyword alerts</b>" if lang == "en" else "🔎 <b>Оповещения по ключевым словам</b>" if lang == "ru" else "🔎 <b>Сповіщення за ключовими словами</b>"
        empty = "No keywords yet." if lang == "en" else "Ключевых слов пока нет." if lang == "ru" else "Ключових слів поки немає."
        body = "\n".join([f"• <code>{e(w)}</code>" for w in words]) if words else empty
        hint = "Press buttons below to add or remove keywords." if lang == "en" else "Нажимай кнопки ниже, чтобы добавлять или удалять слова." if lang == "ru" else "Натискай кнопки нижче, щоб додавати або видаляти слова."
        await self._send_or_edit(tg_id, f"{title}\n\n{body}\n\n{hint}", keywords_keyboard(lang, words), edit)

    async def show_keyword_delete_menu(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        words = await self.db.list_keywords(tg_id)
        text = "🗑 Choose keyword to delete:" if lang == "en" else "🗑 Выбери слово для удаления:" if lang == "ru" else "🗑 Обери слово для видалення:"
        await self._send_or_edit(tg_id, text, keyword_delete_keyboard(lang, words), edit)

    async def show_last_deleted(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        async with self.db._pool().acquire() as con:
            rows = await con.fetch(
                """SELECT cm.chat_title, cm.sender_name, cm.text, cm.caption, cm.content_type, de.created_at
                   FROM deleted_events de
                   LEFT JOIN cached_messages cm ON cm.id=de.cached_message_id
                   WHERE de.owner_tg_id=$1
                   ORDER BY de.created_at DESC LIMIT 10""",
                tg_id,
            )
        rows = [dict(r) for r in rows]
        if not rows:
            msg = "No deleted messages yet." if lang == "en" else "Удалённых сообщений пока нет." if lang == "ru" else "Видалених повідомлень поки немає."
            await self._send_or_edit(tg_id, msg, back_menu(lang), edit)
            return
        lines = ["👻 <b>Last deleted</b>" if lang == "en" else "👻 <b>Останні видалені</b>" if lang == "uk" else "👻 <b>Последние удалённые</b>"]
        for r in rows:
            body = r.get("text") or r.get("caption") or f"[{r.get('content_type') or 'unknown'}]"
            lines.append(f"<b>{e(r.get('chat_title') or '')}</b> — {e(r.get('sender_name') or '')}\n{e(body)[:500]}\n<code>{dt(r.get('created_at'))}</code>")
        await self._send_or_edit(tg_id, "\n\n".join(lines), back_menu(lang), edit)

    async def _send_or_edit(self, tg_id: int, text: str, keyboard: dict[str, Any] | None = None, edit: tuple[int, int] | None = None) -> None:
        if edit:
            chat_id, message_id = edit
            try:
                await self.bot.edit_message_text(chat_id, message_id, text, keyboard)
                return
            except Exception:
                pass
        await self.bot.send_message(tg_id, text, keyboard)

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
            elif target.startswith("admin_plan:"):
                await self.show_admin_plan(tg_id, lang, int(target.split(":", 1)[1]), edit)
            elif target.startswith("admin_method:"):
                await self.show_admin_method(tg_id, lang, target.split(":", 1)[1], edit)
            else:
                await self._send_or_edit(tg_id, tr(lang, "menu"), main_menu(lang, await self.db.is_admin(tg_id)), edit)
            return

        if data == "menu":
            await self._send_or_edit(tg_id, tr(lang, "menu"), main_menu(lang, await self.db.is_admin(tg_id)), edit)
        elif data == "status":
            await self.show_status(tg_id, lang, edit)
        elif data == "plans":
            await self.show_plans(tg_id, lang, edit)
        elif data == "connect":
            await self._send_or_edit(tg_id, tr(lang, "connect"), back_menu(lang), edit)
        elif data == "privacy":
            await self._send_or_edit(tg_id, tr(lang, "privacy"), back_menu(lang), edit)
        elif data == "lang":
            await self._send_or_edit(tg_id, tr(lang, "choose_lang"), lang_keyboard(), edit)
        elif data == "last_deleted":
            await self.show_last_deleted(tg_id, lang, edit)
        elif data == "keywords":
            await self.show_keywords(tg_id, lang, edit)
        elif data == "kw_add":
            await self.db.set_state(tg_id, "keyword_add", {})
            await self._send_or_edit(tg_id, state_prompt(lang, "keyword_add", {}), cancel_keyboard(lang, "keywords"), edit)
        elif data == "kw_delete_menu":
            await self.show_keyword_delete_menu(tg_id, lang, edit)
        elif data.startswith("kw_del:"):
            words = await self.db.list_keywords(tg_id)
            idx = int(data.split(":", 1)[1])
            if 0 <= idx < len(words):
                await self.db.delete_keyword(tg_id, words[idx])
            await self.show_keywords(tg_id, lang, edit)
        elif data.startswith("setlang:"):
            new_lang = data.split(":", 1)[1]
            await self.db.set_lang(tg_id, new_lang)
            await self._send_or_edit(tg_id, tr(new_lang, "menu"), main_menu(new_lang, await self.db.is_admin(tg_id)), edit)
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
        elif data.startswith("admin_") or data.startswith("adm_"):
            await self.handle_admin_callback(tg_id, lang, data, edit)

    async def callback_buy(self, tg_id: int, lang: str, plan_id: int, edit: tuple[int, int] | None) -> None:
        plan = await self.db.get_plan(plan_id)
        if not plan or not plan.get("is_active"):
            await self.show_plans(tg_id, lang, edit)
            return
        methods = await self.db.payment_methods(active_only=True)
        text = tr(lang, "choose_payment", plan=e(plan_name(plan, lang)), price=e(plan["price_usd"]))
        await self._send_or_edit(tg_id, text, payment_methods_keyboard(lang, plan_id, methods), edit)

    async def callback_pay(self, tg_id: int, lang: str, plan_id: int, method_code: str, edit: tuple[int, int] | None) -> None:
        plan = await self.db.get_plan(plan_id)
        method = await self.db.get_payment_method(method_code)
        if not plan or not method or not method.get("is_active"):
            await self.show_plans(tg_id, lang, edit)
            return
        amount = Decimal(str(plan["price_usd"]))
        if method_code == "cryptobot":
            try:
                invoice = await self.crypto.create_invoice(amount, f"{self.settings.app_name}: {plan_name(plan, 'en')}", f"user:{tg_id}:plan:{plan_id}")
                external_id = str(invoice.get("invoice_id"))
                url = invoice.get("bot_invoice_url") or invoice.get("mini_app_invoice_url") or invoice.get("web_app_invoice_url") or invoice.get("pay_url")
                payment = await self.db.create_payment(tg_id, plan_id, "cryptobot", amount, external_id=external_id, invoice_url=url, raw=invoice)
                text = tr(lang, "payment_crypto_created", amount=e(amount), url=e(url or ""))
                await self._send_or_edit(tg_id, text, crypto_payment_keyboard(lang, int(payment["id"]), url or "https://t.me/CryptoBot"), edit)
            except Exception as exc:
                print("Crypto payment error:", repr(exc))
                await self.bot.send_message(tg_id, tr(lang, "payment_error"), back_menu(lang))
            return

        payment = await self.db.create_payment(tg_id, plan_id, method_code, amount, raw={"method": method_code})
        text = tr(lang, "payment_manual", plan=e(plan_name(plan, lang)), amount=e(amount), instructions=method_instructions(method, lang))
        await self._send_or_edit(tg_id, text, manual_payment_keyboard(lang, int(payment["id"])), edit)

    async def callback_check_crypto(self, tg_id: int, lang: str, payment_id: int, edit: tuple[int, int] | None) -> None:
        payment = await self.db.get_payment(payment_id)
        if not payment or int(payment["user_id"]) != tg_id or payment["provider"] != "cryptobot":
            await self.bot.send_message(tg_id, tr(lang, "payment_error"))
            return
        if payment["status"] == "paid":
            await self.bot.send_message(tg_id, tr(lang, "crypto_paid", date=dt(payment.get("paid_until") or (await self.db.get_user(tg_id) or {}).get("subscription_until"))))
            return
        try:
            invoice = await self.crypto.get_invoice(str(payment["external_id"]))
            if invoice and invoice.get("status") == "paid":
                paid = await self.db.mark_payment_paid(payment_id, raw=invoice)
                await self.bot.send_message(tg_id, tr(lang, "crypto_paid", date=dt(paid.get("paid_until") if paid else None)), main_menu(lang, await self.db.is_admin(tg_id)))
            else:
                await self.bot.send_message(tg_id, tr(lang, "crypto_not_paid"), crypto_payment_keyboard(lang, payment_id, payment.get("invoice_url") or "https://t.me/CryptoBot"))
        except Exception as exc:
            print("Crypto check error:", repr(exc))
            await self.bot.send_message(tg_id, tr(lang, "payment_error"), back_menu(lang))

    async def callback_manual_paid(self, tg_id: int, lang: str, payment_id: int) -> None:
        payment = await self.db.get_payment(payment_id)
        if not payment or int(payment["user_id"]) != tg_id:
            await self.bot.send_message(tg_id, tr(lang, "payment_error"))
            return
        await self.bot.send_message(tg_id, tr(lang, "paid_wait_admin"), main_menu(lang, await self.db.is_admin(tg_id)))
        user = await self.db.get_user(tg_id)
        plan = await self.db.get_plan(int(payment["plan_id"])) if payment.get("plan_id") else None
        admin_text = (
            f"💳 <b>Manual payment request</b>\n\n"
            f"Payment ID: <code>{payment_id}</code>\n"
            f"User: <code>{tg_id}</code> @{e((user or {}).get('username') or '')}\n"
            f"Provider: <b>{e(payment['provider'])}</b>\n"
            f"Plan: <b>{e(plan_name(plan, 'en'))}</b>\n"
            f"Amount: <b>${e(payment['amount_usd'])}</b>"
        )
        for admin_id in self.settings.admin_ids:
            try:
                await self.bot.send_message(admin_id, admin_text, admin_payment_keyboard(payment_id))
            except Exception as exc:
                print("Notify admin error", admin_id, repr(exc))

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
        elif data.startswith("admin_payment:"):
            await self.show_admin_payment(tg_id, lang, int(data.split(":", 1)[1]), edit)
        elif data == "admin_plans":
            await self.show_admin_plans(tg_id, lang, edit)
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
        elif data == "admin_cleanup":
            deleted = await self.db.cleanup_old_messages()
            await self._send_or_edit(tg_id, f"🧹 Cleanup done. Deleted rows: <b>{deleted}</b>", admin_settings_keyboard(lang), edit)
        elif data == "admin_users":
            await self.show_admin_users(tg_id, lang, edit)

    async def show_admin_stats(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        s = await self.db.stats()
        await self._send_or_edit(tg_id, tr(lang, "stats", **{k: e(v) for k, v in s.items()}), back_menu(lang, "admin"), edit)

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
            f"Тривалість: <b>{e(p['duration_days'])} днів</b>\n"
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
        text = (
            f"💳 <b>Заявка #{p['id']}</b>\n\n"
            f"Статус: <b>{e(p['status'])}</b>\n"
            f"Користувач: <code>{e(p['user_id'])}</code> @{e((user or {}).get('username') or '')}\n"
            f"Тариф: <b>{e(plan_name(plan, 'uk'))}</b>\n"
            f"Метод: <b>{e(p['provider'])}</b>\n"
            f"Сума: <b>${e(p['amount_usd'])}</b>\n"
            f"Створено: <code>{dt(p.get('created_at'))}</code>"
        )
        await self._send_or_edit(tg_id, text, admin_single_payment_keyboard(lang, payment_id), edit)

    async def show_admin_settings(self, tg_id: int, lang: str, edit: tuple[int, int] | None = None) -> None:
        free_limit = await self.db.get_setting("free_deleted_limit_per_day", self.settings.free_deleted_limit_per_day)
        free_hours = await self.db.get_setting("free_retention_hours", self.settings.free_retention_hours)
        paid_days = await self.db.get_setting("message_retention_days", self.settings.message_retention_days)
        text = (
            "⚙️ <b>Налаштування</b>\n\n"
            f"🎁 Free deleted/day: <b>{e(free_limit)}</b>\n"
            f"🧹 Free retention hours: <b>{e(free_hours)}</b>\n"
            f"🗄 Paid retention days: <b>{e(paid_days)}</b>\n\n"
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

    async def handle_business_connection(self, data: dict[str, Any]) -> None:
        conn = await self.db.upsert_business_connection(data)
        if not conn or not conn.get("owner_tg_id"):
            return
        owner_id = int(conn["owner_tg_id"])
        lang = await self.user_lang(owner_id)
        try:
            await self.bot.send_message(owner_id, tr(lang, "business_connected" if conn.get("is_enabled") else "business_disabled"), main_menu(lang, await self.db.is_admin(owner_id)))
        except Exception as exc:
            print("Business connection notify error:", repr(exc))

    async def handle_business_message(self, msg: dict[str, Any]) -> None:
        cached = await self.db.cache_business_message(msg)
        if not cached or not cached.get("owner_tg_id"):
            return
        owner_id = int(cached["owner_tg_id"])
        body = cached.get("text") or cached.get("caption") or ""
        if not body:
            return
        if not await self.db.active_subscription(owner_id):
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
        if not new or not new.get("owner_tg_id"):
            return
        owner_id = int(new["owner_tg_id"])
        if old and (old.get("text") or old.get("caption")) == (new.get("text") or new.get("caption")):
            return
        if not await self.db.active_subscription(owner_id):
            return
        lang = await self.user_lang(owner_id)
        old_text = (old.get("text") or old.get("caption")) if old else "—"
        new_text = new.get("text") or new.get("caption") or "—"
        text = (
            f"{tr(lang, 'edited_title')}\n\n"
            f"<b>{tr(lang, 'chat')}:</b> {e(new.get('chat_title') or new.get('chat_id'))}\n"
            f"<b>{tr(lang, 'from')}:</b> {e(new.get('sender_name') or new.get('sender_id'))}\n\n"
            f"<b>Before:</b>\n{e(old_text)[:1500]}\n\n"
            f"<b>After:</b>\n{e(new_text)[:1500]}"
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
        for message_id in data.get("message_ids") or []:
            cached = await self.db.find_cached_message(bc_id, chat_id, int(message_id))
            if not cached:
                await self.db.mark_deleted_event(bc_id, owner_id, chat_id, int(message_id), None, data, False)
                if await self.db.can_use_free_deleted(owner_id):
                    await self.safe_send(owner_id, tr(lang, "unknown_deleted"))
                    await self.db.consume_free_deleted(owner_id)
                continue
            can_send = await self.db.can_use_free_deleted(owner_id)
            if not can_send:
                await self.db.mark_deleted_event(bc_id, owner_id, chat_id, int(message_id), int(cached["id"]), data, False)
                await self.safe_send(owner_id, tr(lang, "free_limit"), plans_keyboard(lang, await self.db.plans(True)))
                continue
            delivered = await self.send_deleted_message(owner_id, lang, cached)
            await self.db.mark_deleted_event(bc_id, owner_id, chat_id, int(message_id), int(cached["id"]), data, delivered)
            if delivered:
                await self.db.consume_free_deleted(owner_id)

    async def send_deleted_message(self, owner_id: int, lang: str, cached: dict[str, Any]) -> bool:
        kind = cached.get("content_type") or "unknown"
        body = cached.get("text") or cached.get("caption") or ""
        label = tr(lang, "text") if cached.get("text") else tr(lang, "caption")
        text = (
            f"{tr(lang, 'deleted_title')}\n\n"
            f"<b>{tr(lang, 'chat')}:</b> {e(cached.get('chat_title') or cached.get('chat_id'))}\n"
            f"<b>{tr(lang, 'from')}:</b> {e(cached.get('sender_name') or cached.get('sender_id'))}\n"
            f"<b>ID:</b> <code>{e(cached.get('message_id'))}</code>\n"
        )
        if body:
            text += f"\n<b>{label}:</b>\n{e(body)[:3000]}"
        elif cached.get("file_id"):
            text += "\n" + tr(lang, "media_saved", kind=e(kind))
        else:
            text += "\n" + tr(lang, "unknown_deleted")
        try:
            await self.bot.send_message(owner_id, text)
            if cached.get("file_id") and kind in {"photo", "video", "animation", "document", "audio", "voice", "video_note", "sticker"}:
                try:
                    await self.bot.send_cached_media(owner_id, kind, cached["file_id"], cached.get("caption"))
                except Exception as exc:
                    print("Send cached media error:", repr(exc))
            return True
        except Exception as exc:
            print("Send deleted message error:", repr(exc))
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
            elif cmd == "/cleanup":
                deleted = await self.db.cleanup_old_messages()
                await self.bot.send_message(admin_id, f"🧹 Cleanup done. Deleted rows: {deleted}")
            else:
                await self.show_admin(admin_id, lang)
        except Exception as exc:
            await self.bot.send_message(admin_id, f"❌ Admin command error:\n<code>{e(repr(exc))}</code>")
