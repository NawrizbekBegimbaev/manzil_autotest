# Живые наблюдения мобильных приложений Manzil (staging, эмулятор Pixel 6, Android 14)

Снято 2026-07-10 на `staging-manzil.greatmall.uz`. Обе сборки подтверждённо смотрят на staging.
UI обоих приложений — узбекский.

## Учётки (staging)
- Склад (Сотрудник склада, роль SHIPPER_WAREHOUSE): `+998900000004 / <staging-password>` — РАБОТАЕТ.
- Carrier/driver app (роль TRANSPORT_ADMIN): корректной staging-учётки НЕТ (в списке коллизия
  номера с менеджером). Попытка входа `+998900000003` → **403 wrong-app** (это SHIPPER_MANAGER,
  а не транспортник). Подтверждает гейт clientType вживую.

## ПРИЛОЖЕНИЕ СКЛАДА — `uz.logos.manzil.warehouse.staging` (v1.1.1-staging)
Главная активность `uz.logos.manzil.warehouse.MainActivity`.

### Экран входа
- Верх справа: переключатель языка «O'zbekcha».
- Логотип «MANZIL», подпись «Hisobingizga kiring».
- Поле телефона: фиксированный флаг + `+998` (dropdown-стрелка рядом), плейсхолдер «00 000 00 00».
  Вводится 9 цифр (национальный номер), маска «99 474 60 06».
- Поле пароля «Parol» с иконкой-глаз (показать/скрыть), точечная маскировка.
- Кнопка «Kirish» — НЕАКТИВНА (бледная), пока поля пустые; становится синей при заполнении обоих.
- Внизу текст согласия «Kirib, siz Maxfiylik siyosati va Foydalanish shartlariga rozilik bildirasiz.»
- Системный диалог Android «Allow notifications?» при первом запуске (Allow / Don't allow).
- ДЕФЕКТ вёрстки: при открытии клавиатуры форма «прыгает» вверх, поля/кнопка меняют позицию —
  легко промахнуться. При закрытии клавиатуры кнопка уезжает вниз.
- Ответы сервера (пойманы в логах OkHttp):
  - неверный пароль/чужая среда → `401 {"code":"error.invalid-credentials","detail":"Noto'g'ri login yoki parol"}`
  - есть баннер ошибки вверху «Noto'g'ri so'rov» (bad request) в некоторых состояниях.

### Главный экран (Buyurtmalar)
- Верхняя лента ВКЛАДОК статусов со счётчиками (горизонтально прокручиваемая, часть за правым краем):
  `E'lon qilindi (2)` [PUBLISHED], `Olingan (1)` [QUOTED/взятые], `Ishda (4)` [IN_WORK],
  `Yo'lda (1)` [IN_TRANSIT], далее ещё есть (напр. `Tugallangan` [COMPLETED]).
- Карточка заявки: номер `NAMA-00010` (staging-префикс NAMA), дата (календарь) `2026-07-10`,
  блок маршрута: зелёная точка = пункт отправления (город + подпись, напр. «Urumqi / Small · Qwerty»),
  стрелка `--->`, красная метка = пункт назначения («Yiwu / Square · Kpyro…»), чип типа ТС «Bortli 13.7».
  У некоторых заявок тип ТС пуст: чип с «—» (напр. NAMA-00009 Nukus→Almata).
- Зелёная круглая FAB «+» (Ariza yaratish) справа снизу — создание заявки.
- Нижняя навигация: «Buyurtmalar» (список, активна) и «Profil».
- Маршруты реальные CN↔CIS: Urumqi, Yiwu, Nukus, Almata, Beijing.

### Профиль (Profil)
- Аватар с инициалами (напр. «БН»), ФИО «Бегимбаев Наврузбек Мамбетали», телефон `+998900000004`.
- Пункты меню (карточки со стрелками): «Bildirishnomalar» (уведомления), «Til» (язык, значение «UZ»),
  «Chiqish» (выход).

### Создание заявки — шаг 1 (bottom sheet)
- Заголовок «Transport turini tanlang» (выберите тип транспорта).
- Две карточки: «Temir yo'l» (ж/д — СЕРАЯ/недоступна) и «Avtomobil» (авто — активна, выделена зелёным).

### Создание заявки — шаг 2 (форма «Yangi ariza yaratish»)
Кнопка «назад» (стрелка) в шапке. Поля (звёздочка = обязательное):
- «Yuklash sanasi *» — дата загрузки, поле с иконкой-календарём, по умолчанию сегодня («10 Iyul · Ju»).
- «Transport *» — чипы типов ТС: Bortli 13.7, Bortli 16, Bortli 17.5, Refrijerator 12.5,
  Baland bortli 13, Tentli 9.6 (одиночный выбор).
- «Haydovchilar soni *» — число водителей: «1 haydovchi» (выбрано по умолчанию) / «2 haydovchi».
- «Yo'nalish *» — маршрут: карточка «откуда» (зелёная точка, город+склад, стрелка-редактирование) →
  «куда» (красная метка). Предзаполнен сохранёнными складами аккаунта (Nukus→Almata). Тап по стрелке
  открывает выбор адреса.
- «Izohlar» — комментарии, плейсхолдер «Maxsus talablar...» (особые требования), необязательное.
- Низ: «Orqaga» (назад) / «Ko'rib chiqish» (просмотр перед публикацией).

### Из Maestro-флоу (mobile/flows) — реальные лейблы для последующих шагов
- FAB content-desc «Ariza yaratish»; «Koʻrib chiqish» → экран просмотра → «Eʼlon qilish» (публикация).
- Добавление адреса: «Oʻz manzilingizni qoʻshish» / «Manzilni saqlash»; экран страны «Xitoy» (Китай),
  поиск города «Shaharni qidirish»; «Yuklash manzili» (адрес загрузки), «Yetkazib berish manzili»
  (адрес доставки); «Davlat raqami» (госномер).
- Детали заявки: «Haydovchi bilan aloqa» (связь с водителем) со статусами «Tasdiqlandi» (подтв.),
  «Rad etildi», «Aloqasiz», «Bogʻlanish»; «Yuk joʻnatildi» (груз отправлен → IN_TRANSIT).
  Детали показывают внутренний «ID», а не отображаемый номер заявки.
- Вкладки статусов: E'lon qilindi / Olingan / Ishda / Yoʻlda / Tugallangan.

## CARRIER / DRIVER APP — `uz.logos.manzil.driver` (v1.0.2)
Главная активность `uz.logos.manzil.driver/.MainActivity`. Роль TRANSPORT_ADMIN.
Смотрит на staging. Внутрь войти не удалось (нет корректной staging-учётки ТК).

### Экран входа (дизайн ОТЛИЧАЕТСЯ от склада)
- Верх слева: переключатель языка «🌐 O'zbekcha ⌄» (dropdown).
- Логотип: синий кружок «M» + «Manzil».
- Заголовок «Yana xush kelibsiz» (снова добро пожаловать), подзаголовок
  «Hisobingizga kiring va sektoringizdagi yuklarni ko'ring, marshrutga mos buyurtmalarni oling.»
- Поле «Telefon raqam» (лейбл сверху, зелёная точка-индикатор): флаг + `+998 ⌄`, разделитель,
  плейсхолдер «00 000 00 00». Ввод 9 цифр, маска «90 000 00 03».
- Поле «Parol» с иконкой-замок слева, крестик-очистка и глаз-показать справа.
- Кнопка «Kirish →» (со стрелкой) — неактивна, пока телефон пуст; активна при заполнении.
- Внизу «Kirib, siz Foydalanish shartlariga rozilik bildirasiz.»
- Клавиатура предлагает автозаполнение номеров (chips `+998900000011`, `+998900000012` …).
- Ответ сервера при чужой роли (SHIPPER_MANAGER): `403` (wrong-app) — остаётся на экране входа.

## Общие технические заметки
- Оверлей отладчика Pluto (androidpluto.com) виден у края в staging-сборках (не часть продукта).
- Лимитер логина: 5 неудач/телефон, 30/IP, окно 10 мин → 429. Проверять аккуратно.
- Оба приложения используют clientType: склад = WAREHOUSE_APP (только SHIPPER_WAREHOUSE),
  carrier = TRANSPORT_COMPANY_APP (только TRANSPORT_ADMIN). DRIVER не входит никуда → 403.
