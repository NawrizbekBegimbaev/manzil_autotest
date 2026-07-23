# Мобильная разведка (Фаза 4 — 119 Maestro-флоу)

Собрано при верификации BUG-028…034 на эмуляторе 2026-07-23. Пригодится при написании
мобильного слоя (carrier/Driver-TK + warehouse).

## Окружение / инструменты

- **Android SDK:** `/opt/homebrew/share/android-commandlinetools` (homebrew `android-commandlinetools`).
  `adb` → `$SDK/platform-tools/adb`, `emulator` → `$SDK/emulator/emulator`. Не в PATH — экспортировать.
- **AVD:** `manzil` (android-34), `~/.android/avd/manzil.avd`.
- **Запуск (холодный, стабильно):** `emulator -avd manzil -no-snapshot -dns-server 8.8.8.8,1.1.1.1 -gpu swiftshader_indirect`.
  Готовность: `adb wait-for-device` + опрос `getprop sys.boot_completed`=1.
- **JAVA (для Maestro):** JRE в PATH нет; брать JBR из Android Studio —
  `JAVA_HOME=/Applications/Android Studio.app/Contents/jbr/Contents/Home` (openjdk 21). Без него maestro падает «Unable to locate a Java Runtime».
- **Maestro:** `~/.maestro/bin/maestro`.

## Приложения (оба ходят на **staging**)

| Приложение | package | launcher |
|---|---|---|
| Склад (Warehouse) | `uz.logos.manzil.warehouse.staging` | `…warehouse.MainActivity` |
| Перевозчик (Driver-TK) | `uz.logos.manzil.driver` | `.MainActivity` (v1.0, Build 2026.05) |

- **Driver-app = staging** (подтверждено: staging-склад-телефон → 403 wrong-app, а не «неизвестен»).
- **Оба — Flutter.** `uiautomator dump` даёт пустое дерево (`android:id/content`) → **тексты читать скриншотом**
  (`adb exec-out screencap -p > x.png`, затем визуально). Maestro матчит по видимому тексту — работает.

## Грабли (проверено)

- **Blank-mount флейк** на `launchApp: {clearState:true}` — процесс стартует, RN/Flutter-view не монтируется
  (пустой экран). Лечится релончем: обернуть запуск в `retry: {maxRetries: 3, commands:[launchApp…, extendedWaitUntil "00 000 00 00"]}`.
- **Язык driver-app:** после `clearState` дефолт — **O'zbekcha (узбекский)**; переключатель в Профиле
  («Til/Язык» → O'zbekcha/Русский). Язык **персистит через logout** (на экране входа сохраняется). Экран входа язык уважает.
- **Rate-limit жечь нельзя** на UAT/известных аккаунтах (5 неудач/телефон/10 мин) — под-проверки лимита пропускать.
- **Карго-креды:** в `mobile/config/maestro.env` только склад (`WAREHOUSE_PHONE` нац. + `WAREHOUSE_PASSWORD`).
  Перевозчика провизинить через staging super-admin: `POST /super-admin/transport-companies {name,tin(9),address,transportTypes,isAll,admin:{fullName,phone,password}}`, пароль = `NEW_ACCOUNT_PASSWORD`. Удалять после (`DELETE …/{id}`).

## Селекторы входа (общие для обоих)

- Телефон: placeholder **`00 000 00 00`** (нац. цифры, `+998` фиксирован в UI).
- Пароль: label **`Parol`** (uz) / **`Пароль`** (ru).
- Кнопка входа: **`Kirish`** (uz) / **`Войти`** (ru).
- Нижняя навигация перевозчика: **`Buyurtmalar/Takliflar/Profil`** (uz) ↔ **`Заявки/Предложения/Профиль`** (ru).
- Выход: **`Chiqish`** (uz) / **`Выйти`** (ru) — **без диалога подтверждения** (см. BUG-033).

## Тексты экранов (для assert'ов флоу)

- **Склад home:** табы `E'lon qilindi / Olingan / Ishda / Yo'lda`; FAB `Ariza yaratish`; нав `Buyurtmalar/Profil`.
- **Перевозчик home:** `Mavjud yuklar` / `Лента заявок`; поиск `Marshrut, TC, ID bo'yicha qidirish…` / `Поиск по маршруту, TC, ID…`.
- **Перевозчик Профиль:** плитки `mavjud/kutilmoqda/jarayonda` ↔ `доступно/в ожидании/в работе`; строки
  `Bildirishnomalar/Til/Avtopark` ↔ `Уведомления/Язык/Автопарк`; пустые уведомления `Bildirishnomalar yo'q`.
- **Деталь заказа (перевозчик):** `Детали груза` / `Спецификация груза`; поля `Транспорт / Кол-во водителей /
  Длина / Дата погрузки / Груз / Тип оплаты`; кнопка `Подать предложение` (подать оффер).

## ⚠ Локализационный лик (China-first) — новая находка

Название **типа ТС** приходит с сервера **по-китайски** и НЕ локализуется в приложении перевозчика:
в ленте и в детали заказа отрисовано **`平板 13.7`** (平板 = бортовой) — и при узбекском, и при русском UI.
В складском приложении тот же тип показан как **`Bortli 13.7`** (латиница). То есть carrier-app не переводит
серверное имя vehicleType (семья дефектов BUG-032 «китайский у перевозчика»). Кандидат в баг-трекер отдельно.

## Итог верификации BUG-028…034 (staging, 2026-07-23) — см. BUG_TRACKER
