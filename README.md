# ChatGuard — Telegram Business Anti-Delete Bot

Готовий production-MVP бота для Telegram Business: зберігає нові повідомлення після офіційного Business-підключення, показує видалені повідомлення, фіксує редагування для Pro-користувачів, має підписки, платежі й повністю кнопковий UX для клієнтів та адміна.

## Важливо по безпеці

Цей проєкт **не просить Telegram-код, пароль, QR-login або session string**. Користувач сам підключає бота через офіційний Telegram Business / Chatbots. Бот може показати тільки ті повідомлення, які отримав **після підключення**. Старі видалені повідомлення відновити неможливо.

## Що вже є

- UA / RU / EN інтерфейс.
- Кнопкове меню для клієнта:
  - статус захисту;
  - підписка;
  - як підключити;
  - останні видалені;
  - ключові слова;
  - приватність;
  - мова.
- Кнопкова адмін-панель:
  - статистика;
  - заявки на ручну оплату;
  - конструктор тарифів;
  - конструктор методів оплати;
  - видача доступу;
  - відкликання доступу;
  - налаштування лімітів і зберігання;
  - останні користувачі;
  - cleanup старих повідомлень.
- Telegram Business updates:
  - `business_connection`
  - `business_message`
  - `edited_business_message`
  - `deleted_business_messages`
- Збереження тексту, підписів і `file_id` медіа.
- Показ видалених повідомлень власнику акаунта.
- Історія редагувань для активних підписників.
- Free demo: ліміт видалених повідомлень на день + коротке зберігання.
- Підписки з тарифами у базі даних.
- CryptoBot автоматичні інвойси.
- Ручні методи: українська картка, USDT TRC20, USDT BEP20.
- Підтвердження/відхилення ручних оплат кнопками.
- Ключові слова для Pro-користувачів кнопками без команд.
- Базовий антискам-фільтр для підозрілих посилань і фраз.
- `/forget_me` для видалення даних користувача.
- PostgreSQL на Railway.
- FastAPI webhook server.

## 1. BotFather

1. Створи бота в `@BotFather`.
2. Скопіюй `BOT_TOKEN`.
3. Увімкни Business/Secretary mode для бота, якщо BotFather показує таку опцію.
4. Після деплою користувач підключає бота в Telegram: Settings → Telegram Business → Chatbots.

## 2. Railway

1. Створи новий Railway project.
2. Додай PostgreSQL.
3. Додай сервіс з GitHub repo.
4. В Variables встав:

```env
BOT_TOKEN=...
DATABASE_URL=${{Postgres.DATABASE_URL}}
ADMIN_IDS=твій_telegram_id
ADMIN_CHAT_ID=-1001234567890
WEBHOOK_BASE_URL=https://твій-домен.up.railway.app
WEBHOOK_SECRET=будь-який-довгий-рандомний-рядок
APP_NAME=ChatGuard
DEFAULT_LANG=ru
CRYPTO_PAY_TOKEN=...
```

`WEBHOOK_BASE_URL` має бути саме публічний домен Railway без `/` в кінці.

## 3. CryptoBot

1. Відкрий `@CryptoBot`.
2. Команда `/pay`.
3. Створи app.
4. Скопіюй Crypto Pay API token у `CRYPTO_PAY_TOKEN`.

Автоматична перевірка працює через кнопку “Перевірити оплату”. Додатково є endpoint `/cryptopay/webhook`, але для старту він не обовʼязковий.

## 4. Як адмін користується ботом

Напиши боту `/start`, потім натисни **👑 Адмін**.

В адмін-панелі все робиться кнопками:

- **📊 Статистика** — користувачі, активні підписки, business-звʼязки, повідомлення, видалення, оплати.
- **💳 Заявки** — ручні оплати з кнопками підтвердити/відхилити.
- **💎 Тарифи** — вибір тарифу, зміна ціни, днів, назв, описів і активності.
- **🏦 Оплати** — зміна назв/реквізитів картки, USDT TRC20, USDT BEP20, увімкнення/вимкнення методів.
- **🎁 Видати доступ** — вводиш `USER_ID DAYS`, наприклад `123456789 30`.
- **🚫 Забрати доступ** — вводиш `USER_ID`.
- **⚙️ Налаштування** — free-ліміт, зберігання для free/paid, cleanup.
- **👥 Юзери** — останні користувачі.

Команди залишені тільки як backup-режим для тебе:

```text
/stats
/plans_admin
/methods_admin
/grant 123456789 30
/revoke 123456789
/approve 15
/reject 15
/set_plan 1 price_usd 2.99
/set_method ua_card instructions_uk 💳 Картка: 4441 1111 1111 1111
/set_setting free_deleted_limit_per_day 10
/cleanup
```

## 5. Як клієнт користується ботом

Клієнту достатньо натиснути `/start` і далі користуватись кнопками:

- **🛡 Статус** — чи активна підписка і Business-підключення.
- **💎 Підписка** — вибір тарифу і способу оплати.
- **🔌 Як підключити** — інструкція по Telegram Business.
- **👻 Видалені** — останні знайдені видалені повідомлення.
- **🔎 Ключові слова** — додати/видалити слова кнопками.
- **🔐 Приватність** — пояснення, що бот не просить коди.
- **🌐 Мова** — UA/RU/EN.

## 6. Як це працює технічно

1. Коли користувач підключає бота в Telegram Business, приходить `business_connection`.
2. Коли в його дозволених чатах зʼявляється нове повідомлення, приходить `business_message`.
3. Бот зберігає `business_connection_id`, `chat_id`, `message_id`, текст/медіа `file_id`.
4. Коли повідомлення видаляють, Telegram надсилає `deleted_business_messages` з ID повідомлень.
5. Бот шукає їх у базі й надсилає власнику збережену копію.

## 7. Обмеження

- Старі видалені повідомлення до підключення не показує.
- Якщо повідомлення видалили швидше, ніж Telegram доставив боту update, вміст може не зберегтися.
- Медіа відправляється через Telegram `file_id`; якщо Telegram не дозволить переслати файл, бот покаже текстове повідомлення.
- Для Business-функцій може знадобитися Telegram Premium/Business на акаунті користувача.

## 8. Production-поради

Перед великим запуском бажано додати:

- Шифрування тексту повідомлень у базі.
- Окрему сторінку Terms / Privacy.
- Логи помилок у Sentry.
- Обмеження розміру медіа.
- Юридичний дисклеймер, що сервіс працює тільки для власних чатів користувача після його згоди.

## 9. Локальний запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8080
```

Для Telegram webhook локально потрібен публічний HTTPS URL, наприклад через ngrok/cloudflared.

## Update notes: payments proof + flexible admin

This build adds:

- manual payment proof flow: after pressing “I paid”, the user must send a receipt/screenshot/video/file/text;
- admin receives the manual payment request plus copied proof;
- admin payment card has a “Proof” button;
- fixed PostgreSQL `FOR UPDATE` approval bug;
- admin can create a new plan from the plan constructor;
- admin can edit plan price, duration, position, names, features and active status;
- admin can upload a guide video/media for “How to connect”;
- admin can set a guide video URL in settings.


## Admin rich edit with Premium emoji

The bot supports an admin-only `/edit` helper for polishing bot messages after deployment.

### Mode 1 — safer for Premium emoji and multiline text
1. Reply to any message sent by the bot with `/edit`.
2. Send the new text as a separate message.
3. The bot edits the replied bot message and preserves Telegram entities, including custom emoji.

### Mode 2 — quick inline edit
Reply to a bot message with:

```text
/edit New text here
```

This also supports custom emoji/entities that are placed after the `/edit` command.

Notes:
- Works only for admins from `ADMIN_IDS` / database admins.
- Works only with messages sent by this bot.
- Preserves inline keyboard buttons when possible.
- For Premium/custom emoji, use native Telegram emoji/entities in your admin message, not HTML tags.

## Rich text templates with Premium emoji

`/edit` edits a single bot message only. To make edited text persist for future users, use template mode:

1. Reply to the bot message you want to use as a base.
2. Send `/edit start` to edit and save the start/welcome template for your current language.
3. Send the new rich text with Telegram Premium emoji and formatting.
4. The bot edits the current message and saves it in DB. Future `/start` messages will use this template.

Supported template keys:

- `/edit start` — welcome message used on `/start`
- `/edit connect` — “How to connect” screen
- `/edit business` — message after Telegram Business connection is enabled
- `/edit privacy` — privacy screen

Quick mode also works:

`/edit start Your new text here`

Templates are language-specific. If your admin language is Ukrainian, `/edit start` saves `start_uk`. Switch language to RU/EN and repeat to save `start_ru` or `start_en`.

## Professional template editor: text + media

This build upgrades `/edit` into a reusable content/template editor.

You can now save not only rich text and Premium emoji, but also media screens:

- text-only templates;
- photo + caption;
- video + caption;
- GIF/animation + caption;
- document/file + caption.

Recommended workflow:

1. Open the screen you want to polish: `/start`, “How to connect”, Privacy, etc.
2. Reply to that bot message with `/edit`.
3. Send the final content as one message:
   - rich text with Premium emoji, or
   - photo/video/GIF/file with caption.
4. The bot updates the current screen and saves the reusable template in DB.

Explicit template commands:

- `/edit start` — save welcome screen for the current language;
- `/edit connect` — save “How to connect” screen;
- `/edit business` — save successful Business connection screen;
- `/edit privacy` — save privacy screen.

Important notes:

- Auto-detection now checks connect/privacy/business screens before the generic start screen, so “How to connect Ghostly” will no longer be saved as `start_uk` by mistake.
- Telegram media captions have a 1024-character limit. If your caption is longer, the bot sends media first and then sends the rich text with buttons as a separate message.
- To remove media from a template, reply to the media screen with `/edit` and send text-only replacement content.


### Timezone
Set `APP_TIMEZONE=Europe/Kyiv` in Railway Variables to display deleted-message times in Kyiv/local project time instead of UTC.


## Ghostly no-Premium Chat Automation rebuild

This build is rebuilt for the newer Telegram Chat Automation / Chatbots flow:

- UI no longer says Telegram Premium is required.
- Core protection is open by default: `FREE_FULL_ACCESS=true`.
- Start/status/connect texts use "Chat Automation / Автоматизація чатів" instead of mandatory "Telegram Business Premium".
- Normal voice/photo/video messages are cached silently and are not spammed immediately.
- Likely timer media is sent immediately only for captionless `photo`, `video`, and `video_note`; voice/audio/documents are excluded to avoid spam.
- If Telegram exposes explicit `ttl/self_destruct/expire` metadata, the bot treats it as timer media.
- Deleted media fallback uses strict short windows to avoid sending older wrong files.
- Raw update logs are off by default. Enable with `GHOSTLY_DEBUG_UPDATES=true`.
- Broad "send every media instantly" remains off unless `INSTANT_MEDIA_BACKUP_ALL=true`.


## Timer-only professional fix

This build forces the current timer-media defaults even on older databases:

- `timer_media_candidate_instant=true`
- `timer_media_candidate_types=["photo","video","video_note"]`

Immediate sending is limited to timer-like `photo`, `video`, and `video_note` only.
Voice/audio/documents/stickers are never sent immediately and are only shown after
a deletion event.

If Telegram exposes explicit ttl/self-destruct/timer fields, the bot uses them.
If Telegram hides the flag, the fallback treats captionless photo/video/video_note
as timer candidates so timer media is delivered immediately before expiry.

Useful env toggles:
- `TIMER_MEDIA_CAPTIONLESS_INSTANT=false` disables the fallback and uses only explicit timer hints.
- `DIRECT_TIMER_MEDIA_ENABLED=false` disables direct-message timer handling.
- `GHOSTLY_DEBUG_UPDATES=true` enables raw update diagnostics.


## Timer truth debug + no false warnings

This build keeps timer-only behavior but adds safe media-only logs by default:

- `GHOSTLY_MEDIA_DEBUG=true` logs whether Telegram sent `business_message`/`message` media and `file_id`.
- It does not log message text/captions.
- `NOTIFY_MISSED_TIMER_MEDIA=false` by default, so users do not see annoying failure warnings when Telegram sends only a deletion event without a file.
- `NOTIFY_DELETED_NO_CONTENT=false` by default: when Telegram reports a deletion the bot has no saved content for (the contact cleared chat history, or the chat auto-deletes old messages from before the connection), the event is recorded silently instead of spamming one "I saw a deletion but saved nothing" message per id. Set to `true` to get those notices back.
- If a timer photo/video is not delivered, check Railway for `GHOSTLY_MEDIA_DEBUG`, `Media cached bytes`, `Timer media instant not triggered`, and `Timer media instant delivery result`.


## Deterministic `/edit` (precise template editing)

Earlier builds guessed which screen a message belonged to by scanning its text for
keywords. After a screen was customized with Premium emoji, or when two screens
shared words, this could pick the wrong template — so `/edit` sometimes showed the
wrong "current text to copy" and saved your new content into a different screen.

This build makes `/edit` deterministic:

- Every screen the bot sends is recorded as `(chat_id, message_id) → template_key`
  in the new `sent_template_messages` table.
- When you reply to a bot message with `/edit`, the bot resolves the **exact**
  template by message id, with no guessing. The text you edit is the text that
  changes — and it stays changed for future users in that exact screen and language.
- Heuristic detection is kept only as a fallback for old messages sent before this
  build (just reopen the screen once to re-record it).
- Per-method payment screens stay isolated: editing the TON screen never touches
  card / USDT TRC20 / USDT BEP20.

The mapping table self-prunes (entries older than 60 days are removed lazily), so it
never grows unbounded.

### Full content support

`/edit` accepts any of the following as replacement content, in any language, with
full formatting and Premium custom emoji preserved through Telegram entities:

- rich text (bold, italic, underline, strikethrough, spoiler, code, blockquote, links);
- photo + caption;
- video + caption;
- GIF / animation + caption;
- document / file + caption;
- audio + caption;
- voice + caption;
- video note (round video, no caption);
- **stickers** (sent as a media-only screen, inline buttons preserved).

Workflow: open the screen → reply to it with `/edit` → send the new content as one
message. Switch the bot language and repeat to edit the same screen in UA / RU / EN.

---

# Оновлення 2026 — тарифи, тріал, реферали, розсилки

## 1. Тарифи

Активні підписки (єдиний повний доступ, різниця лише в тривалості):

| Період | Ціна |
|--------|------|
| 1 день | $0.15 |
| 3 дні | $0.25 |
| 7 днів | $0.40 |
| 1 місяць | $0.99 |
| 3 місяці | $1.99 |
| 6 місяців | $2.99 |
| 12 місяців | $3.99 |

Ціни задаються в `db.seed_defaults` і їх можна змінювати в адмін-панелі
(`👑 Адмін → 💎 Тарифи`). Старі Pro/Lifetime тарифи автоматично вимкнено.

## 2. Безкоштовний тріал + доступ

- Кожен новий користувач при першому `/start` отримує **1 день Premium** (один раз).
- Після завершення тріалу без активної підписки основний функціонал
  (видалені повідомлення, редагування, зникаючі медіа) **недоступний** — бот
  пропонує оформити підписку.
- Тривалість тріалу: налаштування `trial_days`. Гейтинг доступу:
  `access_gating_enabled` (можна вимкнути в адмін-панелі або env `FREE_FULL_ACCESS=true`).

## 3. Реферальна система (дні Premium)

Реферальне посилання: `t.me/<bot>?start=ref_<твій_id>` (кнопка `🤝 Реферали`).

- **Звичайний реферал** (без Telegram Premium): рефовод отримує **+2 дні**.
  Ліміт — **3 звичайних реферали** (макс. +6 днів). Далі реферали рахуються в
  статистику, але дні не нараховуються.
- **Premium-реферал** (з активним Telegram Premium): рефовод отримує **+5 днів**, без ліміту.
- Тип реферала визначається автоматично за `is_premium` з Telegram API.

Антифрод: самореферали заборонені; один акаунт зараховується лише один раз;
усі нарахування зберігаються в БД (`referral_bonuses`) і переживають перезапуск.

Користувач у розділі `🤝 Реферали` бачить: звичайних / Premium рефералів,
зароблені дні та залишок доступу.

Адмін: `👑 Адмін → 🤝 Реферали` — загальна статистика + топ рефоводів.
Ручне коригування: кнопка `✏️ Нарахувати дні` або команда
`/ref_bonus <user_id> <днів>`.

Налаштування: `ref_normal_days` (2), `ref_normal_limit` (3), `ref_premium_days` (5).

## 4. Автоматичні розсилки

Розділ `👑 Адмін → 📢 Розсилки`.

1. **Шаблон** — натисни `📝 Задати шаблон` і перешли/надішли боту повідомлення
   (текст, фото, відео, GIF, документ, аудіо, голос, відеоповідомлення, стікер,
   пересланий пост або **альбом** — перешли всі частини поспіль). Бот копіює його
   в чати в оригінальному вигляді.
2. **Додати чат** — або зроби бота **адміністратором** у групі/каналі (додасться
   автоматично), або натисни `➕ Додати чат` і перешли повідомлення з потрібного
   чату / надішли `chat_id`. Команда: `/broadcast_add <chat_id>`.
3. **Інтервал** — для кожного чату окремо: 5 хв / 15 хв / 30 хв / 1 год / 3 год або
   свій. Пауза/видалення — там само.
4. **Авто-видалення** — перед кожною новою розсилкою бот видаляє своє попереднє
   повідомлення, тож у чаті завжди лише одна актуальна розсилка.
5. `🚀 Розіслати зараз` або `/broadcast_now` — миттєва розсилка в усі активні чати.

Планувальник тікає кожні 30 c; інтервали й id останніх повідомлень зберігаються в
БД (`broadcast_chats`, `bc_last_*`), тож розклад переживає перезапуск.


## Адмін-чат для заявок і квитанцій (`ADMIN_CHAT_ID`)

За замовчуванням заявки на ручну оплату, квитанції/докази, підтвердження зірками
та кнопки «Підтвердити/Відхилити» приходять у **особисті** чати адмінів з
`ADMIN_IDS`. Щоб усе це йшло в **окремий адмін-чат** (групу) замість приватки:

1. Створи групу (або супергрупу) для адмінів.
2. Додай туди бота і **зроби його адміністратором** (щоб міг писати й копіювати
   квитанції).
3. Дізнайся `chat_id` групи (для супергруп він вигляду `-1001234567890`).
4. У Railway → Variables додай `ADMIN_CHAT_ID=-1001234567890` і передеплой.

Що зміниться:

- усі заявки на оплату, копії квитанцій/доказів і кнопка «Доказ» ідуть **тільки**
  в адмін-чат, а не в приватку кожного адміна;
- кнопки «✅ Підтвердити / ❌ Відхилити» працюють прямо в чаті — натиснути може
  лише адмін з `ADMIN_IDS`/бази (стороннім бот відповість «Немає доступу»);
- адмін-чат **не** додається в клієнтські розсилки автоматично: коли бот стає там
  адміном, він лише підтверджує, що це адмін-чат;
- якщо `ADMIN_CHAT_ID` не заданий — поведінка стара (приватки адмінів).


## `/edit`: усі сповіщення тепер із дужками для динамічних даних

Раніше частина сповіщень надсилалась напряму, із вже «запеченими» живими
значеннями (назва чату, автор, текст повідомлення, дата, тип/розмір медіа). Через
це `/edit` показував їх як звичайний текст — і їх можна було випадково
відредагувати, хоча для кожного користувача вони різні.

Тепер **усі** такі сповіщення проходять через єдиний редагований шар
(`editable_send` → шаблон `msg_<key>_<lang>`), тож динамічні частини показуються у
`{дужках}` і підставляються ботом автоматично. Редагувати можна лише статичний
текст/емодзі, а змінні лишаються живими:

- `keyword_alert` — `{keywords}`, `{chat}`, `{author}`, `{body}`;
- `scam_alert` — `{chat}`, `{author}`, `{body}`;
- `edited_alert` (зміна повідомлення) — `{chat}`, `{author}`, `{old}`, `{new}`;
- `deleted_no_content` (видалили, вміст не встигли зберегти) — `{chat}`;
- `alert_direct_media` / `alert_direct_timer` (медіа надіслане прямо в бота) —
  `{type}`, `{size}`;
- `crypto_paid` (підтвердження оплати/видачі доступу) — `{date}` тепер скрізь
  іде через редагований шар, а не напряму.

Робота як завжди: відкрий екран → відповідь на повідомлення бота командою
`/edit` → надішли новий контент. Лишай `{змінні}` там, де потрібні авто-дані.
