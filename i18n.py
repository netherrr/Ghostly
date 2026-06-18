from __future__ import annotations

SUPPORTED_LANGS = {'uk', 'ru', 'en'}

TEXTS: dict[str, dict[str, str]] = {'uk': {'start': '🛡 <b>{app}</b> — твій особистий захист Telegram-чатів.\n'
                 '\n'
                 '<b>Що я вмію:</b>\n'
                 '👻 показувати повідомлення, які співрозмовник видалив;\n'
                 '🔥 зберігати зникаючі медіа: кружки, голосові, фото, відео;\n'
                 '✏️ зберігати історію редагувань;\n'
                 '🔎 ловити важливі слова;\n'
                 '⚠️ попереджати про підозрілі скам-повідомлення.\n'
                 '\n'
                 '<b>Як це працює:</b> ти офіційно додаєш мене в Telegram Business. Я не прошу код входу, пароль або '
                 'session string.\n'
                 '\n'
                 'Натисни <b>🔌 Як підключити</b>, щоб увімкнути захист.',
        'choose_lang': '🌐 Обери мову:',
        'menu': '🏠 <b>Головне меню</b>\n\nОбери, що потрібно:',
        'status': '🛡 <b>Статус захисту</b>\n'
                  '\n'
                  '💎 <b>Підписка:</b> {sub_status}\n'
                  '🔌 <b>Business-підключення:</b> {business_status}\n'
                  '💬 <b>Збережено нових повідомлень:</b> {saved}\n'
                  '👻 <b>Видалених знайдено:</b> {deleted}\n'
                  '\n'
                  '{hint}',
        'sub_active': 'активна до {date}',
        'sub_free': 'Free / демо',
        'business_on': '✅ активне',
        'business_off': '❌ не підключено',
        'status_hint_connect': 'Щоб я почав працювати, додай мене в Telegram Business. Після цього я бачитиму тільки '
                               'нові повідомлення в дозволених чатах.',
        'status_hint_ok': '✅ Захист увімкнений. Для тесту попроси когось написати тобі повідомлення й видалити його — '
                          'я покажу копію тут.',
        'connect': '🔌 <b>Як підключити {app}</b>\n'
                   '\n'
                   '<b>1.</b> Відкрий Telegram → <b>Settings / Налаштування</b>.\n'
                   '<b>2.</b> Перейди в <b>Telegram Business / Бізнес</b>.\n'
                   '<b>3.</b> Відкрий <b>Chatbots / Чат-боти</b>.\n'
                   '<b>4.</b> Додай цього бота як <b>Business Chatbot</b>.\n'
                   '<b>5.</b> Обери, де бот має доступ: <b>усі чати</b> або <b>тільки вибрані</b>.\n'
                   '\n'
                   '<b>Після підключення:</b>\n'
                   '✅ я зберігатиму нові повідомлення;\n'
                   '👻 якщо їх видалять — покажу копію;\n'
                   '🔥 якщо видалять медіа — спробую зберегти фото/відео/голосове/кружок;\n'
                   '✏️ якщо їх змінять — покажу стару й нову версію.\n'
                   '\n'
                   '<b>Важливо:</b> старі видалені повідомлення до підключення відновити неможливо.',
        'plans_title': '💎 <b>Підписка</b>\n'
                       '\n'
                       'Free-режим працює як демо. Pro відкриває більше видалених повідомлень, історію редагувань, '
                       'ключові слова й антискам.\n'
                       '\n'
                       'Обери тариф:',
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
        'deleted_title': '👻 <b>Повідомлення видалили</b>',
        'edited_title': '✏️ <b>Повідомлення змінили</b>',
        'from': 'Автор',
        'chat': 'Чат',
        'text': 'Текст',
        'caption': 'Підпис',
        'media_saved': '📎 <b>Було медіа:</b> {kind}\n'
                       'Я надішлю збережений файл нижче, якщо Telegram дозволить його переслати.',
        'unknown_deleted': '👻 <b>Повідомлення видалили</b>\n'
                           '\n'
                           'Я побачив факт видалення, але не встиг зберегти вміст. Так буває, якщо повідомлення було '
                           'старе або бот ще не мав доступу до цього чату.',
        'free_limit': '🔒 <b>Free-ліміт на сьогодні вичерпано.</b>\n'
                      '\n'
                      'Оформи Pro, щоб бачити більше видалених повідомлень і історію редагувань без таких обмежень.',
        'privacy': '🔐 <b>Приватність і безпека</b>\n'
                   '\n'
                   '✅ Я не прошу код Telegram, пароль або session string.\n'
                   '✅ Працюю тільки через офіційне Telegram Business-підключення.\n'
                   '✅ Зберігаю тільки нові повідомлення після підключення.\n'
                   '✅ Старі видалені повідомлення не відновлюю й не обіцяю неможливого.\n'
                   '✅ Дані очищаються автоматично за правилами тарифу.\n'
                   '\n'
                   'Щоб видалити свої дані з бази бота, напиши /forget_me. Підключення в Telegram Business вимикається '
                   'вручну в налаштуваннях Telegram.',
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
        'business_connected': '✅ <b>Business-підключення активовано</b>\n'
                              '\n'
                              'Тепер я бачу нові повідомлення в дозволених чатах і зможу показувати те, що видалять '
                              'або відредагують.\n'
                              '\n'
                              '<b>Як перевірити:</b>\n'
                              '1. Попроси когось написати тобі тестове повідомлення.\n'
                              '2. Нехай він видалить його «для всіх».\n'
                              '3. Я надішлю копію сюди.\n'
                              '\n'
                              'Старі видалені повідомлення до підключення показати неможливо.',
        'business_disabled': '⚠️ Business-підключення вимкнено.',
        'unknown_command': 'Не зрозумів команду. Натисни меню нижче.'},
 'ru': {'start': '🛡 <b>{app}</b> — твоя личная защита Telegram-чатов.\n'
                 '\n'
                 '<b>Что я умею:</b>\n'
                 '👻 показывать сообщения, которые собеседник удалил;\n'
                 '🔥 сохранять исчезающие медиа: кружки, голосовые, фото, видео;\n'
                 '✏️ сохранять историю редактирований;\n'
                 '🔎 ловить важные слова;\n'
                 '⚠️ предупреждать о подозрительных скам-сообщениях.\n'
                 '\n'
                 '<b>Как это работает:</b> ты официально добавляешь меня в Telegram Business. Я не прошу код входа, '
                 'пароль или session string.\n'
                 '\n'
                 'Нажми <b>🔌 Как подключить</b>, чтобы включить защиту.',
        'choose_lang': '🌐 Выбери язык:',
        'menu': '🏠 <b>Главное меню</b>\n\nВыбери, что нужно:',
        'status': '🛡 <b>Статус защиты</b>\n'
                  '\n'
                  '💎 <b>Подписка:</b> {sub_status}\n'
                  '🔌 <b>Business-подключение:</b> {business_status}\n'
                  '💬 <b>Сохранено новых сообщений:</b> {saved}\n'
                  '👻 <b>Удалённых найдено:</b> {deleted}\n'
                  '\n'
                  '{hint}',
        'sub_active': 'активна до {date}',
        'sub_free': 'Free / демо',
        'business_on': '✅ активно',
        'business_off': '❌ не подключено',
        'status_hint_connect': 'Чтобы я начал работать, добавь меня в Telegram Business. После этого я буду видеть '
                               'только новые сообщения в разрешённых чатах.',
        'status_hint_ok': '✅ Защита включена. Для теста попроси кого-то написать тебе сообщение и удалить его — я '
                          'покажу копию здесь.',
        'connect': '🔌 <b>Как подключить {app}</b>\n'
                   '\n'
                   '<b>1.</b> Открой Telegram → <b>Settings / Настройки</b>.\n'
                   '<b>2.</b> Перейди в <b>Telegram Business / Бизнес</b>.\n'
                   '<b>3.</b> Открой <b>Chatbots / Чат-боты</b>.\n'
                   '<b>4.</b> Добавь этого бота как <b>Business Chatbot</b>.\n'
                   '<b>5.</b> Выбери, где бот имеет доступ: <b>все чаты</b> или <b>только выбранные</b>.\n'
                   '\n'
                   '<b>После подключения:</b>\n'
                   '✅ я буду сохранять новые сообщения;\n'
                   '👻 если их удалят — покажу копию;\n'
                   '🔥 если удалят медиа — попробую сохранить фото/видео/голосовое/кружок;\n'
                   '✏️ если их изменят — покажу старую и новую версию.\n'
                   '\n'
                   '<b>Важно:</b> старые удалённые сообщения до подключения восстановить невозможно.',
        'plans_title': '💎 <b>Подписка</b>\n'
                       '\n'
                       'Free-режим работает как демо. Pro открывает больше удалённых сообщений, историю '
                       'редактирований, ключевые слова и антискам.\n'
                       '\n'
                       'Выбери тариф:',
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
        'deleted_title': '👻 <b>Сообщение удалили</b>',
        'edited_title': '✏️ <b>Сообщение изменили</b>',
        'from': 'Автор',
        'chat': 'Чат',
        'text': 'Текст',
        'caption': 'Подпись',
        'media_saved': '📎 <b>Было медиа:</b> {kind}\n'
                       'Я отправлю сохранённый файл ниже, если Telegram позволит его переслать.',
        'unknown_deleted': '👻 <b>Сообщение удалили</b>\n'
                           '\n'
                           'Я увидел факт удаления, но не успел сохранить содержимое. Так бывает, если сообщение было '
                           'старое или бот ещё не имел доступа к этому чату.',
        'free_limit': '🔒 <b>Free-лимит на сегодня исчерпан.</b>\n'
                      '\n'
                      'Оформи Pro, чтобы видеть больше удалённых сообщений и историю редактирований без таких '
                      'ограничений.',
        'privacy': '🔐 <b>Приватность и безопасность</b>\n'
                   '\n'
                   '✅ Я не прошу код Telegram, пароль или session string.\n'
                   '✅ Работаю только через официальное Telegram Business-подключение.\n'
                   '✅ Сохраняю только новые сообщения после подключения.\n'
                   '✅ Старые удалённые сообщения не восстанавливаю и не обещаю невозможного.\n'
                   '✅ Данные очищаются автоматически по правилам тарифа.\n'
                   '\n'
                   'Чтобы удалить свои данные из базы бота, напиши /forget_me. Подключение в Telegram Business '
                   'выключается вручную в настройках Telegram.',
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
        'business_connected': '✅ <b>Business-подключение активировано</b>\n'
                              '\n'
                              'Теперь я вижу новые сообщения в разрешённых чатах и смогу показывать то, что удалят или '
                              'отредактируют.\n'
                              '\n'
                              '<b>Как проверить:</b>\n'
                              '1. Попроси кого-то написать тебе тестовое сообщение.\n'
                              '2. Пусть он удалит его «для всех».\n'
                              '3. Я отправлю копию сюда.\n'
                              '\n'
                              'Старые удалённые сообщения до подключения показать невозможно.',
        'business_disabled': '⚠️ Business-подключение выключено.',
        'unknown_command': 'Не понял команду. Нажми меню ниже.'},
 'en': {'start': '🛡 <b>{app}</b> is your personal Telegram chat protection.\n'
                 '\n'
                 '<b>What I can do:</b>\n'
                 '👻 show messages that were deleted;\n'
                 '🔥 save disappearing media: video notes, voice, photos, videos;\n'
                 '✏️ keep edit history;\n'
                 '🔎 track important keywords;\n'
                 '⚠️ warn about suspicious scam messages.\n'
                 '\n'
                 '<b>How it works:</b> you officially add me in Telegram Business. I never ask for login codes, '
                 'passwords, or session strings.\n'
                 '\n'
                 'Press <b>🔌 How to connect</b> to enable protection.',
        'choose_lang': '🌐 Choose language:',
        'menu': '🏠 <b>Main menu</b>\n\nChoose what you need:',
        'status': '🛡 <b>Protection status</b>\n'
                  '\n'
                  '💎 <b>Subscription:</b> {sub_status}\n'
                  '🔌 <b>Business connection:</b> {business_status}\n'
                  '💬 <b>New messages saved:</b> {saved}\n'
                  '👻 <b>Deleted found:</b> {deleted}\n'
                  '\n'
                  '{hint}',
        'sub_active': 'active until {date}',
        'sub_free': 'Free / demo',
        'business_on': '✅ active',
        'business_off': '❌ not connected',
        'status_hint_connect': 'To start protection, add me in Telegram Business. After that, I will only see new '
                               'messages in allowed chats.',
        'status_hint_ok': '✅ Protection is active. To test it, ask someone to send you a message and delete it — I '
                          'will show a copy here.',
        'connect': '🔌 <b>How to connect {app}</b>\n'
                   '\n'
                   '<b>1.</b> Open Telegram → <b>Settings</b>.\n'
                   '<b>2.</b> Go to <b>Telegram Business</b>.\n'
                   '<b>3.</b> Open <b>Chatbots</b>.\n'
                   '<b>4.</b> Add this bot as a <b>Business Chatbot</b>.\n'
                   '<b>5.</b> Choose access: <b>all chats</b> or <b>selected chats only</b>.\n'
                   '\n'
                   '<b>After connection:</b>\n'
                   '✅ I will save new messages;\n'
                   '👻 if they are deleted — I will show a copy;\n'
                   '🔥 if media is deleted — I will try to save photo/video/voice/video note;\n'
                   '✏️ if they are edited — I will show before and after.\n'
                   '\n'
                   '<b>Important:</b> deleted messages from before connection cannot be restored.',
        'plans_title': '💎 <b>Subscription</b>\n'
                       '\n'
                       'Free mode works as a demo. Pro unlocks more deleted messages, edit history, keywords, and '
                       'anti-scam alerts.\n'
                       '\n'
                       'Choose a plan:',
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
        'deleted_title': '👻 <b>Message deleted</b>',
        'edited_title': '✏️ <b>Message changed</b>',
        'from': 'Author',
        'chat': 'Chat',
        'text': 'Text',
        'caption': 'Caption',
        'media_saved': '📎 <b>Media was attached:</b> {kind}\n'
                       'I will send the saved file below if Telegram allows forwarding it.',
        'unknown_deleted': '👻 <b>Message deleted</b>\n'
                           '\n'
                           'I saw the deletion event, but did not save the content. This can happen if the message was '
                           'old or the bot did not have access to this chat yet.',
        'free_limit': '🔒 <b>Free daily limit reached.</b>\n'
                      '\n'
                      'Upgrade to Pro to see more deleted messages and edit history without these limits.',
        'privacy': '🔐 <b>Privacy and safety</b>\n'
                   '\n'
                   '✅ I never ask for Telegram login codes, passwords, or session strings.\n'
                   '✅ I only work through the official Telegram Business connection.\n'
                   '✅ I only save new messages after connection.\n'
                   '✅ I do not restore old deleted messages or promise impossible things.\n'
                   '✅ Data is cleaned automatically based on your plan.\n'
                   '\n'
                   'To delete your data from the bot database, send /forget_me. Telegram Business connection must be '
                   'disabled manually in Telegram settings.',
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
        'business_connected': '✅ <b>Business connection activated</b>\n'
                              '\n'
                              'I can now see new messages in allowed chats and show what gets deleted or edited.\n'
                              '\n'
                              '<b>How to test:</b>\n'
                              '1. Ask someone to send you a test message.\n'
                              '2. Ask them to delete it “for everyone”.\n'
                              '3. I will send the copy here.\n'
                              '\n'
                              'Deleted messages from before connection cannot be shown.',
        'business_disabled': '⚠️ Business connection disabled.',
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
        'admin_referrals': '🤝 Реферали'},
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
        'admin_referrals': '🤝 Рефералы'},
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
        'admin_referrals': '🤝 Referrals'}}


def tr(lang: str | None, key: str, **kwargs: object) -> str:
    lang = lang if lang in SUPPORTED_LANGS else 'uk'
    value = TEXTS[lang].get(key, TEXTS['uk'].get(key, key))
    return value.format(**kwargs)


def btn(lang: str | None, key: str) -> str:
    lang = lang if lang in SUPPORTED_LANGS else 'uk'
    return BUTTONS[lang].get(key, BUTTONS['uk'].get(key, key))
