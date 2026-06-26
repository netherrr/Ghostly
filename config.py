from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from typing import List


def _split_ids(value: str | None) -> list[int]:
    if not value:
        return []
    ids: list[int] = []
    for part in value.replace(";", ",").split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return ids


def _single_id(value: str | None) -> int | None:
    """Parse one chat/user id (groups are negative, e.g. -1001234567890)."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    admin_ids: list[int]
    admin_chat_id: int | None
    webhook_base_url: str | None
    webhook_secret: str
    port: int
    app_name: str
    default_lang: str
    crypto_pay_token: str | None
    crypto_pay_api_url: str
    message_retention_days: int
    free_retention_hours: int
    free_deleted_limit_per_day: int
    public_terms_url: str | None
    support_username: str | None
    bot_username: str | None

    @property
    def webhook_path(self) -> str:
        return f"/telegram/webhook/{self.webhook_secret}"

    @property
    def webhook_url(self) -> str | None:
        if not self.webhook_base_url:
            return None
        return self.webhook_base_url.rstrip("/") + self.webhook_path


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    webhook_secret = os.getenv("WEBHOOK_SECRET", "").strip() or secrets.token_urlsafe(32)
    return Settings(
        bot_token=token,
        database_url=database_url,
        admin_ids=_split_ids(os.getenv("ADMIN_IDS")),
        admin_chat_id=_single_id(os.getenv("ADMIN_CHAT_ID")),
        webhook_base_url=os.getenv("WEBHOOK_BASE_URL", "").strip() or None,
        webhook_secret=webhook_secret,
        port=int(os.getenv("PORT", "8080")),
        app_name=os.getenv("APP_NAME", "VERTUU SPY BOT").strip() or "VERTUU SPY BOT",
        default_lang=os.getenv("DEFAULT_LANG", "ru").strip() or "ru",
        crypto_pay_token=os.getenv("CRYPTO_PAY_TOKEN", "").strip() or None,
        crypto_pay_api_url=os.getenv("CRYPTO_PAY_API_URL", "https://pay.crypt.bot/api").rstrip("/"),
        message_retention_days=int(os.getenv("MESSAGE_RETENTION_DAYS", "30")),
        free_retention_hours=int(os.getenv("FREE_RETENTION_HOURS", "24")),
        free_deleted_limit_per_day=int(os.getenv("FREE_DELETED_LIMIT_PER_DAY", "10")),
        public_terms_url=os.getenv("PUBLIC_TERMS_URL", "").strip() or None,
        support_username=os.getenv("SUPPORT_USERNAME", "").strip() or None,
        bot_username=os.getenv("BOT_USERNAME", "").strip().lstrip("@") or None,
    )
