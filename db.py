from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import asyncpg

from config import Settings


def decode_json(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self.settings.database_url, min_size=1, max_size=10)
        await self.migrate()
        await self.seed_defaults()

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    def _pool(self) -> asyncpg.Pool:
        if not self.pool:
            raise RuntimeError("Database pool is not initialized")
        return self.pool

    async def migrate(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS users (
            tg_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            lang TEXT NOT NULL DEFAULT 'uk',
            is_admin BOOLEAN NOT NULL DEFAULT FALSE,
            subscription_until TIMESTAMPTZ,
            free_deleted_today INT NOT NULL DEFAULT 0,
            free_deleted_reset_date DATE NOT NULL DEFAULT CURRENT_DATE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS plans (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            name_uk TEXT NOT NULL,
            name_ru TEXT NOT NULL,
            name_en TEXT NOT NULL,
            features_uk TEXT NOT NULL DEFAULT '',
            features_ru TEXT NOT NULL DEFAULT '',
            features_en TEXT NOT NULL DEFAULT '',
            price_usd NUMERIC(12,2) NOT NULL,
            duration_days INT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            position INT NOT NULL DEFAULT 100,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS payment_methods (
            code TEXT PRIMARY KEY,
            title_uk TEXT NOT NULL,
            title_ru TEXT NOT NULL,
            title_en TEXT NOT NULL,
            instructions_uk TEXT NOT NULL DEFAULT '',
            instructions_ru TEXT NOT NULL DEFAULT '',
            instructions_en TEXT NOT NULL DEFAULT '',
            details JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            position INT NOT NULL DEFAULT 100,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS payments (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(tg_id) ON DELETE SET NULL,
            plan_id INT REFERENCES plans(id) ON DELETE SET NULL,
            provider TEXT NOT NULL,
            amount_usd NUMERIC(12,2) NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            status TEXT NOT NULL DEFAULT 'pending',
            external_id TEXT,
            invoice_url TEXT,
            raw JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            paid_at TIMESTAMPTZ,
            admin_checked_by BIGINT,
            admin_note TEXT
        );

        CREATE TABLE IF NOT EXISTS business_connections (
            id TEXT PRIMARY KEY,
            owner_tg_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
            user_chat_id BIGINT,
            can_reply BOOLEAN NOT NULL DEFAULT FALSE,
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            raw JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS cached_messages (
            id BIGSERIAL PRIMARY KEY,
            business_connection_id TEXT REFERENCES business_connections(id) ON DELETE CASCADE,
            owner_tg_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
            chat_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            sender_id BIGINT,
            sender_name TEXT,
            chat_title TEXT,
            content_type TEXT NOT NULL DEFAULT 'unknown',
            text TEXT,
            caption TEXT,
            file_id TEXT,
            media_group_id TEXT,
            edited_versions JSONB NOT NULL DEFAULT '[]'::jsonb,
            raw JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ,
            UNIQUE (business_connection_id, chat_id, message_id)
        );

        CREATE TABLE IF NOT EXISTS deleted_events (
            id BIGSERIAL PRIMARY KEY,
            business_connection_id TEXT,
            owner_tg_id BIGINT,
            chat_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            cached_message_id BIGINT REFERENCES cached_messages(id) ON DELETE SET NULL,
            delivered BOOLEAN NOT NULL DEFAULT FALSE,
            raw JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS user_keywords (
            owner_tg_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
            keyword TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY(owner_tg_id, keyword)
        );

        CREATE TABLE IF NOT EXISTS user_states (
            user_id BIGINT PRIMARY KEY REFERENCES users(tg_id) ON DELETE CASCADE,
            state TEXT NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS admin_logs (
            id BIGSERIAL PRIMARY KEY,
            admin_tg_id BIGINT,
            action TEXT NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_cached_owner ON cached_messages(owner_tg_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_cached_lookup ON cached_messages(business_connection_id, chat_id, message_id);
        CREATE INDEX IF NOT EXISTS idx_deleted_owner ON deleted_events(owner_tg_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id, created_at DESC);
        """
        async with self._pool().acquire() as con:
            await con.execute(sql)

    async def seed_defaults(self) -> None:
        async with self._pool().acquire() as con:
            for admin_id in self.settings.admin_ids:
                await con.execute(
                    """
                    INSERT INTO users(tg_id, lang, is_admin)
                    VALUES($1, $2, TRUE)
                    ON CONFLICT(tg_id) DO UPDATE SET is_admin=TRUE, updated_at=NOW()
                    """,
                    admin_id,
                    self.settings.default_lang,
                )

            await con.execute(
                """
                INSERT INTO plans(code, name_uk, name_ru, name_en, features_uk, features_ru, features_en, price_usd, duration_days, position)
                VALUES
                ('basic_month', 'Basic', 'Basic', 'Basic',
                 '👻 Видалені повідомлення\n✏️ Історія редагувань\n🗄 Зберігання 7 днів',
                 '👻 Удалённые сообщения\n✏️ История правок\n🗄 Хранение 7 дней',
                 '👻 Deleted messages\n✏️ Edit history\n🗄 7-day storage',
                 1.99, 30, 10),
                ('pro_month', 'Pro', 'Pro', 'Pro',
                 '👻 Безліміт видалених\n✏️ Історія редагувань\n🔎 Ключові слова\n🗄 Зберігання 30 днів',
                 '👻 Безлимит удалённых\n✏️ История правок\n🔎 Ключевые слова\n🗄 Хранение 30 дней',
                 '👻 Unlimited deleted messages\n✏️ Edit history\n🔎 Keywords\n🗄 30-day storage',
                 3.99, 30, 20),
                ('pro_90', 'Pro 90 днів', 'Pro 90 дней', 'Pro 90 days',
                 '👻 Безліміт видалених\n✏️ Історія редагувань\n🗄 Зберігання 30 днів\n🔥 Вигідніше на 3 місяці',
                 '👻 Безлимит удалённых\n✏️ История правок\n🗄 Хранение 30 дней\n🔥 Выгоднее на 3 месяца',
                 '👻 Unlimited deleted messages\n✏️ Edit history\n🗄 30-day storage\n🔥 Better value for 3 months',
                 9.99, 90, 30)
                ON CONFLICT(code) DO NOTHING
                """
            )

            await con.execute(
                """
                INSERT INTO payment_methods(code, title_uk, title_ru, title_en, instructions_uk, instructions_ru, instructions_en, details, position, is_active)
                VALUES
                ('cryptobot', 'CryptoBot автоматично', 'CryptoBot автоматически', 'CryptoBot automatic',
                 'Натисни кнопку рахунку CryptoBot і оплати інвойс.',
                 'Нажми кнопку счёта CryptoBot и оплати инвойс.',
                 'Open the CryptoBot invoice and pay it.', '{}'::jsonb, 10, TRUE),
                ('ua_card', 'Українська картка', 'Украинская карта', 'Ukrainian card',
                 'Переказ на картку. Замінити реквізити можна командою /set_method ua_card instructions_uk ...',
                 'Перевод на карту. Реквизиты можно заменить командой /set_method ua_card instructions_ru ...',
                 'Card transfer. Replace payment details with /set_method ua_card instructions_en ...', '{}'::jsonb, 20, TRUE),
                ('usdt_trc20', 'USDT TRC20', 'USDT TRC20', 'USDT TRC20',
                 'Надішли USDT TRC20 на гаманець. Замінити реквізити: /set_method usdt_trc20 instructions_uk ...',
                 'Отправь USDT TRC20 на кошелёк. Реквизиты: /set_method usdt_trc20 instructions_ru ...',
                 'Send USDT TRC20 to the wallet. Edit details with /set_method usdt_trc20 instructions_en ...', '{}'::jsonb, 30, TRUE),
                ('usdt_bep20', 'USDT BEP20', 'USDT BEP20', 'USDT BEP20',
                 'Надішли USDT BEP20 на гаманець. Замінити реквізити: /set_method usdt_bep20 instructions_uk ...',
                 'Отправь USDT BEP20 на кошелёк. Реквизиты: /set_method usdt_bep20 instructions_ru ...',
                 'Send USDT BEP20 to the wallet. Edit details with /set_method usdt_bep20 instructions_en ...', '{}'::jsonb, 40, TRUE)
                ON CONFLICT(code) DO NOTHING
                """
            )

            defaults = {
                "support_username": self.settings.support_username or "",
                "free_deleted_limit_per_day": self.settings.free_deleted_limit_per_day,
                "free_retention_hours": self.settings.free_retention_hours,
                "message_retention_days": self.settings.message_retention_days,
                "connect_video_url": "",
                "connect_video_file_id": "",
                "connect_video_kind": "video",
            }
            for key, value in defaults.items():
                await con.execute(
                    """
                    INSERT INTO settings(key, value) VALUES($1, $2::jsonb)
                    ON CONFLICT(key) DO NOTHING
                    """,
                    key,
                    json.dumps(value),
                )

    async def upsert_user(self, user: dict[str, Any] | None, lang: str | None = None) -> dict[str, Any] | None:
        if not user or not user.get("id"):
            return None
        tg_id = int(user["id"])
        username = user.get("username")
        first_name = user.get("first_name")
        last_name = user.get("last_name")
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                INSERT INTO users(tg_id, username, first_name, last_name, lang, is_admin)
                VALUES($1, $2, $3, $4, COALESCE($5, $6), $7)
                ON CONFLICT(tg_id) DO UPDATE SET
                  username=EXCLUDED.username,
                  first_name=EXCLUDED.first_name,
                  last_name=EXCLUDED.last_name,
                  updated_at=NOW()
                RETURNING *
                """,
                tg_id,
                username,
                first_name,
                last_name,
                lang,
                self.settings.default_lang,
                tg_id in self.settings.admin_ids,
            )
            return dict(row)

    async def get_user(self, tg_id: int) -> dict[str, Any] | None:
        async with self._pool().acquire() as con:
            row = await con.fetchrow("SELECT * FROM users WHERE tg_id=$1", tg_id)
            return dict(row) if row else None

    async def set_lang(self, tg_id: int, lang: str) -> None:
        async with self._pool().acquire() as con:
            await con.execute("UPDATE users SET lang=$2, updated_at=NOW() WHERE tg_id=$1", tg_id, lang)

    async def is_admin(self, tg_id: int) -> bool:
        if tg_id in self.settings.admin_ids:
            return True
        row = await self.get_user(tg_id)
        return bool(row and row.get("is_admin"))

    async def grant_subscription(self, tg_id: int, days: int) -> datetime:
        now = datetime.now(timezone.utc)
        user = await self.get_user(tg_id)
        current = user.get("subscription_until") if user else None
        start = current if current and current > now else now
        until = start + timedelta(days=days)
        async with self._pool().acquire() as con:
            await con.execute(
                """
                INSERT INTO users(tg_id, lang, subscription_until)
                VALUES($1, $3, $2)
                ON CONFLICT(tg_id) DO UPDATE SET subscription_until=$2, updated_at=NOW()
                """,
                tg_id,
                until,
                self.settings.default_lang,
            )
        return until

    async def revoke_subscription(self, tg_id: int) -> None:
        async with self._pool().acquire() as con:
            await con.execute("UPDATE users SET subscription_until=NULL, updated_at=NOW() WHERE tg_id=$1", tg_id)

    async def active_subscription(self, tg_id: int) -> bool:
        row = await self.get_user(tg_id)
        return bool(row and row.get("subscription_until") and row["subscription_until"] > datetime.now(timezone.utc))

    async def plans(self, active_only: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM plans"
        if active_only:
            sql += " WHERE is_active=TRUE"
        sql += " ORDER BY position, price_usd"
        async with self._pool().acquire() as con:
            rows = await con.fetch(sql)
            return [dict(r) for r in rows]

    async def get_plan(self, plan_id: int) -> dict[str, Any] | None:
        async with self._pool().acquire() as con:
            row = await con.fetchrow("SELECT * FROM plans WHERE id=$1", plan_id)
            return dict(row) if row else None

    async def create_plan(self, code: str, price_usd: Decimal | float | str, duration_days: int, name: str | None = None) -> dict[str, Any]:
        clean_code = code.strip().lower().replace(" ", "_")[:64]
        title = (name or clean_code).strip()[:120]
        async with self._pool().acquire() as con:
            pos = await con.fetchval("SELECT COALESCE(MAX(position), 0) + 10 FROM plans")
            row = await con.fetchrow(
                """
                INSERT INTO plans(code, name_uk, name_ru, name_en, features_uk, features_ru, features_en, price_usd, duration_days, position, is_active)
                VALUES($1, $2, $2, $2, '', '', '', $3, $4, $5, TRUE)
                RETURNING *
                """,
                clean_code, title, Decimal(str(price_usd)), int(duration_days), int(pos or 100),
            )
            return dict(row)

    async def update_plan_field(self, plan_id: int, field: str, value: str) -> None:
        allowed = {"name_uk", "name_ru", "name_en", "features_uk", "features_ru", "features_en", "price_usd", "duration_days", "is_active", "position"}
        if field not in allowed:
            raise ValueError(f"Unsupported plan field: {field}")
        parsed: Any = value
        if field in {"price_usd"}:
            parsed = Decimal(value.replace(",", "."))
        elif field in {"duration_days", "position"}:
            parsed = int(value)
        elif field == "is_active":
            parsed = value.lower() in {"1", "true", "yes", "on", "актив", "да", "так"}
        async with self._pool().acquire() as con:
            await con.execute(f"UPDATE plans SET {field}=$2, updated_at=NOW() WHERE id=$1", plan_id, parsed)

    async def payment_methods(self, active_only: bool = True) -> list[dict[str, Any]]:
        sql = "SELECT * FROM payment_methods"
        if active_only:
            sql += " WHERE is_active=TRUE"
        sql += " ORDER BY position"
        async with self._pool().acquire() as con:
            return [dict(r) for r in await con.fetch(sql)]

    async def get_payment_method(self, code: str) -> dict[str, Any] | None:
        async with self._pool().acquire() as con:
            row = await con.fetchrow("SELECT * FROM payment_methods WHERE code=$1", code)
            return dict(row) if row else None

    async def update_method_field(self, code: str, field: str, value: str) -> None:
        allowed = {"title_uk", "title_ru", "title_en", "instructions_uk", "instructions_ru", "instructions_en", "details", "is_active", "position"}
        if field not in allowed:
            raise ValueError(f"Unsupported method field: {field}")
        parsed: Any = value
        cast = ""
        if field == "details":
            parsed = json.dumps(json.loads(value))
            cast = "::jsonb"
        elif field == "is_active":
            parsed = value.lower() in {"1", "true", "yes", "on", "актив", "да", "так"}
        elif field == "position":
            parsed = int(value)
        async with self._pool().acquire() as con:
            await con.execute(f"UPDATE payment_methods SET {field}=$2{cast}, updated_at=NOW() WHERE code=$1", code, parsed)

    async def create_payment(self, user_id: int, plan_id: int, provider: str, amount_usd: Decimal | float | str, currency: str = "USD", external_id: str | None = None, invoice_url: str | None = None, raw: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                INSERT INTO payments(user_id, plan_id, provider, amount_usd, currency, external_id, invoice_url, raw)
                VALUES($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                RETURNING *
                """,
                user_id,
                plan_id,
                provider,
                Decimal(str(amount_usd)),
                currency,
                external_id,
                invoice_url,
                json.dumps(raw or {}),
            )
            return dict(row)

    async def get_payment(self, payment_id: int) -> dict[str, Any] | None:
        async with self._pool().acquire() as con:
            row = await con.fetchrow("SELECT p.*, pl.duration_days FROM payments p LEFT JOIN plans pl ON p.plan_id=pl.id WHERE p.id=$1", payment_id)
            return dict(row) if row else None

    async def add_payment_proof(self, payment_id: int, proof: dict[str, Any]) -> dict[str, Any] | None:
        async with self._pool().acquire() as con:
            async with con.transaction():
                row = await con.fetchrow("SELECT * FROM payments WHERE id=$1 FOR UPDATE", payment_id)
                if not row:
                    return None
                data = dict(row)
                raw = decode_json(data.get("raw"), {}) or {}
                if not isinstance(raw, dict):
                    raw = {"raw": raw}
                raw["proof"] = proof
                updated = await con.fetchrow(
                    "UPDATE payments SET raw=$2::jsonb, status=CASE WHEN status='pending' THEN 'waiting_admin' ELSE status END WHERE id=$1 RETURNING *",
                    payment_id, json.dumps(raw),
                )
                return dict(updated) if updated else None

    async def mark_payment_paid(self, payment_id: int, admin_id: int | None = None, raw: dict[str, Any] | None = None) -> dict[str, Any] | None:
        async with self._pool().acquire() as con:
            async with con.transaction():
                row = await con.fetchrow("""
                    SELECT p.*, COALESCE((SELECT duration_days FROM plans pl WHERE pl.id=p.plan_id), 30) AS duration_days
                    FROM payments p
                    WHERE p.id=$1
                    FOR UPDATE
                    """, payment_id)
                if not row:
                    return None
                payment = dict(row)
                if payment["status"] == "paid":
                    return payment
                paid_raw = decode_json(payment.get("raw"), {}) or {}
                if not isinstance(paid_raw, dict):
                    paid_raw = {"raw": paid_raw}
                if raw:
                    paid_raw["paid_check"] = raw
                await con.execute(
                    """UPDATE payments SET status='paid', paid_at=NOW(), admin_checked_by=COALESCE($2, admin_checked_by), raw=$3::jsonb WHERE id=$1""",
                    payment_id,
                    admin_id,
                    json.dumps(paid_raw),
                )
                days = int(payment.get("duration_days") or 30)
                user_id = int(payment["user_id"])
                user = await con.fetchrow("SELECT subscription_until FROM users WHERE tg_id=$1 FOR UPDATE", user_id)
                now = datetime.now(timezone.utc)
                current = user["subscription_until"] if user else None
                start = current if current and current > now else now
                until = start + timedelta(days=days)
                await con.execute("UPDATE users SET subscription_until=$2, updated_at=NOW() WHERE tg_id=$1", user_id, until)
                payment["status"] = "paid"
                payment["paid_until"] = until
                return payment

    async def mark_payment_status(self, payment_id: int, status: str, admin_id: int | None = None, note: str | None = None) -> None:
        async with self._pool().acquire() as con:
            await con.execute(
                "UPDATE payments SET status=$2, admin_checked_by=$3, admin_note=$4 WHERE id=$1",
                payment_id,
                status,
                admin_id,
                note,
            )

    async def upsert_business_connection(self, data: dict[str, Any]) -> dict[str, Any] | None:
        bc_id = data.get("id")
        if not bc_id:
            return None
        user = data.get("user") or {}
        owner_id = int(user["id"]) if user.get("id") else None
        if owner_id:
            await self.upsert_user(user)
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                INSERT INTO business_connections(id, owner_tg_id, user_chat_id, can_reply, is_enabled, raw)
                VALUES($1, $2, $3, $4, $5, $6::jsonb)
                ON CONFLICT(id) DO UPDATE SET
                  owner_tg_id=EXCLUDED.owner_tg_id,
                  user_chat_id=EXCLUDED.user_chat_id,
                  can_reply=EXCLUDED.can_reply,
                  is_enabled=EXCLUDED.is_enabled,
                  raw=EXCLUDED.raw,
                  updated_at=NOW()
                RETURNING *
                """,
                bc_id,
                owner_id,
                data.get("user_chat_id"),
                bool(data.get("can_reply")),
                bool(data.get("is_enabled", True)),
                json.dumps(data),
            )
            return dict(row)

    async def get_business_connection(self, bc_id: str) -> dict[str, Any] | None:
        async with self._pool().acquire() as con:
            row = await con.fetchrow("SELECT * FROM business_connections WHERE id=$1", bc_id)
            return dict(row) if row else None

    async def user_has_business(self, tg_id: int) -> bool:
        async with self._pool().acquire() as con:
            return bool(await con.fetchval("SELECT EXISTS(SELECT 1 FROM business_connections WHERE owner_tg_id=$1 AND is_enabled=TRUE)", tg_id))

    async def cache_business_message(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        bc_id = msg.get("business_connection_id")
        if not bc_id:
            return None
        conn = await self.get_business_connection(bc_id)
        owner_id = int(conn["owner_tg_id"]) if conn and conn.get("owner_tg_id") else None
        chat = msg.get("chat") or {}
        sender = msg.get("from") or msg.get("sender_chat") or {}
        content_type, text, caption, file_id = extract_message_content(msg)
        sender_name = display_name(sender)
        chat_title = display_name(chat)
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                INSERT INTO cached_messages(
                    business_connection_id, owner_tg_id, chat_id, message_id, sender_id, sender_name, chat_title,
                    content_type, text, caption, file_id, media_group_id, raw
                ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::jsonb)
                ON CONFLICT(business_connection_id, chat_id, message_id) DO UPDATE SET
                    text=EXCLUDED.text,
                    caption=EXCLUDED.caption,
                    file_id=EXCLUDED.file_id,
                    content_type=EXCLUDED.content_type,
                    raw=EXCLUDED.raw,
                    updated_at=NOW()
                RETURNING *
                """,
                bc_id,
                owner_id,
                int(chat.get("id")),
                int(msg.get("message_id")),
                int(sender["id"]) if sender.get("id") else None,
                sender_name,
                chat_title,
                content_type,
                text,
                caption,
                file_id,
                msg.get("media_group_id"),
                json.dumps(msg),
            )
            return dict(row)

    async def cache_edited_message(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        bc_id = msg.get("business_connection_id")
        if not bc_id:
            return None
        chat_id = int((msg.get("chat") or {}).get("id"))
        message_id = int(msg.get("message_id"))
        content_type, text, caption, file_id = extract_message_content(msg)
        edit_entry = {
            "edited_at": datetime.now(timezone.utc).isoformat(),
            "content_type": content_type,
            "text": text,
            "caption": caption,
            "file_id": file_id,
        }
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                UPDATE cached_messages SET
                    edited_versions = edited_versions || $4::jsonb,
                    text=$5,
                    caption=$6,
                    file_id=COALESCE($7, file_id),
                    content_type=$8,
                    raw=$9::jsonb,
                    updated_at=NOW()
                WHERE business_connection_id=$1 AND chat_id=$2 AND message_id=$3
                RETURNING *
                """,
                bc_id,
                chat_id,
                message_id,
                json.dumps([edit_entry]),
                text,
                caption,
                file_id,
                content_type,
                json.dumps(msg),
            )
            if row:
                return dict(row)
        return await self.cache_business_message(msg)

    async def find_cached_message(self, bc_id: str, chat_id: int, message_id: int) -> dict[str, Any] | None:
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                "SELECT * FROM cached_messages WHERE business_connection_id=$1 AND chat_id=$2 AND message_id=$3",
                bc_id,
                chat_id,
                message_id,
            )
            return dict(row) if row else None

    async def mark_deleted_event(self, bc_id: str, owner_id: int | None, chat_id: int, message_id: int, cached_id: int | None, raw: dict[str, Any], delivered: bool) -> None:
        async with self._pool().acquire() as con:
            await con.execute(
                """
                INSERT INTO deleted_events(business_connection_id, owner_tg_id, chat_id, message_id, cached_message_id, raw, delivered)
                VALUES($1,$2,$3,$4,$5,$6::jsonb,$7)
                """,
                bc_id,
                owner_id,
                chat_id,
                message_id,
                cached_id,
                json.dumps(raw),
                delivered,
            )
            await con.execute(
                "UPDATE cached_messages SET deleted_at=NOW() WHERE business_connection_id=$1 AND chat_id=$2 AND message_id=$3",
                bc_id,
                chat_id,
                message_id,
            )

    async def can_use_free_deleted(self, tg_id: int) -> bool:
        if await self.active_subscription(tg_id):
            return True
        limit = await self.get_setting_int("free_deleted_limit_per_day", self.settings.free_deleted_limit_per_day)
        today = date.today()
        async with self._pool().acquire() as con:
            row = await con.fetchrow("SELECT free_deleted_today, free_deleted_reset_date FROM users WHERE tg_id=$1", tg_id)
            if not row:
                return False
            count = int(row["free_deleted_today"])
            reset_date = row["free_deleted_reset_date"]
            if reset_date != today:
                await con.execute("UPDATE users SET free_deleted_today=0, free_deleted_reset_date=$2 WHERE tg_id=$1", tg_id, today)
                count = 0
            return count < limit

    async def consume_free_deleted(self, tg_id: int) -> None:
        if await self.active_subscription(tg_id):
            return
        today = date.today()
        async with self._pool().acquire() as con:
            await con.execute(
                """
                UPDATE users SET
                  free_deleted_today = CASE WHEN free_deleted_reset_date=$2 THEN free_deleted_today + 1 ELSE 1 END,
                  free_deleted_reset_date=$2
                WHERE tg_id=$1
                """,
                tg_id,
                today,
            )


    async def add_keyword(self, tg_id: int, keyword: str) -> None:
        keyword = keyword.strip().lower()[:80]
        if not keyword:
            return
        async with self._pool().acquire() as con:
            await con.execute(
                """INSERT INTO user_keywords(owner_tg_id, keyword) VALUES($1, $2)
                ON CONFLICT(owner_tg_id, keyword) DO UPDATE SET is_active=TRUE""",
                tg_id,
                keyword,
            )

    async def delete_keyword(self, tg_id: int, keyword: str) -> None:
        keyword = keyword.strip().lower()[:80]
        async with self._pool().acquire() as con:
            await con.execute("DELETE FROM user_keywords WHERE owner_tg_id=$1 AND keyword=$2", tg_id, keyword)

    async def list_keywords(self, tg_id: int) -> list[str]:
        async with self._pool().acquire() as con:
            rows = await con.fetch("SELECT keyword FROM user_keywords WHERE owner_tg_id=$1 AND is_active=TRUE ORDER BY keyword", tg_id)
            return [str(r["keyword"]) for r in rows]

    async def match_keywords(self, tg_id: int, text: str) -> list[str]:
        haystack = text.lower()
        words = await self.list_keywords(tg_id)
        return [w for w in words if w and w in haystack]

    async def forget_user(self, tg_id: int) -> None:
        async with self._pool().acquire() as con:
            async with con.transaction():
                await con.execute("DELETE FROM deleted_events WHERE owner_tg_id=$1", tg_id)
                await con.execute("DELETE FROM cached_messages WHERE owner_tg_id=$1", tg_id)
                await con.execute("DELETE FROM business_connections WHERE owner_tg_id=$1", tg_id)
                await con.execute("DELETE FROM payments WHERE user_id=$1", tg_id)
                await con.execute("UPDATE users SET subscription_until=NULL, free_deleted_today=0 WHERE tg_id=$1", tg_id)

    async def stats(self) -> dict[str, Any]:
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                SELECT
                  (SELECT COUNT(*) FROM users) AS users,
                  (SELECT COUNT(*) FROM users WHERE subscription_until > NOW()) AS active_subs,
                  (SELECT COUNT(*) FROM business_connections WHERE is_enabled=TRUE) AS connections,
                  (SELECT COUNT(*) FROM cached_messages) AS messages,
                  (SELECT COUNT(*) FROM deleted_events) AS deletions,
                  (SELECT COALESCE(SUM(amount_usd),0) FROM payments WHERE status='paid') AS paid,
                  (SELECT COUNT(*) FROM payments WHERE status IN ('pending','waiting_admin') AND provider <> 'cryptobot') AS pending
                """
            )
            return dict(row)

    async def set_setting(self, key: str, value: Any) -> None:
        async with self._pool().acquire() as con:
            await con.execute(
                """
                INSERT INTO settings(key, value) VALUES($1, $2::jsonb)
                ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
                """,
                key,
                json.dumps(value),
            )

    async def get_setting(self, key: str, default: Any = None) -> Any:
        async with self._pool().acquire() as con:
            val = await con.fetchval("SELECT value FROM settings WHERE key=$1", key)
            return decode_json(val, default) if val is not None else default

    async def get_setting_int(self, key: str, default: int) -> int:
        val = await self.get_setting(key, default)
        return int(val)

    async def set_template(
        self,
        key: str,
        text: str,
        entities: list[dict[str, Any]] | None = None,
        media: dict[str, Any] | None = None,
    ) -> None:
        payload = {"text": text or "", "entities": entities or []}
        if media and media.get("file_id") and media.get("kind"):
            payload["media"] = {
                "kind": str(media.get("kind")),
                "file_id": str(media.get("file_id")),
            }
        await self.set_setting(f"template_{key}", payload)

    async def get_template(self, key: str) -> dict[str, Any] | None:
        value = await self.get_setting(f"template_{key}", None)
        value = decode_json(value, None)
        if isinstance(value, dict) and isinstance(value.get("text"), str):
            entities = value.get("entities") or []
            if not isinstance(entities, list):
                entities = []
            media = value.get("media") or None
            if not isinstance(media, dict) or not media.get("file_id") or not media.get("kind"):
                media = None
            return {"text": value.get("text") or "", "entities": entities, "media": media}
        return None

    async def set_state(self, user_id: int, state: str, payload: dict[str, Any] | None = None) -> None:
        async with self._pool().acquire() as con:
            await con.execute(
                """
                INSERT INTO user_states(user_id, state, payload) VALUES($1, $2, $3::jsonb)
                ON CONFLICT(user_id) DO UPDATE SET state=EXCLUDED.state, payload=EXCLUDED.payload, updated_at=NOW()
                """,
                user_id,
                state,
                json.dumps(payload or {}),
            )

    async def get_state(self, user_id: int) -> dict[str, Any] | None:
        async with self._pool().acquire() as con:
            row = await con.fetchrow("SELECT * FROM user_states WHERE user_id=$1", user_id)
            if not row:
                return None
            data = dict(row)
            data["payload"] = decode_json(data.get("payload"), {}) or {}
            return data

    async def clear_state(self, user_id: int) -> None:
        async with self._pool().acquire() as con:
            await con.execute("DELETE FROM user_states WHERE user_id=$1", user_id)

    async def pending_payments(self, limit: int = 10) -> list[dict[str, Any]]:
        async with self._pool().acquire() as con:
            rows = await con.fetch(
                """
                SELECT p.*, u.username, u.first_name, u.last_name, pl.code AS plan_code, pl.name_uk, pl.name_ru, pl.name_en
                FROM payments p
                LEFT JOIN users u ON u.tg_id=p.user_id
                LEFT JOIN plans pl ON pl.id=p.plan_id
                WHERE p.status IN ('pending','waiting_admin') AND p.provider <> 'cryptobot'
                ORDER BY p.created_at ASC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]

    async def recent_users(self, limit: int = 10) -> list[dict[str, Any]]:
        async with self._pool().acquire() as con:
            rows = await con.fetch(
                """
                SELECT tg_id, username, first_name, last_name, lang, subscription_until, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]

    async def cleanup_old_messages(self) -> int:
        paid_days = await self.get_setting_int("message_retention_days", self.settings.message_retention_days)
        free_hours = await self.get_setting_int("free_retention_hours", self.settings.free_retention_hours)
        async with self._pool().acquire() as con:
            result = await con.execute(
                """
                DELETE FROM cached_messages cm
                USING users u
                WHERE cm.owner_tg_id = u.tg_id
                AND (
                  (u.subscription_until IS NULL OR u.subscription_until <= NOW()) AND cm.created_at < NOW() - ($1::TEXT || ' hours')::INTERVAL
                  OR
                  (u.subscription_until > NOW() AND cm.created_at < NOW() - ($2::TEXT || ' days')::INTERVAL)
                )
                """,
                free_hours,
                paid_days,
            )
            try:
                return int(result.split()[-1])
            except Exception:
                return 0


def display_name(obj: dict[str, Any] | None) -> str | None:
    if not obj:
        return None
    if obj.get("title"):
        return obj["title"]
    parts = [obj.get("first_name"), obj.get("last_name")]
    name = " ".join([p for p in parts if p])
    if name:
        return name
    if obj.get("username"):
        return "@" + obj["username"]
    if obj.get("id"):
        return str(obj["id"])
    return None


def extract_message_content(msg: dict[str, Any]) -> tuple[str, str | None, str | None, str | None]:
    if msg.get("text") is not None:
        return "text", msg.get("text"), None, None
    if msg.get("photo"):
        photos = msg.get("photo") or []
        file_id = photos[-1].get("file_id") if photos else None
        return "photo", None, msg.get("caption"), file_id
    for kind in ["video", "animation", "document", "audio", "voice", "video_note", "sticker"]:
        if msg.get(kind):
            data = msg[kind]
            return kind, None, msg.get("caption"), data.get("file_id")
    if msg.get("contact"):
        return "contact", json.dumps(msg.get("contact"), ensure_ascii=False), None, None
    if msg.get("location"):
        return "location", json.dumps(msg.get("location"), ensure_ascii=False), None, None
    if msg.get("poll"):
        return "poll", json.dumps(msg.get("poll"), ensure_ascii=False), None, None
    return "unknown", msg.get("caption"), msg.get("caption"), None
