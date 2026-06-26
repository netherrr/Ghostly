from __future__ import annotations

SUPPORTED_LANGS = {'uk', 'ru', 'en'}

TEXTS: dict[str, dict[str, str]] = {'uk': {'start': '🕵️ <b>VERTUU SPY BOT</b>\n\nЗберігаю видалені повідомлення, правки та зникаючі медіа у твоїх чатах.\n\n👇 Натисни «🔌 Підключити», щоб налаштувати за 30 секунд.',
        'choose_lang': '🌐 Обери мову:',
        'menu': '🏠 <b>Головне меню</b>\n\nОбери розділ:',
        'status': '🛡 <b>Статус захисту</b>\n\n💎 <b>Доступ:</b> {sub_status}\n🔌 <b>Автоматизація чатів:</b> {business_status}\n💬 <b>Збережено нових повідомлень:</b> {saved}\n👻 <b>Видалених знайдено:</b> {deleted}\n\n{hint}',
        'sub_active': 'активна до {date}',
        'sub_free': 'увімкнено / відкритий доступ',
        'business_on': '✅ підключено',
        'business_off': '❌ не підключено',
        'status_hint_connect': 'Щоб я почав працювати, додай мене в Telegram → профіль → Змінити → Автоматизація чатів. Після цього я бачитиму тільки нові повідомлення в дозволених чатах.',
        'status_hint_ok': '✅ Захист увімкнений. Для тесту попроси когось написати повідомлення й видалити його — я покажу копію тут.',
        'connect': '🔌 <b>Підключення за 3 кроки</b>\n\n1️⃣ Telegram → <b>Налаштування</b> → <b>Telegram Business</b>\n2️⃣ Відкрий <b>Чат-боти</b>\n3️⃣ Встав <code>@{bot_username}</code> і обери чати\n\n✅ Без кодів, паролів і session string\n💡 Натисни на <code>@{bot_username}</code>, щоб скопіювати',
        'plans_title': '💎 <b>Тарифи VERTUU SPY BOT</b>\n\nОбери відповідний тариф:',
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
        'invoice_stars_support': '⭐ <b>Рахунок створено.</b>\n\nДо відправки: <b>{stars} ⭐</b>\nПісля підтвердження зірки зарахуються на баланс бота.',
        'invoice_stars_plan': '⭐ <b>Рахунок у Telegram Stars створено.</b>\n\nДо сплати: <b>{stars} ⭐</b>\nПісля підтвердження доступ активується автоматично.',
        'crypto_paid': '✅ Оплату підтверджено.\n'
                       '\n'
                       'Підписка активна до: <b>{date}</b>\n'
                       '\n'
                       'Тепер можеш користуватися Pro-функціями.',
        'crypto_not_paid': 'Поки не бачу оплату. Спробуй ще раз після підтвердження платежу.',
        'payment_rejected': '❌ <b>Оплату відхилено.</b>\n\nЯкщо це помилка — звернись у підтримку або спробуй інший спосіб оплати.',
        'payment_error': 'Не вийшло створити/перевірити платіж. Напиши підтримці або спробуй інший спосіб.',
        'deleted_title': '👁 <b>Повідомлення видалили</b>',
        'alert_deleted': '👁 <b>Повідомлення видалили</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n🕒 <b>Час:</b> {time}\n\n{saved}',
        'alert_timer_saved': '🔥 <b>Таймерове медіа збережено</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n📎 <b>Тип:</b> {type}\n\nЯ одразу зберіг це медіа, не чекаючи видалення або завершення таймера.',
        'alert_disappearing_saved': '🔥 <b>Зникаюче медіа збережено</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n📎 <b>Тип:</b> {type}\n\nУ цього медіа є таймер/самознищення, тому я зберіг його одразу.',
        'alert_media_backup': '🔥 <b>Медіа збережено</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n📎 <b>Тип:</b> {type}\n\nЯ зберіг це медіа одразу, тому таймерові/зникаючі повідомлення не загубляться.',
        'alert_timer_reply': '🔥 <b>Таймерове медіа — витягнуто через відповідь</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n📎 <b>Тип:</b> {type}\n\nВи відповіли на це повідомлення, тому я витягнув медіа до відкриття.',
        'edited_title': '✏️ <b>Повідомлення змінили</b>',
        'edited_alert': '✏️ <b>Повідомлення змінили</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n\n⬅️ <b>Було:</b>\n{old}\n\n➡️ <b>Стало:</b>\n{new}',
        'keyword_alert': '🔎 <b>Сповіщення за ключовим словом</b>: {keywords}\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n\n{body}',
        'scam_alert': '⚠️ <b>Можливий скам/фішинг</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n\n{body}',
        'alert_direct_media': '🔥 <b>Медіа одразу збережено</b>\n\n📎 <b>Тип:</b> {type}\n💾 <b>Розмір:</b> {size}\n\nЯ отримав це як звичайне повідомлення в боті, тому одразу зробив копію.',
        'alert_direct_timer': '🔥 <b>Таймерове медіа збережено</b>\n\n📎 <b>Тип:</b> {type}',
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
        'deleted_no_content': '👁 <b>Повідомлення видалили</b>\n\n💬 <b>Чат:</b> {chat}\n\nЯ побачив факт видалення, але не встиг зберегти вміст. Так буває, якщо повідомлення було старе або бот ще не мав доступу до цього чату.',
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
        'trial_granted': '🎁 <b>Premium на {days} дн. активовано.</b>\nДоступ до всіх функцій увімкнено.',
        'access_locked': '🔒 <b>Доступ обмежено.</b>\nПробний період завершився. Оформи підписку, щоб користуватися ботом.',
        'ref_earned_normal': '🤝 <b>+{days} дн. Premium</b> за нового реферала.',
        'ref_earned_premium': '💎 <b>+{days} дн. Premium</b> за Premium-реферала.',
        'ref_limit_reached': '🤝 Новий реферал зараховано. Ліміт бонусних днів за звичайних рефералів вичерпано.',
        'unknown_command': 'Не зрозумів команду. Натисни меню нижче.'},
 'ru': {'start': '🕵️ <b>VERTUU SPY BOT</b>\n\nСохраняю удалённые сообщения, правки и исчезающие медиа в твоих чатах.\n\n👇 Нажми «🔌 Подключить» и настрой за 30 секунд.',
        'choose_lang': '🌐 Выбери язык:',
        'menu': '🏠 <b>Главное меню</b>\n\nВыбери раздел:',
        'status': '🛡 <b>Статус защиты</b>\n\n💎 <b>Доступ:</b> {sub_status}\n🔌 <b>Автоматизация чатов:</b> {business_status}\n💬 <b>Сохранено новых сообщений:</b> {saved}\n👻 <b>Удалённых найдено:</b> {deleted}\n\n{hint}',
        'sub_active': 'активна до {date}',
        'sub_free': 'включено / открытый доступ',
        'business_on': '✅ подключено',
        'business_off': '❌ не подключено',
        'status_hint_connect': 'Чтобы я начал работать, добавь меня в Telegram → профиль → Изм. → Автоматизация чатов. После этого я буду видеть только новые сообщения в разрешённых чатах.',
        'status_hint_ok': '✅ Защита включена. Для теста попроси кого-то написать сообщение и удалить его — я покажу копию здесь.',
        'connect': '🔌 <b>Подключение за 3 шага</b>\n\n1️⃣ Telegram → <b>Настройки</b> → <b>Telegram Business</b>\n2️⃣ Открой <b>Чат-боты</b>\n3️⃣ Вставь <code>@{bot_username}</code> и выбери чаты\n\n✅ Без кодов, паролей и session string\n💡 Нажми на <code>@{bot_username}</code>, чтобы скопировать',
        'plans_title': '💎 <b>Тарифы VERTUU SPY BOT</b>\n\nВыберите подходящий тариф:',
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
        'invoice_stars_support': '⭐ <b>Счёт создан.</b>\n\nК отправке: <b>{stars} ⭐</b>\nПосле подтверждения звёзды зачислятся на баланс бота.',
        'invoice_stars_plan': '⭐ <b>Счёт в Telegram Stars создан.</b>\n\nК оплате: <b>{stars} ⭐</b>\nПосле подтверждения доступ активируется автоматически.',
        'crypto_paid': '✅ Оплата подтверждена.\n'
                       '\n'
                       'Подписка активна до: <b>{date}</b>\n'
                       '\n'
                       'Теперь можешь пользоваться Pro-функциями.',
        'crypto_not_paid': 'Пока не вижу оплату. Попробуй ещё раз после подтверждения платежа.',
        'payment_rejected': '❌ <b>Оплата отклонена.</b>\n\nЕсли это ошибка — напиши в поддержку или попробуй другой способ оплаты.',
        'payment_error': 'Не получилось создать/проверить платёж. Напиши поддержке или попробуй другой способ.',
        'deleted_title': '👁 <b>Сообщение удалили</b>',
        'alert_deleted': '👁 <b>Сообщение удалили</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n🕒 <b>Время:</b> {time}\n\n{saved}',
        'alert_timer_saved': '🔥 <b>Таймерное медиа сохранено</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n📎 <b>Тип:</b> {type}\n\nЯ сразу сохранил это медиа, не ожидая удаления или окончания таймера.',
        'alert_disappearing_saved': '🔥 <b>Исчезающее медиа сохранено</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n📎 <b>Тип:</b> {type}\n\nУ этого медиа есть таймер/самоуничтожение, поэтому я сохранил его сразу.',
        'alert_media_backup': '🔥 <b>Медиа сохранено</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n📎 <b>Тип:</b> {type}\n\nЯ сохранил это медиа сразу, поэтому таймеровые/исчезающие сообщения не потеряются.',
        'alert_timer_reply': '🔥 <b>Таймерное медиа — извлечено через ответ</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n📎 <b>Тип:</b> {type}\n\nВы ответили на это сообщение, поэтому я смог извлечь медиа до открытия.',
        'edited_title': '✏️ <b>Сообщение изменили</b>',
        'edited_alert': '✏️ <b>Сообщение изменили</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n\n⬅️ <b>Было:</b>\n{old}\n\n➡️ <b>Стало:</b>\n{new}',
        'keyword_alert': '🔎 <b>Оповещение по ключевому слову</b>: {keywords}\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n\n{body}',
        'scam_alert': '⚠️ <b>Возможный скам/фишинг</b>\n\n💬 <b>Чат:</b> {chat}\n👤 <b>Автор:</b> {author}\n\n{body}',
        'alert_direct_media': '🔥 <b>Медиа сразу сохранено</b>\n\n📎 <b>Тип:</b> {type}\n💾 <b>Размер:</b> {size}\n\nЯ получил это как обычное сообщение в боте, поэтому сразу сделал копию.',
        'alert_direct_timer': '🔥 <b>Таймерное медиа сохранено</b>\n\n📎 <b>Тип:</b> {type}',
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
        'deleted_no_content': '👁 <b>Сообщение удалили</b>\n\n💬 <b>Чат:</b> {chat}\n\nЯ увидел факт удаления, но не успел сохранить содержимое. Так бывает, если сообщение было старое или бот ещё не имел доступа к этому чату.',
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
        'trial_granted': '🎁 <b>Premium на {days} дн. активирован.</b>\nДоступ ко всем функциям включён.',
        'access_locked': '🔒 <b>Доступ ограничен.</b>\nПробный период закончился. Оформи подписку, чтобы пользоваться ботом.',
        'ref_earned_normal': '🤝 <b>+{days} дн. Premium</b> за нового реферала.',
        'ref_earned_premium': '💎 <b>+{days} дн. Premium</b> за Premium-реферала.',
        'ref_limit_reached': '🤝 Новый реферал засчитан. Лимит бонусных дней за обычных рефералов исчерпан.',
        'unknown_command': 'Не понял команду. Нажми меню ниже.'},
 'en': {'start': '🕵️ <b>VERTUU SPY BOT</b>\n\nI save deleted messages, edits and disappearing media in your chats.\n\n👇 Tap “🔌 Connect” to set up in 30 seconds.',
        'choose_lang': '🌐 Choose language:',
        'menu': '🏠 <b>Main menu</b>\n\nChoose a section:',
        'status': '🛡 <b>Protection status</b>\n\n💎 <b>Access:</b> {sub_status}\n🔌 <b>Chat Automation:</b> {business_status}\n💬 <b>New messages saved:</b> {saved}\n👻 <b>Deleted found:</b> {deleted}\n\n{hint}',
        'sub_active': 'active until {date}',
        'sub_free': 'enabled / open access',
        'business_on': '✅ connected',
        'business_off': '❌ not connected',
        'status_hint_connect': 'To start protection, add me in Telegram → profile → Edit → Chat Automation. After that I only see new messages in allowed chats.',
        'status_hint_ok': '✅ Protection is on. Ask someone to send you a message and delete it — I will show a copy here.',
        'connect': '🔌 <b>Connect in 3 steps</b>\n\n1️⃣ Telegram → <b>Settings</b> → <b>Telegram Business</b>\n2️⃣ Open <b>Chatbots</b>\n3️⃣ Paste <code>@{bot_username}</code> and choose chats\n\n✅ No codes, passwords or session strings\n💡 Tap <code>@{bot_username}</code> to copy it',
        'plans_title': '💎 <b>VERTUU SPY BOT Plans</b>\n\nChoose a plan:',
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
        'invoice_stars_support': '⭐ <b>Invoice created.</b>\n\nTo send: <b>{stars} ⭐</b>\nAfter confirmation, Stars will be added to the bot balance.',
        'invoice_stars_plan': '⭐ <b>Telegram Stars invoice created.</b>\n\nTo pay: <b>{stars} ⭐</b>\nAccess activates automatically after confirmation.',
        'crypto_paid': '✅ Payment confirmed.\n'
                       '\n'
                       'Subscription active until: <b>{date}</b>\n'
                       '\n'
                       'You can now use Pro features.',
        'crypto_not_paid': 'I do not see the payment yet. Try again after the payment is confirmed.',
        'payment_rejected': '❌ <b>Payment rejected.</b>\n\nIf this is a mistake, contact support or try another payment method.',
        'payment_error': 'Could not create/check payment. Contact support or try another method.',
        'deleted_title': '👁 <b>Message deleted</b>',
        'alert_deleted': '👁 <b>Message deleted</b>\n\n💬 <b>Chat:</b> {chat}\n👤 <b>From:</b> {author}\n🕒 <b>Time:</b> {time}\n\n{saved}',
        'alert_timer_saved': '🔥 <b>Timer media saved</b>\n\n💬 <b>Chat:</b> {chat}\n👤 <b>From:</b> {author}\n📎 <b>Type:</b> {type}\n\nI saved this media immediately, without waiting for deletion or timer expiry.',
        'alert_disappearing_saved': '🔥 <b>Disappearing media saved</b>\n\n💬 <b>Chat:</b> {chat}\n👤 <b>From:</b> {author}\n📎 <b>Type:</b> {type}\n\nThis media has a timer/self-destruct hint, so I saved it immediately.',
        'alert_media_backup': '🔥 <b>Media backup saved</b>\n\n💬 <b>Chat:</b> {chat}\n👤 <b>From:</b> {author}\n📎 <b>Type:</b> {type}\n\nI saved this media immediately, so timer/disappearing media will not be lost.',
        'alert_timer_reply': '🔥 <b>Timer media — extracted via reply</b>\n\n💬 <b>Chat:</b> {chat}\n👤 <b>From:</b> {author}\n📎 <b>Type:</b> {type}\n\nYou replied to this message, so I extracted the media before it was opened.',
        'edited_title': '✏️ <b>Message changed</b>',
        'edited_alert': '✏️ <b>Message edited</b>\n\n💬 <b>Chat:</b> {chat}\n👤 <b>From:</b> {author}\n\n⬅️ <b>Before:</b>\n{old}\n\n➡️ <b>After:</b>\n{new}',
        'keyword_alert': '🔎 <b>Keyword alert</b>: {keywords}\n\n💬 <b>Chat:</b> {chat}\n👤 <b>From:</b> {author}\n\n{body}',
        'scam_alert': '⚠️ <b>Possible scam/phishing</b>\n\n💬 <b>Chat:</b> {chat}\n👤 <b>From:</b> {author}\n\n{body}',
        'alert_direct_media': '🔥 <b>Media saved instantly</b>\n\n📎 <b>Type:</b> {type}\n💾 <b>Size:</b> {size}\n\nI received this as a direct bot message, so I backed it up immediately.',
        'alert_direct_timer': '🔥 <b>Timer media saved</b>\n\n📎 <b>Type:</b> {type}',
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
        'deleted_no_content': '👁 <b>Message deleted</b>\n\n💬 <b>Chat:</b> {chat}\n\nI detected a deletion but did not save the content. This can happen if the message was old or the bot did not have access to this chat yet.',
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
        'connect': '🔌 Підключити',
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
        'connect': '🔌 Подключить',
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
        'connect': '🔌 Connect',
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
    lang = lang if lang in SUPPORTED_LANGS else 'ru'
    value = TEXTS[lang].get(key, TEXTS['ru'].get(key, key))
    return value.format(**kwargs)


def tr_template(lang: str | None, key: str) -> str:
    """Raw message text for `key` with its {placeholders} intact (not formatted).

    Used by the editable-message layer so /edit can show the placeholders that
    the bot fills with live data.
    """
    lang = lang if lang in SUPPORTED_LANGS else 'ru'
    return TEXTS[lang].get(key) or TEXTS['ru'].get(key) or key


def tr_keys() -> list[str]:
    """All known message keys (union across languages)."""
    keys: set[str] = set()
    for table in TEXTS.values():
        keys.update(table.keys())
    return sorted(keys)


def btn(lang: str | None, key: str) -> str:
    lang = lang if lang in SUPPORTED_LANGS else 'ru'
    return BUTTONS[lang].get(key, BUTTONS['ru'].get(key, key))
