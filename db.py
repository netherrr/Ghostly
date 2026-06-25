from __future__ import annotations

import json
import os
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
            lang TEXT NOT NULL DEFAULT 'ru',
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
            price_uah NUMERIC(12,0),
            price_stars INT,
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
            file_bytes BYTEA,
            file_name TEXT,
            file_size BIGINT,
            mime_type TEXT,
            is_disappearing BOOLEAN NOT NULL DEFAULT FALSE,
            file_cached_at TIMESTAMPTZ,
            media_backup_sent_at TIMESTAMPTZ,
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

        -- Deterministic /edit: remember which reusable template every bot
        -- screen was sent as, so reply -> /edit can resolve the exact template
        -- by (chat_id, message_id) instead of guessing from the message text.
        CREATE TABLE IF NOT EXISTS sent_template_messages (
            chat_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            template_key TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY(chat_id, message_id)
        );

        ALTER TABLE plans ADD COLUMN IF NOT EXISTS price_uah NUMERIC(12,0);
        ALTER TABLE plans ADD COLUMN IF NOT EXISTS price_stars INT;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_id BIGINT REFERENCES users(tg_id) ON DELETE SET NULL;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_created_at TIMESTAMPTZ;

        CREATE TABLE IF NOT EXISTS referral_rewards (
            id BIGSERIAL PRIMARY KEY,
            referrer_id BIGINT REFERENCES users(tg_id) ON DELETE SET NULL,
            buyer_id BIGINT REFERENCES users(tg_id) ON DELETE SET NULL,
            payment_id BIGINT UNIQUE REFERENCES payments(id) ON DELETE CASCADE,
            percent NUMERIC(5,2) NOT NULL DEFAULT 30.00,
            purchase_amount_usd NUMERIC(12,2) NOT NULL,
            reward_amount_usd NUMERIC(12,2) NOT NULL,
            status TEXT NOT NULL DEFAULT 'available',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            paid_at TIMESTAMPTZ,
            admin_checked_by BIGINT,
            raw JSONB NOT NULL DEFAULT '{}'::jsonb
        );

        CREATE INDEX IF NOT EXISTS idx_referral_referrer ON referral_rewards(referrer_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_referral_buyer ON referral_rewards(buyer_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);

        CREATE INDEX IF NOT EXISTS idx_cached_owner ON cached_messages(owner_tg_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_cached_lookup ON cached_messages(business_connection_id, chat_id, message_id);
        CREATE INDEX IF NOT EXISTS idx_deleted_owner ON deleted_events(owner_tg_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_sent_template_created ON sent_template_messages(created_at);

        -- New referral model (days-based bonuses) + free trial tracking.
        ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_granted BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium_user BOOLEAN NOT NULL DEFAULT FALSE;
        ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_checked_at TIMESTAMPTZ;

        -- Each row is one referral accrual. referred_id is unique (when not null)
        -- so a single Telegram account can be credited at most once. Manual admin
        -- adjustments use kind='manual' with referred_id NULL.
        CREATE TABLE IF NOT EXISTS referral_bonuses (
            id BIGSERIAL PRIMARY KEY,
            referrer_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
            referred_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
            kind TEXT NOT NULL DEFAULT 'normal',
            is_premium BOOLEAN NOT NULL DEFAULT FALSE,
            bonus_days INT NOT NULL DEFAULT 0,
            counted BOOLEAN NOT NULL DEFAULT TRUE,
            note TEXT,
            admin_id BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_referral_bonuses_referred
            ON referral_bonuses(referred_id) WHERE referred_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_referral_bonuses_referrer
            ON referral_bonuses(referrer_id, created_at DESC);

        -- Auto-broadcast targets (groups/channels where the bot is admin).
        CREATE TABLE IF NOT EXISTS broadcast_chats (
            chat_id BIGINT PRIMARY KEY,
            title TEXT,
            chat_type TEXT,
            interval_seconds INT NOT NULL DEFAULT 1800,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            last_message_id BIGINT,
            last_sent_at TIMESTAMPTZ,
            added_by BIGINT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_broadcast_active ON broadcast_chats(is_active);

        -- Group keyword monitoring: a user links a group/channel (where the bot
        -- can read messages) so their keywords are matched against it.
        CREATE TABLE IF NOT EXISTS monitored_chats (
            id BIGSERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            owner_tg_id BIGINT REFERENCES users(tg_id) ON DELETE CASCADE,
            title TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(chat_id, owner_tg_id)
        );
        CREATE INDEX IF NOT EXISTS idx_monitored_chat ON monitored_chats(chat_id) WHERE is_active;
        CREATE INDEX IF NOT EXISTS idx_monitored_owner ON monitored_chats(owner_tg_id);
        """
        async with self._pool().acquire() as con:
            await con.execute(sql)
            await con.execute("ALTER TABLE cached_messages ADD COLUMN IF NOT EXISTS file_bytes BYTEA")
            await con.execute("ALTER TABLE cached_messages ADD COLUMN IF NOT EXISTS file_name TEXT")
            await con.execute("ALTER TABLE cached_messages ADD COLUMN IF NOT EXISTS file_size BIGINT")
            await con.execute("ALTER TABLE cached_messages ADD COLUMN IF NOT EXISTS mime_type TEXT")
            await con.execute("ALTER TABLE cached_messages ADD COLUMN IF NOT EXISTS is_disappearing BOOLEAN NOT NULL DEFAULT FALSE")
            await con.execute("ALTER TABLE cached_messages ADD COLUMN IF NOT EXISTS file_cached_at TIMESTAMPTZ")
            await con.execute("ALTER TABLE cached_messages ADD COLUMN IF NOT EXISTS media_backup_sent_at TIMESTAMPTZ")

    async def seed_defaults(self) -> None:
        async with self._pool().acquire() as con:
            # Timer-only professional fix: force current defaults even on old DBs
            # that may contain previous false/debug values from earlier builds.
            await con.execute(
                """
                INSERT INTO settings(key, value) VALUES
                    ('timer_only_professional_fix_v1', 'true'::jsonb),
                    ('timer_media_candidate_instant', 'true'::jsonb),
                    ('timer_media_candidate_types', '["photo","video","video_note"]'::jsonb)
                ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
                """
            )

            # New public launch defaults: no Premium/Pro gate for core functions.
            await con.execute(
                """
                INSERT INTO settings(key, value) VALUES
                    ('no_premium_rebuild_defaults_v1', 'true'::jsonb),
                    ('open_access_enabled', 'true'::jsonb),
                    ('timer_media_candidate_instant', 'true'::jsonb),
                    ('timer_media_candidate_types', '["photo","video","video_note"]'::jsonb)
                ON CONFLICT(key) DO NOTHING
                """
            )

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

            # 2026 pricing model. Seven duration-based subscriptions with a single
            # full-access tier. All earlier Pro/Basic tiers are disabled so old
            # prices never resurface anywhere in the system.
            await con.execute(
                """
                UPDATE plans
                   SET is_active=FALSE, updated_at=NOW()
                 WHERE code IN ('basic_month', 'pro_month', 'pro_30', 'pro_90',
                                'pro_180', 'pro_365', 'pro_lifetime')
                """
            )

            full_uk = '✅ Повний доступ до всіх функцій'
            full_ru = '✅ Полный доступ ко всем функциям'
            full_en = '✅ Full access to all features'
            await con.execute(
                """
                INSERT INTO plans(code, name_uk, name_ru, name_en, features_uk, features_ru, features_en, price_usd, price_uah, price_stars, duration_days, position, is_active)
                VALUES
                ('sub_1d',   '1 день',     '1 день',     '1 day',     $1, $2, $3, 0.15, NULL, 20,  1,   10, TRUE),
                ('sub_3d',   '3 дні',      '3 дня',      '3 days',    $1, $2, $3, 0.25, NULL, 30,  3,   20, TRUE),
                ('sub_7d',   '7 днів',     '7 дней',     '7 days',    $1, $2, $3, 0.40, NULL, 50,  7,   30, TRUE),
                ('sub_30d',  '1 місяць',   '1 месяц',    '1 month',   $1, $2, $3, 0.99, NULL, 120, 30,  40, TRUE),
                ('sub_90d',  '3 місяці',   '3 месяца',   '3 months',  $1, $2, $3, 1.99, NULL, 240, 90,  50, TRUE),
                ('sub_180d', '6 місяців',  '6 месяцев',  '6 months',  $1, $2, $3, 2.99, NULL, 360, 180, 60, TRUE),
                ('sub_365d', '12 місяців', '12 месяцев', '12 months', $1, $2, $3, 3.99, NULL, 480, 365, 70, TRUE)
                ON CONFLICT(code) DO UPDATE SET
                    name_uk=EXCLUDED.name_uk,
                    name_ru=EXCLUDED.name_ru,
                    name_en=EXCLUDED.name_en,
                    features_uk=EXCLUDED.features_uk,
                    features_ru=EXCLUDED.features_ru,
                    features_en=EXCLUDED.features_en,
                    duration_days=EXCLUDED.duration_days,
                    position=EXCLUDED.position,
                    is_active=TRUE,
                    updated_at=NOW()
                """,
                full_uk, full_ru, full_en,
            )

            # One-time price enforcement for the new model so a fresh deploy lands
            # on the exact requested prices even if a partial seed ran earlier.
            pricing_applied = await con.fetchval("SELECT value FROM settings WHERE key='pricing_model_2026_v1'")
            if not pricing_applied:
                await con.execute(
                    """
                    UPDATE plans SET
                        price_usd = CASE code
                            WHEN 'sub_1d' THEN 0.15 WHEN 'sub_3d' THEN 0.25
                            WHEN 'sub_7d' THEN 0.40 WHEN 'sub_30d' THEN 0.99
                            WHEN 'sub_90d' THEN 1.99 WHEN 'sub_180d' THEN 2.99
                            WHEN 'sub_365d' THEN 3.99 ELSE price_usd END,
                        updated_at=NOW()
                     WHERE code IN ('sub_1d','sub_3d','sub_7d','sub_30d','sub_90d','sub_180d','sub_365d')
                    """
                )
                await con.execute(
                    "INSERT INTO settings(key, value) VALUES('pricing_model_2026_v1', 'true'::jsonb) ON CONFLICT(key) DO UPDATE SET value='true'::jsonb, updated_at=NOW()"
                )

            # Stars repricing at 120⭐ per $1, rounded UP to the nearest 5 (so a
            # Stars purchase is never below the USD rate). Forces the values once
            # on existing DBs that still hold earlier ones.
            stars_applied = await con.fetchval("SELECT value FROM settings WHERE key='stars_pricing_2026_v4'")
            if not stars_applied:
                await con.execute(
                    """
                    UPDATE plans SET
                        price_stars = CASE code
                            WHEN 'sub_1d' THEN 20  WHEN 'sub_3d' THEN 30
                            WHEN 'sub_7d' THEN 50  WHEN 'sub_30d' THEN 120
                            WHEN 'sub_90d' THEN 240 WHEN 'sub_180d' THEN 360
                            WHEN 'sub_365d' THEN 480 ELSE price_stars END,
                        updated_at=NOW()
                     WHERE code IN ('sub_1d','sub_3d','sub_7d','sub_30d','sub_90d','sub_180d','sub_365d')
                    """
                )
                await con.execute(
                    "INSERT INTO settings(key, value) VALUES('stars_pricing_2026_v4', 'true'::jsonb) ON CONFLICT(key) DO UPDATE SET value='true'::jsonb, updated_at=NOW()"
                )

            await con.execute(
                """
                INSERT INTO payment_methods(code, title_uk, title_ru, title_en, instructions_uk, instructions_ru, instructions_en, details, position, is_active)
                VALUES
                ('telegram_stars', '⭐ Telegram Stars', '⭐ Telegram Stars', '⭐ Telegram Stars',
                 'Оплата зірками Telegram. Натисни кнопку оплати, підтверди покупку — доступ активується автоматично.',
                 'Оплата звёздами Telegram. Нажми кнопку оплаты, подтверди покупку — доступ активируется автоматически.',
                 'Pay with Telegram Stars. Tap the payment button and confirm — access activates automatically.', '{}'::jsonb, 5, TRUE),
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
                "referral_percent": 30,
                "uah_rate": 44,
                # New referral model (days-based bonuses).
                "trial_days": 2,
                "access_gating_enabled": True,
                "ref_normal_days": 2,
                "ref_normal_limit": 3,
                "ref_premium_days": 5,
                # Broadcast system defaults.
                "broadcast_default_interval": 1800,
                "broadcast_enabled": True,
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

            # One-time bump of the free trial to 2 days for already-seeded DBs
            # (the INSERT above is DO NOTHING and would keep an old value of 1).
            trial_bumped = await con.fetchval("SELECT value FROM settings WHERE key='trial_2days_v1'")
            if not trial_bumped:
                await con.execute(
                    "INSERT INTO settings(key, value) VALUES('trial_days', '2'::jsonb) ON CONFLICT(key) DO UPDATE SET value='2'::jsonb, updated_at=NOW()"
                )
                await con.execute(
                    "INSERT INTO settings(key, value) VALUES('trial_2days_v1', 'true'::jsonb) ON CONFLICT(key) DO UPDATE SET value='true'::jsonb, updated_at=NOW()"
                )

            # One-time project setup requested by owner: prefill real payment
            # details and set UAH/USD rate to 44. We mark it as applied so future
            # restarts will not overwrite manual admin edits in the bot panel.
            applied = await con.fetchval("SELECT value FROM settings WHERE key='requisites_prefill_v1'")
            if not applied:
                await con.execute(
                    """
                    INSERT INTO settings(key, value) VALUES('uah_rate', '44'::jsonb)
                    ON CONFLICT(key) DO UPDATE SET value='44'::jsonb, updated_at=NOW()
                    """
                )
                await con.execute(
                    """
                    INSERT INTO payment_methods(code, title_uk, title_ru, title_en, instructions_uk, instructions_ru, instructions_en, details, position, is_active)
                    VALUES
                    ('ua_card', 'Українська картка', 'Украинская карта', 'Ukrainian card',
                     $1, $2, $3,
                     $4::jsonb, 20, TRUE),
                    ('binance_id', 'Binance ID', 'Binance ID', 'Binance ID',
                     $5, $6, $7,
                     $8::jsonb, 30, TRUE),
                    ('usdt_trc20', 'USDT TRC20', 'USDT TRC20', 'USDT TRC20',
                     $9, $10, $11,
                     $12::jsonb, 40, TRUE),
                    ('usdt_bep20', 'USDT BEP20', 'USDT BEP20', 'USDT BEP20',
                     $13, $14, $15,
                     $16::jsonb, 50, TRUE),
                    ('ton', 'TON', 'TON', 'TON',
                     $17, $18, $19,
                     $20::jsonb, 60, TRUE)
                    ON CONFLICT(code) DO UPDATE SET
                        title_uk=EXCLUDED.title_uk,
                        title_ru=EXCLUDED.title_ru,
                        title_en=EXCLUDED.title_en,
                        instructions_uk=EXCLUDED.instructions_uk,
                        instructions_ru=EXCLUDED.instructions_ru,
                        instructions_en=EXCLUDED.instructions_en,
                        details=EXCLUDED.details,
                        position=EXCLUDED.position,
                        is_active=TRUE,
                        updated_at=NOW()
                    """,
                    """💳 <b>Українська картка — ручна оплата</b>

Сума до оплати в гривні буде показана вище в повідомленні бота. Переказуй саме цю суму.

💳 <b>Картка:</b>
<code>4441114419666357</code>

👤 <b>Отримувач:</b>
<code>Назар М</code>

Після оплати натисни «Я оплатив» і надішли скріншот, квитанцію або файл підтвердження.

Доступ активується після перевірки адміністратором.""",
                    """💳 <b>Украинская карта — ручная оплата</b>

Сумма к оплате в гривне будет показана выше в сообщении бота. Переводи именно эту сумму.

💳 <b>Карта:</b>
<code>4441114419666357</code>

👤 <b>Получатель:</b>
<code>Назар М</code>

После оплаты нажми «Я оплатил» и отправь скриншот, квитанцию или файл подтверждения.

Доступ активируется после проверки администратором.""",
                    """💳 <b>Ukrainian card — manual payment</b>

The UAH amount will be shown above in the bot message. Please send exactly that amount.

💳 <b>Card:</b>
<code>4441114419666357</code>

👤 <b>Recipient:</b>
<code>Nazar M</code>

After payment, press “I paid” and send a screenshot, receipt, or confirmation file.

Access will be activated after admin verification.""",
                    json.dumps({"card":"4441114419666357","recipient":"Назар М"}),
                    """🚗 <b>Binance ID — ручна оплата</b>

Оплати суму, яку бот показав вище.

🚗 <b>BINANCE ID:</b>
<code>482957043</code>

Nickname:
<code>travyx</code>

Після оплати натисни «Я оплатив» і надішли скріншот, квитанцію або TxID/коментар платежу.""",
                    """🚗 <b>Binance ID — ручная оплата</b>

Оплати сумму, которую бот показал выше.

🚗 <b>BINANCE ID:</b>
<code>482957043</code>

Nickname:
<code>travyx</code>

После оплаты нажми «Я оплатил» и отправь скриншот, квитанцию или TxID/комментарий платежа.""",
                    """🚗 <b>Binance ID — manual payment</b>

Send the amount shown above by the bot.

🚗 <b>BINANCE ID:</b>
<code>482957043</code>

Nickname:
<code>travyx</code>

After payment, press “I paid” and send a screenshot, receipt, or TxID/payment comment.""",
                    json.dumps({"binance_id":"482957043","nickname":"travyx"}),
                    """🪙 <b>USDT TRC20 — ручна оплата</b>

Оплати суму, яку бот показав вище.

Мережа: <b>TRC20</b>
Гаманець:
<code>TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei</code>

Після оплати натисни «Я оплатив» і надішли скріншот, квитанцію або hash/TxID транзакції.

Важливо: перевір мережу перед оплатою. Якщо відправити USDT не в ту мережу, платіж може бути втрачений.""",
                    """🪙 <b>USDT TRC20 — ручная оплата</b>

Оплати сумму, которую бот показал выше.

Сеть: <b>TRC20</b>
Кошелёк:
<code>TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei</code>

После оплаты нажми «Я оплатил» и отправь скриншот, квитанцию или hash/TxID транзакции.

Важно: проверь сеть перед оплатой. Если отправить USDT не в ту сеть, платёж может быть потерян.""",
                    """🪙 <b>USDT TRC20 — manual payment</b>

Send the amount shown above by the bot.

Network: <b>TRC20</b>
Wallet:
<code>TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei</code>

After payment, press “I paid” and send a screenshot, receipt, or transaction hash/TxID.

Important: check the network before sending. If USDT is sent through the wrong network, the payment may be lost.""",
                    json.dumps({"network":"TRC20","address":"TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei"}),
                    """🪙 <b>USDT BEP20 — ручна оплата</b>

Оплати суму, яку бот показав вище.

Мережа: <b>BEP20</b>
Гаманець:
<code>0x2d523071538cd8a417858d78775e966c9171ffc8</code>

Після оплати натисни «Я оплатив» і надішли скріншот, квитанцію або hash/TxID транзакції.

Важливо: перевір мережу перед оплатою. Якщо відправити USDT не в ту мережу, платіж може бути втрачений.""",
                    """🪙 <b>USDT BEP20 — ручная оплата</b>

Оплати сумму, которую бот показал выше.

Сеть: <b>BEP20</b>
Кошелёк:
<code>0x2d523071538cd8a417858d78775e966c9171ffc8</code>

После оплаты нажми «Я оплатил» и отправь скриншот, квитанцию или hash/TxID транзакции.

Важно: проверь сеть перед оплатой. Если отправить USDT не в ту сеть, платёж может быть потерян.""",
                    """🪙 <b>USDT BEP20 — manual payment</b>

Send the amount shown above by the bot.

Network: <b>BEP20</b>
Wallet:
<code>0x2d523071538cd8a417858d78775e966c9171ffc8</code>

After payment, press “I paid” and send a screenshot, receipt, or transaction hash/TxID.

Important: check the network before sending. If USDT is sent through the wrong network, the payment may be lost.""",
                    json.dumps({"network":"BEP20","address":"0x2d523071538cd8a417858d78775e966c9171ffc8"}),
                    """💎 <b>TON — ручна оплата</b>

Оплати суму, яку бот показав вище.

TON-гаманець:
<code>UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3</code>

Після оплати натисни «Я оплатив» і надішли скріншот, квитанцію або hash/TxID транзакції.""",
                    """💎 <b>TON — ручная оплата</b>

Оплати сумму, которую бот показал выше.

TON-кошелёк:
<code>UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3</code>

После оплаты нажми «Я оплатил» и отправь скриншот, квитанцию или hash/TxID транзакции.""",
                    """💎 <b>TON — manual payment</b>

Send the amount shown above by the bot.

TON wallet:
<code>UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3</code>

After payment, press “I paid” and send a screenshot, receipt, or transaction hash/TxID.""",
                    json.dumps({"network":"TON","address":"UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3"}),
                )
                await con.execute(
                    """
                    INSERT INTO settings(key, value) VALUES('requisites_prefill_v1', 'true'::jsonb)
                    ON CONFLICT(key) DO UPDATE SET value='true'::jsonb, updated_at=NOW()
                    """
                )


            # One-time cleanup after owner feedback: simplify manual payment text
            # and remove repeated explanations. This intentionally overwrites the
            # previous prefilled requisites/templates once, then protects future edits.
            simplified = await con.fetchval("SELECT value FROM settings WHERE key='requisites_simplified_v2'")
            if not simplified:
                await con.execute(
                    """
                    INSERT INTO settings(key, value) VALUES('uah_rate', '44'::jsonb)
                    ON CONFLICT(key) DO UPDATE SET value='44'::jsonb, updated_at=NOW()
                    """
                )
                await con.execute(
                    """
                    UPDATE payment_methods SET
                        instructions_uk=$2,
                        instructions_ru=$3,
                        instructions_en=$4,
                        details=$5::jsonb,
                        updated_at=NOW()
                    WHERE code=$1
                    """,
                    "ua_card",
                    """💳 <b>Картка:</b>
<code>4441114419666357</code>

👤 <b>Отримувач:</b>
<code>Назар М</code>""",
                    """💳 <b>Карта:</b>
<code>4441114419666357</code>

👤 <b>Получатель:</b>
<code>Назар М</code>""",
                    """💳 <b>Card:</b>
<code>4441114419666357</code>

👤 <b>Recipient:</b>
<code>Nazar M</code>""",
                    json.dumps({"card": "4441114419666357", "recipient": "Назар М"}),
                )
                await con.execute(
                    """
                    UPDATE payment_methods SET instructions_uk=$2, instructions_ru=$3, instructions_en=$4, details=$5::jsonb, updated_at=NOW()
                    WHERE code=$1
                    """,
                    "binance_id",
                    """🚗 <b>Binance ID:</b>
<code>482957043</code>

Nickname:
<code>travyx</code>""",
                    """🚗 <b>Binance ID:</b>
<code>482957043</code>

Nickname:
<code>travyx</code>""",
                    """🚗 <b>Binance ID:</b>
<code>482957043</code>

Nickname:
<code>travyx</code>""",
                    json.dumps({"binance_id": "482957043", "nickname": "travyx"}),
                )
                await con.execute(
                    """
                    UPDATE payment_methods SET instructions_uk=$2, instructions_ru=$3, instructions_en=$4, details=$5::jsonb, updated_at=NOW()
                    WHERE code=$1
                    """,
                    "usdt_trc20",
                    """🪙 <b>USDT TRC20</b>
<code>TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei</code>

Перевір мережу перед оплатою.""",
                    """🪙 <b>USDT TRC20</b>
<code>TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei</code>

Проверь сеть перед оплатой.""",
                    """🪙 <b>USDT TRC20</b>
<code>TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei</code>

Check the network before sending.""",
                    json.dumps({"network": "TRC20", "address": "TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei"}),
                )
                await con.execute(
                    """
                    UPDATE payment_methods SET instructions_uk=$2, instructions_ru=$3, instructions_en=$4, details=$5::jsonb, updated_at=NOW()
                    WHERE code=$1
                    """,
                    "usdt_bep20",
                    """🪙 <b>USDT BEP20</b>
<code>0x2d523071538cd8a417858d78775e966c9171ffc8</code>

Перевір мережу перед оплатою.""",
                    """🪙 <b>USDT BEP20</b>
<code>0x2d523071538cd8a417858d78775e966c9171ffc8</code>

Проверь сеть перед оплатой.""",
                    """🪙 <b>USDT BEP20</b>
<code>0x2d523071538cd8a417858d78775e966c9171ffc8</code>

Check the network before sending.""",
                    json.dumps({"network": "BEP20", "address": "0x2d523071538cd8a417858d78775e966c9171ffc8"}),
                )
                await con.execute(
                    """
                    UPDATE payment_methods SET instructions_uk=$2, instructions_ru=$3, instructions_en=$4, details=$5::jsonb, updated_at=NOW()
                    WHERE code=$1
                    """,
                    "ton",
                    """💎 <b>TON</b>
<code>UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3</code>""",
                    """💎 <b>TON</b>
<code>UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3</code>""",
                    """💎 <b>TON</b>
<code>UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3</code>""",
                    json.dumps({"network": "TON", "address": "UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3"}),
                )
                manual_templates = {
                    "template_payment_manual_uk": {
                        "text": "💳 Ручна оплата\n\n💎 Тариф: {plan_name}\n{payment_amount_lines}\n\n{instructions}\n\nПісля оплати натисни «Я оплатив» і надішли скрін/квитанцію.",
                        "entities": [],
                    },
                    "template_payment_manual_ru": {
                        "text": "💳 Ручная оплата\n\n💎 Тариф: {plan_name}\n{payment_amount_lines}\n\n{instructions}\n\nПосле оплаты нажми «Я оплатил» и отправь скрин/квитанцию.",
                        "entities": [],
                    },
                    "template_payment_manual_en": {
                        "text": "💳 Manual payment\n\n💎 Plan: {plan_name}\n{payment_amount_lines}\n\n{instructions}\n\nAfter payment, press “I paid” and send a receipt/screenshot.",
                        "entities": [],
                    },
                }
                for key, value in manual_templates.items():
                    await con.execute(
                        """
                        INSERT INTO settings(key, value) VALUES($1, $2::jsonb)
                        ON CONFLICT(key) DO UPDATE SET value=$2::jsonb, updated_at=NOW()
                        """,
                        key,
                        json.dumps(value),
                    )
                await con.execute(
                    """
                    INSERT INTO settings(key, value) VALUES('requisites_simplified_v2', 'true'::jsonb)
                    ON CONFLICT(key) DO UPDATE SET value='true'::jsonb, updated_at=NOW()
                    """
                )


            # Force-clean manual requisites v3: no HTML tags inside instructions.
            # Payment templates can contain Premium emoji entities, so inserted
            # requisites must be plain text or Telegram will show <b>/<code> as text.
            clean_payments = await con.fetchval("SELECT value FROM settings WHERE key='requisites_plain_v3'")
            if not clean_payments:
                await con.execute(
                    """
                    INSERT INTO settings(key, value) VALUES('uah_rate', '44'::jsonb)
                    ON CONFLICT(key) DO UPDATE SET value='44'::jsonb, updated_at=NOW()
                    """
                )
                await con.execute(
                    """
                    UPDATE payment_methods SET instructions_uk=$2, instructions_ru=$3, instructions_en=$4, details=$5::jsonb, updated_at=NOW()
                    WHERE code=$1
                    """,
                    "ua_card",
                    """💳 Картка:
4441114419666357

👤 Отримувач:
Назар М""",
                    """💳 Карта:
4441114419666357

👤 Получатель:
Назар М""",
                    """💳 Card:
4441114419666357

👤 Recipient:
Nazar M""",
                    json.dumps({"card": "4441114419666357", "recipient": "Назар М"}),
                )
                await con.execute(
                    """
                    UPDATE payment_methods SET instructions_uk=$2, instructions_ru=$3, instructions_en=$4, details=$5::jsonb, updated_at=NOW()
                    WHERE code=$1
                    """,
                    "binance_id",
                    """🚗 Binance ID:
482957043

Nickname:
travyx""",
                    """🚗 Binance ID:
482957043

Nickname:
travyx""",
                    """🚗 Binance ID:
482957043

Nickname:
travyx""",
                    json.dumps({"binance_id": "482957043", "nickname": "travyx"}),
                )
                await con.execute(
                    """
                    UPDATE payment_methods SET instructions_uk=$2, instructions_ru=$3, instructions_en=$4, details=$5::jsonb, updated_at=NOW()
                    WHERE code=$1
                    """,
                    "usdt_trc20",
                    """🪙 USDT TRC20:
TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei

Перевір мережу перед оплатою.""",
                    """🪙 USDT TRC20:
TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei

Проверь сеть перед оплатой.""",
                    """🪙 USDT TRC20:
TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei

Check the network before sending.""",
                    json.dumps({"network": "TRC20", "address": "TW2XKnkY6MdgsJxXZFXqFoucWkgxEqr7Ei"}),
                )
                await con.execute(
                    """
                    UPDATE payment_methods SET instructions_uk=$2, instructions_ru=$3, instructions_en=$4, details=$5::jsonb, updated_at=NOW()
                    WHERE code=$1
                    """,
                    "usdt_bep20",
                    """🪙 USDT BEP20:
0x2d523071538cd8a417858d78775e966c9171ffc8

Перевір мережу перед оплатою.""",
                    """🪙 USDT BEP20:
0x2d523071538cd8a417858d78775e966c9171ffc8

Проверь сеть перед оплатой.""",
                    """🪙 USDT BEP20:
0x2d523071538cd8a417858d78775e966c9171ffc8

Check the network before sending.""",
                    json.dumps({"network": "BEP20", "address": "0x2d523071538cd8a417858d78775e966c9171ffc8"}),
                )
                await con.execute(
                    """
                    UPDATE payment_methods SET instructions_uk=$2, instructions_ru=$3, instructions_en=$4, details=$5::jsonb, updated_at=NOW()
                    WHERE code=$1
                    """,
                    "ton",
                    """💎 TON:
UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3""",
                    """💎 TON:
UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3""",
                    """💎 TON:
UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3""",
                    json.dumps({"network": "TON", "address": "UQDbfUbzkI8lfO6G1KAPB_F2Et2IRTM4EvFhX5ATaXYrjoV3"}),
                )
                await con.execute(
                    """
                    INSERT INTO settings(key, value) VALUES('requisites_plain_v3', 'true'::jsonb)
                    ON CONFLICT(key) DO UPDATE SET value='true'::jsonb, updated_at=NOW()
                    """
                )

    async def upsert_user(self, user: dict[str, Any] | None, lang: str | None = None) -> dict[str, Any] | None:
        if not user or not user.get("id"):
            return None
        tg_id = int(user["id"])
        username = user.get("username")
        first_name = user.get("first_name")
        last_name = user.get("last_name")
        # Telegram includes is_premium on the user object. Cache it so referral
        # bonuses and stats can rely on it even after restarts.
        is_premium = bool(user.get("is_premium")) if "is_premium" in user else None
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                INSERT INTO users(tg_id, username, first_name, last_name, lang, is_admin, is_premium_user, premium_checked_at)
                VALUES($1, $2, $3, $4, COALESCE($5, $6), $7, COALESCE($8, FALSE), CASE WHEN $8 IS NULL THEN NULL ELSE NOW() END)
                ON CONFLICT(tg_id) DO UPDATE SET
                  username=EXCLUDED.username,
                  first_name=EXCLUDED.first_name,
                  last_name=EXCLUDED.last_name,
                  is_premium_user=CASE WHEN $8 IS NULL THEN users.is_premium_user ELSE $8 END,
                  premium_checked_at=CASE WHEN $8 IS NULL THEN users.premium_checked_at ELSE NOW() END,
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
                is_premium,
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
        # Access model: admins always have access; otherwise an active subscription
        # (or the free trial, which is stored as a normal subscription window) is
        # required. Gating can be disabled in the DB (access_gating_enabled) or via
        # the FREE_FULL_ACCESS env override for emergencies.
        if tg_id in self.settings.admin_ids:
            return True
        if os.getenv("FREE_FULL_ACCESS", "false").lower() in {"1", "true", "yes", "on"}:
            return True
        if not await self.get_setting_bool("access_gating_enabled", True):
            return True
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
                INSERT INTO plans(code, name_uk, name_ru, name_en, features_uk, features_ru, features_en, price_usd, price_uah, price_stars, duration_days, position, is_active)
                VALUES($1, $2, $2, $2, '', '', '', $3, NULL, NULL, $4, $5, TRUE)
                RETURNING *
                """,
                clean_code, title, Decimal(str(price_usd)), int(duration_days), int(pos or 100),
            )
            return dict(row)

    async def update_plan_field(self, plan_id: int, field: str, value: str) -> None:
        allowed = {"name_uk", "name_ru", "name_en", "features_uk", "features_ru", "features_en", "price_usd", "price_uah", "price_stars", "duration_days", "is_active", "position"}
        if field not in allowed:
            raise ValueError(f"Unsupported plan field: {field}")
        parsed: Any = value
        if field in {"price_usd"}:
            parsed = Decimal(value.replace(",", "."))
        elif field == "price_uah":
            value_clean = value.strip().lower()
            parsed = None if value_clean in {"", "0", "null", "none", "auto", "авто"} else Decimal(value.replace(",", "."))
        elif field == "price_stars":
            value_clean = value.strip().lower()
            parsed = None if value_clean in {"", "0", "null", "none", "auto", "авто"} else int(value)
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

    async def create_payment(self, user_id: int, plan_id: int | None, provider: str, amount_usd: Decimal | float | str, currency: str = "USD", external_id: str | None = None, invoice_url: str | None = None, raw: dict[str, Any] | None = None) -> dict[str, Any]:
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

    async def get_payment_by_external_id(self, external_id: str) -> dict[str, Any] | None:
        async with self._pool().acquire() as con:
            row = await con.fetchrow("SELECT p.*, pl.duration_days FROM payments p LEFT JOIN plans pl ON p.plan_id=pl.id WHERE p.external_id=$1", external_id)
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

                # Referral rewards are days-based (see referral_bonuses) and are
                # granted at registration time, not per purchase.

                payment["status"] = "paid"
                payment["paid_until"] = until
                return payment

    async def mark_support_payment_paid(self, payment_id: int, raw: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Mark a Telegram Stars support payment as paid without granting subscription."""
        async with self._pool().acquire() as con:
            async with con.transaction():
                row = await con.fetchrow("SELECT * FROM payments WHERE id=$1 FOR UPDATE", payment_id)
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
                updated = await con.fetchrow(
                    "UPDATE payments SET status='paid', paid_at=NOW(), raw=$2::jsonb WHERE id=$1 RETURNING *",
                    payment_id,
                    json.dumps(paid_raw),
                )
                return dict(updated) if updated else None

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
        file_name, file_size, mime_type, is_disappearing = extract_file_metadata(msg)
        # Heuristic: captionless single photo/video/video_note in a business chat is
        # almost always a disappearing media. Mark it so fallback queries can filter
        # correctly without returning normal media with captions.
        if (not is_disappearing
                and content_type in ("photo", "video", "video_note")
                and not caption
                and not msg.get("media_group_id")):
            is_disappearing = True
        sender_name = display_name(sender)
        chat_title = display_name(chat)
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                INSERT INTO cached_messages(
                    business_connection_id, owner_tg_id, chat_id, message_id, sender_id, sender_name, chat_title,
                    content_type, text, caption, file_id, file_name, file_size, mime_type, is_disappearing, media_group_id, raw
                ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17::jsonb)
                ON CONFLICT(business_connection_id, chat_id, message_id) DO UPDATE SET
                    text=EXCLUDED.text,
                    caption=EXCLUDED.caption,
                    file_id=COALESCE(EXCLUDED.file_id, cached_messages.file_id),
                    file_name=COALESCE(EXCLUDED.file_name, cached_messages.file_name),
                    file_size=COALESCE(EXCLUDED.file_size, cached_messages.file_size),
                    mime_type=COALESCE(EXCLUDED.mime_type, cached_messages.mime_type),
                    is_disappearing=COALESCE(cached_messages.is_disappearing, FALSE) OR EXCLUDED.is_disappearing,
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
                file_name,
                file_size,
                mime_type,
                is_disappearing,
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
        file_name, file_size, mime_type, is_disappearing = extract_file_metadata(msg)
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
                    file_name=COALESCE($10, file_name),
                    file_size=COALESCE($11, file_size),
                    mime_type=COALESCE($12, mime_type),
                    is_disappearing=COALESCE(is_disappearing, FALSE) OR $13,
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
                file_name,
                file_size,
                mime_type,
                is_disappearing,
            )
            if row:
                return dict(row)
        return await self.cache_business_message(msg)


    async def set_cached_file_bytes(
        self,
        cached_id: int,
        file_bytes: bytes,
        file_name: str | None = None,
        file_size: int | None = None,
        mime_type: str | None = None,
        is_disappearing: bool = False,
    ) -> None:
        async with self._pool().acquire() as con:
            await con.execute(
                """
                UPDATE cached_messages
                   SET file_bytes=$2,
                       file_name=$3,
                       file_size=$4,
                       mime_type=$5,
                       is_disappearing=COALESCE(is_disappearing, FALSE) OR $6,
                       file_cached_at=NOW(),
                       updated_at=NOW()
                 WHERE id=$1
                """,
                int(cached_id),
                bytes(file_bytes),
                file_name,
                int(file_size) if file_size is not None else len(file_bytes),
                mime_type,
                bool(is_disappearing),
            )

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
            if cached_id:
                await con.execute(
                    "UPDATE cached_messages SET deleted_at=NOW(), updated_at=NOW() WHERE id=$1",
                    cached_id,
                )
            else:
                await con.execute(
                    "UPDATE cached_messages SET deleted_at=NOW(), updated_at=NOW() WHERE business_connection_id=$1 AND chat_id=$2 AND message_id=$3",
                    bc_id,
                    chat_id,
                    message_id,
                )


    async def find_recent_cached_media_for_deleted_event(
        self,
        bc_id: str,
        owner_id: int,
        chat_id: int,
        deleted_message_id: int | None = None,
        minutes: int = 30,
    ) -> dict[str, Any] | None:
        """Fallback matcher for timer/disappearing media.

        Some Telegram timer media can arrive as a normal business_message with one
        message_id, then Telegram later sends deleted_business_messages with a
        different/internal message_id. Exact lookup fails, but the media bytes were
        already cached. In that case use the newest not-yet-delivered media from
        the same business connection + chat.
        """
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                SELECT *
                  FROM cached_messages
                 WHERE business_connection_id=$1
                   AND owner_tg_id=$2
                   AND chat_id=$3
                   AND deleted_at IS NULL
                   AND is_disappearing=TRUE
                   AND content_type IN ('photo','video','animation','document','audio','voice','video_note','sticker')
                   AND created_at >= NOW() - make_interval(mins => $4::int)
                 ORDER BY
                   CASE WHEN file_bytes IS NOT NULL THEN 0 ELSE 1 END,
                   CASE WHEN file_id IS NOT NULL THEN 0 ELSE 1 END,
                   created_at DESC
                 LIMIT 1
                """,
                bc_id,
                owner_id,
                chat_id,
                int(minutes),
            )
            return dict(row) if row else None

    async def mark_cached_message_deleted_by_id(self, cached_id: int) -> None:
        async with self._pool().acquire() as con:
            await con.execute("UPDATE cached_messages SET deleted_at=NOW(), updated_at=NOW() WHERE id=$1", int(cached_id))



    async def mark_media_backup_sent(self, cached_id: int) -> None:
        async with self._pool().acquire() as con:
            await con.execute(
                "UPDATE cached_messages SET media_backup_sent_at=NOW(), updated_at=NOW() WHERE id=$1",
                int(cached_id),
            )

    async def find_recent_cached_media_for_owner(
        self,
        owner_id: int,
        minutes: int = 10,
    ) -> dict[str, Any] | None:
        """Last-resort timer media fallback.

        If Telegram sends deleted_business_messages with a chat/message pair that
        doesn't match the cached business_message, use the newest cached media for
        this owner. This is intentionally a last resort and is mainly for timer
        media where Telegram can use internal message ids.
        """
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                SELECT *
                  FROM cached_messages
                 WHERE owner_tg_id=$1
                   AND deleted_at IS NULL
                   AND is_disappearing=TRUE
                   AND content_type IN ('photo','video','animation','document','audio','voice','video_note','sticker')
                   AND (file_bytes IS NOT NULL OR file_id IS NOT NULL)
                   AND created_at >= NOW() - make_interval(mins => $2::int)
                 ORDER BY
                   CASE WHEN file_bytes IS NOT NULL THEN 0 ELSE 1 END,
                   created_at DESC
                 LIMIT 1
                """,
                owner_id,
                int(minutes),
            )
            return dict(row) if row else None



    async def find_any_recent_cached_media_for_owner(
        self,
        owner_id: int,
        seconds: int = 90,
    ) -> dict[str, Any] | None:
        """Strict last-resort fallback for Telegram timer media.

        Only use very fresh media, otherwise we risk sending an older normal photo.
        This avoids false positives like sending a previous non-timer image when the
        timer media was not actually provided by Telegram.
        """
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                SELECT *
                  FROM cached_messages
                 WHERE owner_tg_id=$1
                   AND is_disappearing=TRUE
                   AND content_type IN ('photo','video','animation','document','audio','voice','video_note','sticker')
                   AND (file_bytes IS NOT NULL OR file_id IS NOT NULL)
                   AND created_at >= NOW() - make_interval(secs => $2::int)
                 ORDER BY
                   CASE WHEN media_backup_sent_at IS NULL THEN 0 ELSE 1 END,
                   CASE WHEN file_bytes IS NOT NULL THEN 0 ELSE 1 END,
                   created_at DESC
                 LIMIT 1
                """,
                owner_id,
                int(seconds),
            )
            return dict(row) if row else None

    async def can_use_free_deleted(self, tg_id: int) -> bool:
        # Admins must always be able to test deleted/timer media without
        # silently hitting the free daily limit.
        if tg_id in self.settings.admin_ids:
            return True
        async with self._pool().acquire() as con:
            admin_row = await con.fetchrow("SELECT is_admin FROM users WHERE tg_id=$1", tg_id)
            if admin_row and bool(admin_row["is_admin"]):
                return True

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
        async with self._pool().acquire() as con:
            admin_row = await con.fetchrow("SELECT is_admin FROM users WHERE tg_id=$1", tg_id)
            if admin_row and bool(admin_row["is_admin"]):
                return
        if os.getenv("FREE_FULL_ACCESS", "true").lower() in {"1", "true", "yes", "on"}:
            return
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

    # ----- Group keyword monitoring -----

    async def add_monitored_chat(self, chat_id: int, owner_tg_id: int, title: str | None = None) -> dict[str, Any]:
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                INSERT INTO monitored_chats(chat_id, owner_tg_id, title)
                VALUES($1, $2, $3)
                ON CONFLICT(chat_id, owner_tg_id) DO UPDATE SET
                    is_active=TRUE,
                    title=COALESCE(EXCLUDED.title, monitored_chats.title),
                    updated_at=NOW()
                RETURNING *
                """,
                int(chat_id),
                int(owner_tg_id),
                title,
            )
            return dict(row)

    async def remove_monitored_chat(self, chat_id: int, owner_tg_id: int) -> bool:
        async with self._pool().acquire() as con:
            result = await con.execute(
                "DELETE FROM monitored_chats WHERE chat_id=$1 AND owner_tg_id=$2",
                int(chat_id),
                int(owner_tg_id),
            )
            try:
                return int(result.split()[-1]) > 0
            except Exception:
                return False

    async def list_monitored_chats(self, owner_tg_id: int) -> list[dict[str, Any]]:
        async with self._pool().acquire() as con:
            rows = await con.fetch(
                "SELECT * FROM monitored_chats WHERE owner_tg_id=$1 ORDER BY created_at",
                int(owner_tg_id),
            )
            return [dict(r) for r in rows]

    async def monitor_owners_for_chat(self, chat_id: int) -> list[dict[str, Any]]:
        async with self._pool().acquire() as con:
            rows = await con.fetch(
                "SELECT owner_tg_id, title FROM monitored_chats WHERE chat_id=$1 AND is_active=TRUE",
                int(chat_id),
            )
            return [dict(r) for r in rows]

    async def forget_user(self, tg_id: int) -> None:
        async with self._pool().acquire() as con:
            async with con.transaction():
                await con.execute("DELETE FROM deleted_events WHERE owner_tg_id=$1", tg_id)
                await con.execute("DELETE FROM cached_messages WHERE owner_tg_id=$1", tg_id)
                await con.execute("DELETE FROM business_connections WHERE owner_tg_id=$1", tg_id)
                await con.execute("DELETE FROM monitored_chats WHERE owner_tg_id=$1", tg_id)
                await con.execute("DELETE FROM payments WHERE user_id=$1", tg_id)
                await con.execute("UPDATE users SET subscription_until=NULL, free_deleted_today=0 WHERE tg_id=$1", tg_id)


    async def set_referrer(self, user_id: int, referrer_id: int) -> bool:
        if not user_id or not referrer_id or int(user_id) == int(referrer_id):
            return False
        async with self._pool().acquire() as con:
            ref_exists = await con.fetchval("SELECT 1 FROM users WHERE tg_id=$1", int(referrer_id))
            if not ref_exists:
                return False
            row = await con.fetchrow(
                """
                UPDATE users
                SET referrer_id=$2, referral_created_at=COALESCE(referral_created_at, NOW()), updated_at=NOW()
                WHERE tg_id=$1 AND referrer_id IS NULL
                RETURNING referrer_id
                """,
                int(user_id),
                int(referrer_id),
            )
            return bool(row)

    async def referral_stats(self, user_id: int) -> dict[str, Any]:
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                SELECT
                  (SELECT COUNT(*) FROM users WHERE referrer_id=$1) AS invited,
                  (SELECT COUNT(*) FROM referral_rewards WHERE referrer_id=$1) AS purchases,
                  (SELECT COALESCE(SUM(reward_amount_usd),0) FROM referral_rewards WHERE referrer_id=$1) AS earned,
                  (SELECT COALESCE(SUM(reward_amount_usd),0) FROM referral_rewards WHERE referrer_id=$1 AND status='available') AS available,
                  (SELECT COALESCE(SUM(reward_amount_usd),0) FROM referral_rewards WHERE referrer_id=$1 AND status='paid') AS paid
                """,
                int(user_id),
            )
            return dict(row) if row else {"invited": 0, "purchases": 0, "earned": 0, "available": 0, "paid": 0}

    async def admin_referral_stats(self) -> dict[str, Any]:
        async with self._pool().acquire() as con:
            totals = await con.fetchrow(
                """
                SELECT
                  (SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL) AS referred_users,
                  (SELECT COUNT(*) FROM referral_rewards) AS reward_count,
                  (SELECT COALESCE(SUM(purchase_amount_usd),0) FROM referral_rewards) AS referred_sales,
                  (SELECT COALESCE(SUM(reward_amount_usd),0) FROM referral_rewards) AS rewards_total,
                  (SELECT COALESCE(SUM(reward_amount_usd),0) FROM referral_rewards WHERE status='available') AS rewards_available,
                  (SELECT COALESCE(SUM(reward_amount_usd),0) FROM referral_rewards WHERE status='paid') AS rewards_paid
                """
            )
            top = await con.fetch(
                """
                SELECT u.tg_id, u.username, u.first_name, u.last_name,
                       COUNT(r.id) AS reward_count,
                       COALESCE(SUM(r.reward_amount_usd),0) AS earned,
                       COALESCE(SUM(CASE WHEN r.status='available' THEN r.reward_amount_usd ELSE 0 END),0) AS available,
                       (SELECT COUNT(*) FROM users invited WHERE invited.referrer_id=u.tg_id) AS invited
                FROM users u
                LEFT JOIN referral_rewards r ON r.referrer_id=u.tg_id
                WHERE u.tg_id IN (SELECT referrer_id FROM users WHERE referrer_id IS NOT NULL)
                   OR u.tg_id IN (SELECT referrer_id FROM referral_rewards WHERE referrer_id IS NOT NULL)
                GROUP BY u.tg_id
                ORDER BY earned DESC, invited DESC
                LIMIT 10
                """
            )
            result = dict(totals) if totals else {}
            result["top"] = [dict(r) for r in top]
            return result

    async def create_referral_reward_for_payment(self, payment: dict[str, Any]) -> dict[str, Any] | None:
        user_id = payment.get("user_id")
        payment_id = payment.get("id")
        amount = payment.get("amount_usd")
        if not user_id or not payment_id or amount is None:
            return None
        async with self._pool().acquire() as con:
            referrer_id = await con.fetchval("SELECT referrer_id FROM users WHERE tg_id=$1", int(user_id))
            if not referrer_id or int(referrer_id) == int(user_id):
                return None
            percent = Decimal(str(await self.get_setting("referral_percent", 30)))
            reward = Decimal(str(amount)) * percent / Decimal("100")
            row = await con.fetchrow(
                """
                INSERT INTO referral_rewards(referrer_id, buyer_id, payment_id, percent, purchase_amount_usd, reward_amount_usd, raw)
                VALUES($1, $2, $3, $4, $5, $6, $7::jsonb)
                ON CONFLICT(payment_id) DO NOTHING
                RETURNING *
                """,
                int(referrer_id),
                int(user_id),
                int(payment_id),
                percent,
                Decimal(str(amount)),
                reward.quantize(Decimal("0.01")),
                json.dumps({"source": "payment_paid"}),
            )
            return dict(row) if row else None

    # ----- Free trial -----

    async def grant_trial_if_new(self, tg_id: int) -> int | None:
        """Grant the one-time free trial to a brand-new user.

        Returns the number of trial days granted, or None if the user already
        used the trial or already has access. Atomic: the trial_granted flag is
        flipped in the same statement so it can never be granted twice, even on
        concurrent /start updates.
        """
        trial_days = int(await self.get_setting("trial_days", 2) or 0)
        if trial_days <= 0:
            return None
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                UPDATE users
                   SET trial_granted=TRUE,
                       subscription_until=GREATEST(COALESCE(subscription_until, NOW()), NOW()) + ($2::TEXT || ' days')::INTERVAL,
                       updated_at=NOW()
                 WHERE tg_id=$1 AND trial_granted=FALSE
                RETURNING subscription_until
                """,
                int(tg_id),
                str(trial_days),
            )
            return trial_days if row else None

    async def set_premium_flag(self, tg_id: int, is_premium: bool) -> None:
        async with self._pool().acquire() as con:
            await con.execute(
                "UPDATE users SET is_premium_user=$2, premium_checked_at=NOW(), updated_at=NOW() WHERE tg_id=$1",
                int(tg_id),
                bool(is_premium),
            )

    # ----- Referral (days-based) -----

    async def process_referral(self, referred_id: int, referrer_id: int, referred_is_premium: bool) -> dict[str, Any] | None:
        """Register a referral and grant bonus days.

        Antifraud rules enforced here:
          * no self-referrals;
          * the referrer must already exist;
          * each referred account is credited at most once (unique referred_id);
          * a user already linked to a referrer is never re-linked.

        Returns a dict describing the accrual (kind, bonus_days, counted) or None
        if the referral was rejected.
        """
        if not referred_id or not referrer_id or int(referred_id) == int(referrer_id):
            return None
        normal_days = int(await self.get_setting("ref_normal_days", 2) or 0)
        normal_limit = int(await self.get_setting("ref_normal_limit", 3) or 0)
        premium_days = int(await self.get_setting("ref_premium_days", 5) or 0)
        async with self._pool().acquire() as con:
            async with con.transaction():
                ref_exists = await con.fetchval("SELECT 1 FROM users WHERE tg_id=$1", int(referrer_id))
                if not ref_exists:
                    return None
                # One accrual per referred account, ever.
                already = await con.fetchval("SELECT 1 FROM referral_bonuses WHERE referred_id=$1", int(referred_id))
                if already:
                    return None
                # Link the user only if they are not linked yet.
                linked = await con.fetchrow(
                    """
                    UPDATE users
                       SET referrer_id=$2, referral_created_at=COALESCE(referral_created_at, NOW()), updated_at=NOW()
                     WHERE tg_id=$1 AND referrer_id IS NULL
                    RETURNING tg_id
                    """,
                    int(referred_id),
                    int(referrer_id),
                )
                if not linked:
                    return None

                if referred_is_premium:
                    kind = "premium"
                    bonus_days = premium_days
                    counted = True
                else:
                    kind = "normal"
                    used = await con.fetchval(
                        "SELECT COUNT(*) FROM referral_bonuses WHERE referrer_id=$1 AND kind='normal' AND bonus_days > 0",
                        int(referrer_id),
                    ) or 0
                    if normal_limit <= 0 or int(used) < normal_limit:
                        bonus_days = normal_days
                    else:
                        bonus_days = 0
                    counted = True

                await con.execute(
                    """
                    INSERT INTO referral_bonuses(referrer_id, referred_id, kind, is_premium, bonus_days, counted)
                    VALUES($1, $2, $3, $4, $5, $6)
                    """,
                    int(referrer_id),
                    int(referred_id),
                    kind,
                    bool(referred_is_premium),
                    int(bonus_days),
                    bool(counted),
                )
        granted_until = None
        if bonus_days > 0:
            granted_until = await self.grant_subscription(int(referrer_id), bonus_days)
        return {
            "referrer_id": int(referrer_id),
            "kind": kind,
            "is_premium": bool(referred_is_premium),
            "bonus_days": int(bonus_days),
            "granted_until": granted_until,
            "limit_reached": (kind == "normal" and bonus_days == 0),
        }

    async def add_manual_referral_bonus(self, referrer_id: int, days: int, admin_id: int | None = None, note: str | None = None) -> datetime | None:
        """Admin manual adjustment: record a bonus row and grant the days."""
        days = int(days)
        async with self._pool().acquire() as con:
            await con.execute(
                """
                INSERT INTO referral_bonuses(referrer_id, referred_id, kind, is_premium, bonus_days, counted, note, admin_id)
                VALUES($1, NULL, 'manual', FALSE, $2, FALSE, $3, $4)
                """,
                int(referrer_id),
                days,
                (note or "manual adjustment")[:200],
                int(admin_id) if admin_id else None,
            )
        if days > 0:
            return await self.grant_subscription(int(referrer_id), days)
        return None

    async def referral_user_stats(self, user_id: int) -> dict[str, Any]:
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                SELECT
                  (SELECT COUNT(*) FROM referral_bonuses WHERE referrer_id=$1 AND kind='normal') AS normal_count,
                  (SELECT COUNT(*) FROM referral_bonuses WHERE referrer_id=$1 AND kind='premium') AS premium_count,
                  (SELECT COALESCE(SUM(bonus_days),0) FROM referral_bonuses WHERE referrer_id=$1) AS bonus_days,
                  (SELECT subscription_until FROM users WHERE tg_id=$1) AS subscription_until
                """,
                int(user_id),
            )
            return dict(row) if row else {"normal_count": 0, "premium_count": 0, "bonus_days": 0, "subscription_until": None}

    async def admin_referral_overview(self) -> dict[str, Any]:
        async with self._pool().acquire() as con:
            totals = await con.fetchrow(
                """
                SELECT
                  (SELECT COUNT(DISTINCT referrer_id) FROM referral_bonuses) AS referrers,
                  (SELECT COUNT(*) FROM referral_bonuses WHERE referred_id IS NOT NULL) AS total_referrals,
                  (SELECT COUNT(*) FROM referral_bonuses WHERE kind='normal') AS normal_referrals,
                  (SELECT COUNT(*) FROM referral_bonuses WHERE kind='premium') AS premium_referrals,
                  (SELECT COALESCE(SUM(bonus_days),0) FROM referral_bonuses) AS bonus_days_total
                """
            )
            top = await con.fetch(
                """
                SELECT u.tg_id, u.username, u.first_name, u.last_name,
                       COUNT(*) FILTER (WHERE rb.kind='normal') AS normal_count,
                       COUNT(*) FILTER (WHERE rb.kind='premium') AS premium_count,
                       COALESCE(SUM(rb.bonus_days),0) AS bonus_days
                FROM referral_bonuses rb
                JOIN users u ON u.tg_id=rb.referrer_id
                GROUP BY u.tg_id
                ORDER BY bonus_days DESC, premium_count DESC
                LIMIT 10
                """
            )
            result = dict(totals) if totals else {}
            result["top"] = [dict(r) for r in top]
            return result

    # ----- Broadcast chats -----

    async def list_broadcast_chats(self, active_only: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM broadcast_chats"
        if active_only:
            sql += " WHERE is_active=TRUE"
        sql += " ORDER BY created_at"
        async with self._pool().acquire() as con:
            rows = await con.fetch(sql)
            return [dict(r) for r in rows]

    async def get_broadcast_chat(self, chat_id: int) -> dict[str, Any] | None:
        async with self._pool().acquire() as con:
            row = await con.fetchrow("SELECT * FROM broadcast_chats WHERE chat_id=$1", int(chat_id))
            return dict(row) if row else None

    async def add_broadcast_chat(self, chat_id: int, title: str | None = None, chat_type: str | None = None, added_by: int | None = None, interval_seconds: int | None = None) -> dict[str, Any]:
        interval = int(interval_seconds) if interval_seconds else int(await self.get_setting("broadcast_default_interval", 1800) or 1800)
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                INSERT INTO broadcast_chats(chat_id, title, chat_type, interval_seconds, added_by)
                VALUES($1, $2, $3, $4, $5)
                ON CONFLICT(chat_id) DO UPDATE SET
                    title=COALESCE(EXCLUDED.title, broadcast_chats.title),
                    chat_type=COALESCE(EXCLUDED.chat_type, broadcast_chats.chat_type),
                    is_active=TRUE,
                    updated_at=NOW()
                RETURNING *
                """,
                int(chat_id),
                title,
                chat_type,
                int(interval) if interval else 1800,
                int(added_by) if added_by else None,
            )
            return dict(row)

    async def remove_broadcast_chat(self, chat_id: int) -> None:
        async with self._pool().acquire() as con:
            await con.execute("DELETE FROM broadcast_chats WHERE chat_id=$1", int(chat_id))

    async def set_broadcast_interval(self, chat_id: int, interval_seconds: int) -> None:
        async with self._pool().acquire() as con:
            await con.execute(
                "UPDATE broadcast_chats SET interval_seconds=$2, updated_at=NOW() WHERE chat_id=$1",
                int(chat_id),
                max(30, int(interval_seconds)),
            )

    async def set_broadcast_active(self, chat_id: int, active: bool) -> None:
        async with self._pool().acquire() as con:
            await con.execute(
                "UPDATE broadcast_chats SET is_active=$2, updated_at=NOW() WHERE chat_id=$1",
                int(chat_id),
                bool(active),
            )

    async def update_broadcast_sent(self, chat_id: int, message_id: int | None) -> None:
        async with self._pool().acquire() as con:
            await con.execute(
                "UPDATE broadcast_chats SET last_message_id=$2, last_sent_at=NOW(), updated_at=NOW() WHERE chat_id=$1",
                int(chat_id),
                int(message_id) if message_id else None,
            )

    async def due_broadcast_chats(self) -> list[dict[str, Any]]:
        async with self._pool().acquire() as con:
            rows = await con.fetch(
                """
                SELECT * FROM broadcast_chats
                 WHERE is_active=TRUE
                   AND (last_sent_at IS NULL OR last_sent_at <= NOW() - (interval_seconds::TEXT || ' seconds')::INTERVAL)
                """
            )
            return [dict(r) for r in rows]

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

    async def extended_stats(self) -> dict[str, Any]:
        async with self._pool().acquire() as con:
            row = await con.fetchrow(
                """
                SELECT
                  (SELECT COUNT(*) FROM users) AS users_total,
                  (SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '1 day') AS users_today,
                  (SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '7 days') AS users_7d,
                  (SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '30 days') AS users_30d,
                  (SELECT COUNT(*) FROM users WHERE subscription_until > NOW()) AS subs_active,
                  (SELECT COUNT(*) FROM users WHERE subscription_until IS NOT NULL AND subscription_until <= NOW()) AS subs_expired,
                  (SELECT COUNT(*) FROM business_connections WHERE is_enabled=TRUE) AS connections_active,
                  (SELECT COUNT(*) FROM business_connections) AS connections_total,
                  (SELECT COUNT(*) FROM cached_messages) AS messages_total,
                  (SELECT COUNT(*) FROM cached_messages WHERE deleted_at IS NOT NULL) AS messages_deleted,
                  (SELECT COUNT(*) FROM cached_messages WHERE is_disappearing=TRUE) AS messages_disappearing,
                  (SELECT COUNT(*) FROM deleted_events) AS deletions_total,
                  (SELECT COUNT(*) FROM deleted_events WHERE delivered=TRUE) AS deletions_delivered,
                  (SELECT COALESCE(SUM(amount_usd),0) FROM payments WHERE status='paid') AS revenue_total,
                  (SELECT COALESCE(SUM(amount_usd),0) FROM payments WHERE status='paid' AND provider='ua_card') AS revenue_card,
                  (SELECT COALESCE(SUM(amount_usd),0) FROM payments WHERE status='paid' AND provider='cryptobot') AS revenue_crypto,
                  (SELECT COALESCE(SUM(amount_usd),0) FROM payments WHERE status='paid' AND provider='telegram_stars') AS revenue_stars,
                  (SELECT COALESCE(SUM(amount_usd),0) FROM payments WHERE status='paid' AND provider IN ('usdt_trc20','usdt_bep20')) AS revenue_usdt,
                  (SELECT COUNT(*) FROM payments WHERE status='paid') AS payments_paid_count,
                  (SELECT COUNT(*) FROM payments WHERE status IN ('pending','waiting_admin') AND provider <> 'cryptobot') AS payments_pending,
                  (SELECT COUNT(*) FROM payments WHERE status='rejected') AS payments_rejected,
                  (SELECT COALESCE(SUM(amount_usd),0) FROM payments WHERE status='paid' AND created_at >= NOW() - INTERVAL '1 day') AS revenue_today,
                  (SELECT COALESCE(SUM(amount_usd),0) FROM payments WHERE status='paid' AND created_at >= NOW() - INTERVAL '7 days') AS revenue_7d,
                  (SELECT COALESCE(SUM(amount_usd),0) FROM payments WHERE status='paid' AND created_at >= NOW() - INTERVAL '30 days') AS revenue_30d,
                  (SELECT COUNT(*) FROM user_keywords WHERE is_active=TRUE) AS keywords_active,
                  (SELECT COUNT(DISTINCT owner_tg_id) FROM user_keywords WHERE is_active=TRUE) AS keywords_users
                """
            )
            base = dict(row)

            plan_rows = await con.fetch(
                """
                SELECT pl.name_uk AS name, COUNT(p.id) AS cnt,
                       COALESCE(SUM(p.amount_usd),0) AS total
                FROM payments p
                JOIN plans pl ON pl.id=p.plan_id
                WHERE p.status='paid'
                GROUP BY pl.id, pl.name_uk, pl.position
                ORDER BY pl.position ASC
                """
            )
            base["plans_breakdown"] = [dict(r) for r in plan_rows]

            ref_row = await con.fetchrow(
                """
                SELECT
                  COUNT(*) FILTER (WHERE referred_id IS NOT NULL) AS total_referrals,
                  COUNT(*) FILTER (WHERE kind='normal') AS normal_referrals,
                  COUNT(*) FILTER (WHERE kind='premium') AS premium_referrals,
                  COALESCE(SUM(bonus_days),0) AS bonus_days_total
                FROM referral_bonuses
                """
            )
            base["referrals"] = dict(ref_row)
            return base

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

    async def get_setting_bool(self, key: str, default: bool = False) -> bool:
        val = await self.get_setting(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        return str(val).strip().lower() in {"1", "true", "yes", "on", "так", "да"}

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

    async def delete_template(self, key: str) -> None:
        async with self._pool().acquire() as con:
            await con.execute("DELETE FROM settings WHERE key=$1", f"template_{key}")

    async def record_sent_template(self, chat_id: int, message_id: int, template_key: str) -> None:
        """Remember that a specific bot message is a known reusable template.

        This makes `/edit` deterministic: when an admin replies to a bot screen,
        we resolve the exact template by (chat_id, message_id) instead of guessing
        from the (possibly heavily customized) message text.
        """
        if not message_id or not template_key:
            return
        try:
            async with self._pool().acquire() as con:
                await con.execute(
                    """
                    INSERT INTO sent_template_messages(chat_id, message_id, template_key)
                    VALUES($1, $2, $3)
                    ON CONFLICT(chat_id, message_id)
                    DO UPDATE SET template_key=EXCLUDED.template_key, created_at=NOW()
                    """,
                    int(chat_id),
                    int(message_id),
                    str(template_key),
                )
                # Lazy bounded cleanup so this table never grows without limit.
                if int(message_id) % 50 == 0:
                    await con.execute(
                        "DELETE FROM sent_template_messages WHERE created_at < NOW() - INTERVAL '60 days'"
                    )
        except Exception as exc:
            print("record_sent_template failed:", repr(exc))

    async def get_sent_template_key(self, chat_id: int, message_id: int) -> str | None:
        if not message_id:
            return None
        try:
            async with self._pool().acquire() as con:
                row = await con.fetchrow(
                    "SELECT template_key FROM sent_template_messages WHERE chat_id=$1 AND message_id=$2",
                    int(chat_id),
                    int(message_id),
                )
                return str(row["template_key"]) if row else None
        except Exception as exc:
            print("get_sent_template_key failed:", repr(exc))
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



def extract_file_metadata(msg: dict[str, Any]) -> tuple[str | None, int | None, str | None, bool]:
    """Return filename, file_size, mime_type, is_disappearing/timer-like.

    Telegram self-destruct media fields are not always documented in Bot API
    updates, so is_disappearing is intentionally defensive: it searches raw keys
    for ttl/self-destruct/expire hints.
    """
    kind, _text, _caption, _file_id = extract_message_content(msg)
    file_name: str | None = None
    file_size: int | None = None
    mime_type: str | None = None

    data: Any = None
    if kind == "photo":
        photos = msg.get("photo") or []
        data = photos[-1] if photos else None
        file_name = "photo.jpg"
    elif kind in {"video", "animation", "document", "audio", "voice", "video_note", "sticker"}:
        data = msg.get(kind)
        ext = {
            "video": "mp4",
            "animation": "gif",
            "document": "bin",
            "audio": "mp3",
            "voice": "ogg",
            "video_note": "mp4",
            "sticker": "webp",
        }.get(kind, "bin")
        file_name = f"vertuu_{kind}.{ext}"

    if isinstance(data, dict):
        if data.get("file_name"):
            file_name = str(data.get("file_name"))
        if data.get("file_size") is not None:
            try:
                file_size = int(data.get("file_size"))
            except Exception:
                file_size = None
        if data.get("mime_type"):
            mime_type = str(data.get("mime_type"))

    def has_timer_hint(value: Any) -> bool:
        if isinstance(value, dict):
            for key, val in value.items():
                low = str(key).lower()
                # Bot API / MTProto clients may expose self-destruct media with
                # different names depending on Telegram version. Keep this broad,
                # but only as a hint; normal media is still filtered in handlers.
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
                    "self_destruct",
                    "self-destruct",
                    "disappear",
                    "ttl",
                    "timer",
                )):
                    return True
                if has_timer_hint(val):
                    return True
        elif isinstance(value, list):
            return any(has_timer_hint(x) for x in value)
        return False

    return file_name, file_size, mime_type, has_timer_hint(msg)

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
