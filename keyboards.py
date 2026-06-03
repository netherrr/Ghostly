from __future__ import annotations

from typing import Any

from i18n import btn


def inline(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": text, "callback_data": data} for text, data in row] for row in rows]}


def main_menu(lang: str, is_admin: bool = False) -> dict[str, Any]:
    rows = [
        [(btn(lang, "status"), "status"), (btn(lang, "plans"), "plans")],
        [(btn(lang, "connect"), "connect"), (btn(lang, "last_deleted"), "last_deleted")],
        [(btn(lang, "keywords"), "keywords"), (btn(lang, "privacy"), "privacy")],
        [(btn(lang, "referrals"), "referrals"), (btn(lang, "lang"), "lang")],
    ]
    if is_admin:
        rows.append([(btn(lang, "admin"), "admin")])
    return inline(rows)


def lang_keyboard() -> dict[str, Any]:
    return inline([
        [("🇺🇦 Українська", "setlang:uk")],
        [("🏳️ Русский", "setlang:ru")],
        [("🇬🇧 English", "setlang:en")],
    ])


def back_menu(lang: str, to: str = "menu") -> dict[str, Any]:
    return inline([[(btn(lang, "back"), to)]])


def plans_keyboard(lang: str, plans: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = []
    for plan in plans:
        name = plan.get(f"name_{lang}") or plan.get("name_en") or plan["code"]
        rows.append([(f"{btn(lang, 'buy')} {name} — ${plan['price_usd']}", f"buy:{plan['id']}")])
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


def keywords_keyboard(lang: str, words: list[str]) -> dict[str, Any]:
    rows: list[list[tuple[str, str]]] = [[(btn(lang, "add_keyword"), "kw_add")]]
    if words:
        rows.append([(btn(lang, "delete_keyword"), "kw_delete_menu")])
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
    share_text = "Invite friends to Ghostly Guard and earn 30% from their purchases." if lang == "en" else "Приглашай друзей в Ghostly Guard и получай 30% от их покупок." if lang == "ru" else "Запрошуй друзів у Ghostly Guard і отримуй 30% з їхніх покупок."
    share_url = "https://t.me/share/url?url=" + link + "&text=" + share_text.replace(" ", "%20")
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
        [(btn(lang, "admin_referrals"), "admin_referrals")],
        [(btn(lang, "back"), "menu")],
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
        [("💵 Ціна / Price", f"adm_set_plan:{plan_id}:price_usd"), ("📆 Дні / Days", f"adm_set_plan:{plan_id}:duration_days")],
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
        [("🎁 Free delete limit", "adm_set_setting:free_deleted_limit_per_day")],
        [("🤝 Referral percent", "adm_set_setting:referral_percent")],
        [("🧹 Free retention hours", "adm_set_setting:free_retention_hours")],
        [("🗄 Paid retention days", "adm_set_setting:message_retention_days")],
        [("🎬 Завантажити відео-інструкцію", "adm_upload_connect_video")],
        [("🔗 URL відео-інструкції", "adm_set_setting:connect_video_url")],
        [("🧽 Cleanup now", "admin_cleanup")],
        [(btn(lang, "back"), "admin")],
    ])
