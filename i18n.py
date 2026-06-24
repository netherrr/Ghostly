from __future__ import annotations

SUPPORTED_LANGS = {'uk', 'ru', 'en'}

TEXTS: dict[str, dict[str, str]] = {'uk': {'start': '🕵️ <b>VERTUU SPY BOT</b>\n\n👁 Видалені повідомлення\n✏️ Редагування (було/стало)\n🔥 Зникаючі медіа — кружки, голосові, фото, відео\n🔎 Ключові слова\n\nПрацює через офіційну Автоматизацію чатів Telegram. Без кодів і паролів.\n\nНатисни <b>🔌 Як підключити</b>.',
        'choose_lang': '🌐 Обери мову:',
        'menu': '🏠 <b>Головне меню</b>\n\nОбери розділ:',
        'status': '🛡 <b>Статус захисту</b>\n\n💎 <b>Доступ:</b> {sub_status}\n🔌 <b>Автоматизація чатів:</b> {business_status}\n💬 <b>Збережено нових повідомлень:</b> {saved}\n👻 <b>Видалених знайдено:</b> {deleted}\n\n{hint}',
        'sub_active': 'активна до {date}',
        'sub_free': 'увімкнено / відкритий доступ',
        'business_on': '✅ підключено',
        'business_off': '❌ не підключено',
        'status_hint_connect': 'Щоб я почав працювати, додай мене в Telegram → профіль → Змінити → Автоматизація чатів. Після цього я бачитиму тільки нові повідомлення в дозволених чатах.',
        'status_hint_ok': '✅ Захист увімкнений. Для тесту попроси когось написати повідомлення й видалити його — я покажу копію тут.',
        'connect': '🔌 <b>Підключення за 3 кроки</b>\n\n1. Профіль Telegram → <b>Змінити</b>\n2. <b>Автоматизація чатів</b>\n3. Додай <b>@{bot_username}</b> і обери чати\n\n✅ Без кодів і паролів\n✅ Онови Telegram до останньої версії\n⚠️ Старі видалені повідомлення (до підключення) недоступні',
        'plans_title': '💎 <b>Тарифи VERTUU SPY BOT</b>\n\nОбери план підписки:',
        'plan_line': '<b>{name}</b> — ${price} / {days}\n{features}',
        'choose_payment': '💳 <b>Оплата тарифу</b>\n'
                          '\n'
                          'Тариф: <b>{plan}</b>\n'
                          'Сума: <b>${price}</b>\n'
                          '\n'
                          'Обери спосіб оплати:',
        'payment_crypto_created': '✅ Рахунок CryptoBot створено.\n'
                                  '\n'
                                  'Сума: <b>${amount}</b>\n'
                                  'Після оплати натисни «Перевірити оплату».\n'
                                  '\n'
                                  '{url}',
        'payment_manual': '💳 <b>Ручна оплата</b>\n'
                          '\n'
                          '💎 <b>Тариф:</b> {plan}\n'
                          '💰 <b>Сума:</b> ${amount}\n'
                          '\n'
                          '{instructions}\n'
                          '\n'
                          '<b>Після оплати:</b> натисни «Я оплатив» і надішли скрін/квитанцію/файл/відео. Адмін '
                          'перевірить оплату й активує доступ.',
        'paid_wait_admin': '✅ Дякую, квитанцію отримано.\n'
                           '\n'
                           'Заявку вже відправлено адміну. Доступ активують після перевірки оплати.',
        'crypto_paid': '✅ Оплату підтверджено.\n'
                       '\n'
                       'Підписка активна до: <b>{date}</b>\n'
                       '\n'
                       'Тепер можеш користуватися Pro-функціями.',
        'crypto_not_paid': 'Поки не бачу оплату. Спробуй ще раз після підтвердження платежу.',
        'payment_error': 'Не вийшло створити/перевірити платіж. Напиши підтримці або спробуй інший спосіб.',
        'deleted_title': '👁 <b>Повідомлення видалили</b>',
        'edited_title': '✏️ <b>Повідомлення змінили</b>',
        'from': 'Автор',
        'chat': 'Чат',
        'text': 'Текст',
        'caption': 'Підпис',
        'media_saved': '📎 <b>Було медіа:</b> {kind}\n'
                       'Я надішлю збережений файл нижче, якщо Telegram дозволить його переслати.',
        'unknown_deleted': '👁 <b>Повідомлення видалили</b>\n'
                           '\n'
                           'Я побачив факт видалення, але не встиг зберегти вміст. Так буває, якщо повідомлення було '
                           'старе або бот ще не мав доступу до цього чату.',
        'free_limit': '🔒 <b>Free-ліміт на сьогодні вичерпано.</b>\n'
                      '\n'
                      'Оформи Pro, щоб бачити більше видалених повідомлень і історію редагувань без таких обмежень.',
        'privacy': '🔐 <b>Приватність</b>\n'
                   '\n'
                   '✅ Без кодів, паролів і session string\n'
                   '✅ Лише офіційне Telegram Business-підключення\n'
                   '✅ Зберігаються тільки нові повідомлення\n'
                   '✅ Авто-очищення за тарифом\n'
                   '\n'
                   '/forget_me — видалити свої дані з бота.',
        'forgotten': '✅ Твої збережені повідомлення, платежі та business-звʼязки видалено з бази бота. Підключення в '
                     'Telegram Business треба вимкнути вручну в налаштуваннях Telegram.',
        'admin': '👑 <b>Адмін-панель</b>\n'
                 '\n'
                 'Керуй ботом кнопками: тарифи, ціни, методи оплати, ручні заявки, доступи, статистика і налаштування. '
                 'Команди залишені тільки як запасний технічний режим.',
        'not_admin': 'Немає доступу.',
        'stats': '📊 <b>Статистика</b>\n'
                 '\n'
                 'Користувачів: {users}\n'
                 'Активних підписок: {active_subs}\n'
                 'Business-звʼязків: {connections}\n'
                 'Збережено повідомлень: {messages}\n'
                 'Видалень: {deletions}\n'
                 'Оплачено: ${paid}\n'
                 'Очікують ручної перевірки: {pending}',
        'business_connected': '✅ <b>Підключено!</b>\n'
                              '\n'
                              'Слідкую за новими повідомленнями. Видалять або змінять — надішлю копію сюди.\n'
                              '\n'
                              'Перевірка: попроси когось надіслати повідомлення й видалити «для всіх».',
        'business_disabled': '⚠️ Business-підключення вимкнено.',
        'trial_granted': '🎁 <b>{days} день Premium активовано.</b>\nДоступ до всіх функцій увімкнено.',
        'access_locked': '🔒 <b>Доступ обмежено.</b>\nПробний період завершився. Оформи підписку, щоб користуватися ботом.',
        'ref_earned_normal': '🤝 <b>+{days} дн. Premium</b> за нового реферала.',
        'ref_earned_premium': '💎 <b>+{days} дн. Premium</b> за Premium-реферала.',
        'ref_limit_reached': '🤝 Новий реферал зараховано. Ліміт бонусних днів за звичайних рефералів вичерпано.',
        'unknown_command': 'Не зрозумів команду. Натисни меню нижче.'},
 'ru': {'start': '🕵️ <b>VERTUU SPY BOT</b>\n\n👁 Удалённые сообщения\n✏️ Редактирование (было/стало)\n🔥 Исчезающие медиа — кружки, голосовые, фото, видео\n🔎 Ключевые слова\n\nРаботает через официальную Автоматизацию чатов Telegram. Без кодов и паролей.\n\nНажми <b>🔌 Как подключить</b>.',
        'choose_lang': '🌐 Выбери язык:',
        'menu': '🏠 <b>Главное меню</b>\n\nВыбери раздел:',
        'status': '🛡 <b>Статус защиты</b>\n\n💎 <b>Доступ:</b> {sub_status}\n🔌 <b>Автоматизация чатов:</b> {business_status}\n💬 <b>Сохранено новых сообщений:</b> {saved}\n👻 <b>Удалённых найдено:</b> {deleted}\n\n{hint}',
        'sub_active': 'активна до {date}',
        'sub_free': 'включено / открытый доступ',
        'business_on': '✅ подключено',
        'business_off': '❌ не подключено',
        'status_hint_connect': 'Чтобы я начал работать, добавь меня в Telegram → профиль → Изм. → Автоматизация чатов. После этого я буду видеть только новые сообщения в разрешённых чатах.',
        'status_hint_ok': '✅ Защита включена. Для теста попроси кого-то написать сообщение и удалить его — я покажу копию здесь.',
        'connect': '🔌 <b>Подключение за 3 шага</b>\n\n1. Профиль Telegram → <b>Изм.</b>\n2. <b>Автоматизация чатов</b>\n3. Добавь <b>@{bot_username}</b> и выбери чаты\n\n✅ Без кодов и паролей\n✅ Обнови Telegram до последней версии\n⚠️ Старые удалённые сообщения (до подключения) недоступны',
        'plans_title': '💎 <b>Тарифы VERTUU SPY BOT</b>\n\nВыбери план подписки:',
        'plan_line': '<b>{name}</b> — ${price} / {days}\n{features}',
        'choose_payment': '💳 <b>Оплата тарифа</b>\n'
                          '\n'
                          'Тариф: <b>{plan}</b>\n'
                          'Сумма: <b>${price}</b>\n'
                          '\n'
                          'Выбери способ оплаты:',
        'payment_crypto_created': '✅ Счёт CryptoBot создан.\n'
                                  '\n'
                                  'Сумма: <b>${amount}</b>\n'
                                  'После оплаты нажми «Проверить оплату».\n'
                                  '\n'
                                  '{url}',
        'payment_manual': '💳 <b>Ручная оплата</b>\n'
                          '\n'
                          '💎 <b>Тариф:</b> {plan}\n'
                          '💰 <b>Сумма:</b> ${amount}\n'
                          '\n'
                          '{instructions}\n'
                          '\n'
                          '<b>После оплаты:</b> нажми «Я оплатил» и отправь скрин/квитанцию/файл/видео. Админ проверит '
                          'оплату и активирует доступ.',
        'paid_wait_admin': '✅ Спасибо, квитанция получена.\n'
                           '\n'
                           'Заявка уже отправлена админу. Доступ активируют после проверки оплаты.',
        'crypto_paid': '✅ Оплата подтверждена.\n'
                       '\n'
                       'Подписка активна до: <b>{date}</b>\n'
                       '\n'
                       'Теперь можешь пользоваться Pro-функциями.',
        'crypto_not_paid': 'Пока не вижу оплату. Попробуй ещё раз после подтверждения платежа.',
        'payment_error': 'Не получилось создать/проверить платёж. Напиши поддержке или попробуй другой способ.',
        'deleted_title': '👁 <b>Сообщение удалили</b>',
        'edited_title': '✏️ <b>Сообщение изменили</b>',
        'from': 'Автор',
        'chat': 'Чат',
        'text': 'Текст',
        'caption': 'Подпись',
        'media_saved': '📎 <b>Было медиа:</b> {kind}\n'
                       'Я отправлю сохранённый файл ниже, если Telegram позволит его переслать.',
        'unknown_deleted': '👁 <b>Сообщение удалили</b>\n'
                           '\n'
                           'Я увидел факт удаления, но не успел сохранить содержимое. Так бывает, если сообщение было '
                           'старое или бот ещё не имел доступа к этому чату.',
        'free_limit': '🔒 <b>Free-лимит на сегодня исчерпан.</b>\n'
                      '\n'
                      'Оформи Pro, чтобы видеть больше удалённых сообщений и историю редактирований без таких '
                      'ограничений.',
        'privacy': '🔐 <b>Приватность</b>\n'
                   '\n'
                   '✅ Без кодов, паролей и session string\n'
                   '✅ Только официальное Telegram Business-подключение\n'
                   '✅ Сохраняются только новые сообщения\n'
                   '✅ Авто-очистка по тарифу\n'
                   '\n'
                   '/forget_me — удалить свои данные из бота.',
        'forgotten': '✅ Твои сохранённые сообщения, платежи и business-связи удалены из базы бота. Подключение в '
                     'Telegram Business нужно выключить вручную в настройках Telegram.',
        'admin': '👑 <b>Админ-панель</b>\n'
                 '\n'
                 'Управляй ботом кнопками: тарифы, цены, методы оплаты, ручные заявки, доступы, статистика и '
                 'настройки. Команды оставлены только как запасной технический режим.',
        'not_admin': 'Нет доступа.',
        'stats': '📊 <b>Статистика</b>\n'
                 '\n'
                 'Пользователей: {users}\n'
                 'Активных подписок: {active_subs}\n'
                 'Business-связей: {connections}\n'
                 'Сохранено сообщений: {messages}\n'
                 'Удалений: {deletions}\n'
                 'Оплачено: ${paid}\n'
                 'Ожидают ручной проверки: {pending}',
        'business_connected': '✅ <b>Подключено!</b>\n'
                              '\n'
                              'Слежу за новыми сообщениями. Удалят или изменят — пришлю копию сюда.\n'
                              '\n'
                              'Проверка: попроси кого-то отправить сообщение и удалить «для всех».',
        'business_disabled': '⚠️ Business-подключение выключено.',
        'trial_granted': '🎁 <b>{days} день Premium активирован.</b>\nДоступ ко всем функциям включён.',
        'access_locked': '🔒 <b>Доступ ограничен.</b>\nПробный период закончился. Оформи подписку, чтобы пользоваться ботом.',
        'ref_earned_normal': '🤝 <b>+{days} дн. Premium</b> за нового реферала.',
        'ref_earned_premium': '💎 <b>+{days} дн. Premium</b> за Premium-реферала.',
        'ref_limit_reached': '🤝 Новый реферал засчитан. Лимит бонусных дней за обычных рефералов исчерпан.',
        'unknown_command': 'Не понял команду. Нажми меню ниже.'},
 'en': {'start': '🕵️ <b>VERTUU SPY BOT</b>\n\n👁 Deleted messages\n✏️ Edits (before/after)\n🔥 Disappearing media — video notes, voice, photos, videos\n🔎 Keywords\n\nWorks through official Telegram Chat Automation. No codes or passwords.\n\nPress <b>🔌 How to connect</b>.',
        'choose_lang': '🌐 Choose language:',
        'menu': '🏠 <b>Main menu</b>\n\nChoose a section:',
        'status': '🛡 <b>Protection status</b>\n\n💎 <b>Access:</b> {sub_status}\n🔌 <b>Chat Automation:</b> {business_status}\n💬 <b>New messages saved:</b> {saved}\n👻 <b>Deleted found:</b> {deleted}\n\n{hint}',
        'sub_active': 'active until {date}',
        'sub_free': 'enabled / open access',
        'business_on': '✅ connected',
        'business_off': '❌ not connected',
        'status_hint_connect': 'To start protection, add me in Telegram → profile → Edit → Chat Automation. After that I only see new messages in allowed chats.',
        'status_hint_ok': '✅ Protection is on. Ask someone to send you a message and delete it — I will show a copy here.',
        'connect': '🔌 <b>Connect in 3 steps</b>\n\n1. Telegram profile → <b>Edit</b>\n2. <b>Chat Automation</b>\n3. Add <b>@{bot_username}</b> and choose chats\n\n✅ No codes or passwords\n✅ Update Telegram to the latest version\n⚠️ Old deleted messages (before connection) are unavailable',
        'plans_title': '💎 <b>VERTUU SPY BOT Plans</b>\n\nChoose your subscription:',
        'plan_line': '<b>{name}</b> — ${price} / {days}\n{features}',
        'choose_payment': '💳 <b>Plan payment</b>\n'
                          '\n'
                          'Plan: <b>{plan}</b>\n'
                          'Amount: <b>${price}</b>\n'
                          '\n'
                          'Choose payment method:',
        'payment_crypto_created': '✅ CryptoBot invoice created.\n'
                                  '\n'
                                  'Amount: <b>${amount}</b>\n'
                                  'After payment, press “Check payment”.\n'
                                  '\n'
                                  '{url}',
        'payment_manual': '💳 <b>Manual payment</b>\n'
                          '\n'
                          '💎 <b>Plan:</b> {plan}\n'
                          '💰 <b>Amount:</b> ${amount}\n'
                          '\n'
                          '{instructions}\n'
                          '\n'
                          '<b>After payment:</b> press “I paid” and send a screenshot/receipt/file/video. Admin will '
                          'verify and activate access.',
        'paid_wait_admin': '✅ Thank you, receipt received.\n'
                           '\n'
                           'The request has been sent to admin. Access will be activated after verification.',
        'crypto_paid': '✅ Payment confirmed.\n'
                       '\n'
                       'Subscription active until: <b>{date}</b>\n'
                       '\n'
                       'You can now use Pro features.',
        'crypto_not_paid': 'I do not see the payment yet. Try again after the payment is confirmed.',
        'payment_error': 'Could not create/check payment. Contact support or try another method.',
        'deleted_title': '👁 <b>Message deleted</b>',
        'edited_title': '✏️ <b>Message changed</b>',
        'from': 'Author',
        'chat': 'Chat',
        'text': 'Text',
        'caption': 'Caption',
        'media_saved': '📎 <b>Media was attached:</b> {kind}\n'
                       'I will send the saved file below if Telegram allows forwarding it.',
        'unknown_deleted': '👁 <b>Message deleted</b>\n'
                           '\n'
                           'I detected a deletion but did not save the content. This can happen if the message was '
                           'old or the bot did not have access to this chat yet.',
        'free_limit': '🔒 <b>Free daily limit reached.</b>\n'
                      '\n'
                      'Upgrade to Pro to see more deleted messages and edit history without these limits.',
        'privacy': '🔐 <b>Privacy</b>\n'
                   '\n'
                   '✅ No codes, passwords, or session strings\n'
                   '✅ Official Telegram Business connection only\n'
                   '✅ Only new messages are saved\n'
                   '✅ Auto-cleanup based on your plan\n'
                   '\n'
                   '/forget_me — delete your data from the bot.',
        'forgotten': '✅ Your saved messages, payments and business connections were removed from the bot database. You '
                     'must disable Telegram Business connection manually in Telegram settings.',
        'admin': '👑 <b>Admin panel</b>\n'
                 '\n'
                 'Use buttons to manage plans, prices, payment methods, manual requests, access, stats and settings. '
                 'Commands remain only as a backup technical mode.',
        'not_admin': 'Access denied.',
        'stats': '📊 <b>Stats</b>\n'
                 '\n'
                 'Users: {users}\n'
                 'Active subscriptions: {active_subs}\n'
                 'Business connections: {connections}\n'
                 'Saved messages: {messages}\n'
                 'Deletions: {deletions}\n'
                 'Paid: ${paid}\n'
                 'Manual pending: {pending}',
        'business_connected': '✅ <b>Connected!</b>\n'
                              '\n'
                              'I now watch new messages. If they are deleted or edited, I send a copy here.\n'
                              '\n'
                              'Test: ask someone to send a message and delete it “for everyone”.',
        'business_disabled': '⚠️ Business connection disabled.',
        'trial_granted': '🎁 <b>{days}-day Premium activated.</b>\nAll features unlocked.',
        'access_locked': '🔒 <b>Access locked.</b>\nYour trial has ended. Subscribe to keep using the bot.',
        'ref_earned_normal': '🤝 <b>+{days}d Premium</b> for a new referral.',
        'ref_earned_premium': '💎 <b>+{days}d Premium</b> for a Premium referral.',
        'ref_limit_reached': '🤝 New referral counted. Bonus-day limit for normal referrals reached.',
        'unknown_command': 'I did not understand the command. Use the menu below.'}}

BUTTONS: dict[str, dict[str, str]] = {'uk': {'status': '🛡 Статус',
        'plans': '💎 Підписка',
        'connect': '🔌 Як підключити',
        'lang': '🌐 Мова',
        'privacy': '🔐 Приватність',
        'admin': '👑 Адмін',
        'back': '⬅️ Назад',
        'buy': 'Купити',
        'check_payment': '✅ Перевірити оплату',
        'i_paid': 'Я оплатив',
        'last_deleted': '👻 Видалені',
        'keywords': '🔎 Ключові слова',
        'add_keyword': '➕ Додати слово',
        'delete_keyword': '🗑 Видалити слово',
        'cancel': '✖️ Скасувати',
        'admin_stats': '📊 Статистика',
        'admin_pending': '💳 Заявки',
        'admin_plans': '💎 Тарифи',
        'admin_methods': '🏦 Оплати',
        'admin_grant': '🎁 Видати доступ',
        'admin_revoke': '🚫 Забрати доступ',
        'admin_settings': '⚙️ Налаштування',
        'admin_users': '👥 Юзери',
        'referrals': '🤝 Реферали',
        'admin_referrals': '🤝 Реферали',
        'admin_broadcast': '📢 Розсилки'},
 'ru': {'status': '🛡 Статус',
        'plans': '💎 Подписка',
        'connect': '🔌 Как подключить',
        'lang': '🌐 Язык',
        'privacy': '🔐 Приватность',
        'admin': '👑 Админ',
        'back': '⬅️ Назад',
        'buy': 'Купить',
        'check_payment': '✅ Проверить оплату',
        'i_paid': 'Я оплатил',
        'last_deleted': '👻 Удалённые',
        'keywords': '🔎 Ключевые слова',
        'add_keyword': '➕ Добавить слово',
        'delete_keyword': '🗑 Удалить слово',
        'cancel': '✖️ Отмена',
        'admin_stats': '📊 Статистика',
        'admin_pending': '💳 Заявки',
        'admin_plans': '💎 Тарифы',
        'admin_methods': '🏦 Оплаты',
        'admin_grant': '🎁 Выдать доступ',
        'admin_revoke': '🚫 Забрать доступ',
        'admin_settings': '⚙️ Настройки',
        'admin_users': '👥 Юзеры',
        'referrals': '🤝 Рефералы',
        'admin_referrals': '🤝 Рефералы',
        'admin_broadcast': '📢 Рассылки'},
 'en': {'status': '🛡 Status',
        'plans': '💎 Plan',
        'connect': '🔌 How to connect',
        'lang': '🌐 Language',
        'privacy': '🔐 Privacy',
        'admin': '👑 Admin',
        'back': '⬅️ Back',
        'buy': 'Buy',
        'check_payment': '✅ Check payment',
        'i_paid': 'I paid',
        'last_deleted': '👻 Deleted',
        'keywords': '🔎 Keywords',
        'add_keyword': '➕ Add keyword',
        'delete_keyword': '🗑 Delete keyword',
        'cancel': '✖️ Cancel',
        'admin_stats': '📊 Stats',
        'admin_pending': '💳 Requests',
        'admin_plans': '💎 Plans',
        'admin_methods': '🏦 Payments',
        'admin_grant': '🎁 Grant access',
        'admin_revoke': '🚫 Revoke access',
        'admin_settings': '⚙️ Settings',
        'admin_users': '👥 Users',
        'referrals': '🤝 Referrals',
        'admin_referrals': '🤝 Referrals',
        'admin_broadcast': '📢 Broadcasts'}}


def tr(lang: str | None, key: str, **kwargs: object) -> str:
    lang = lang if lang in SUPPORTED_LANGS else 'uk'
    value = TEXTS[lang].get(key, TEXTS['uk'].get(key, key))
    return value.format(**kwargs)


def btn(lang: str | None, key: str) -> str:
    lang = lang if lang in SUPPORTED_LANGS else 'uk'
    return BUTTONS[lang].get(key, BUTTONS['uk'].get(key, key))
