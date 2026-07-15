# Аудит тест-кейсов против кода `manzil-core@staging` — 10.07.2026

Сверка существующих 384 кейсов (`data/01..08`) с реальным кодом.
Ветка `staging` побайтово совпадает с `main` (tree `2371ea0c`).
Все ссылки — от корня `backend/src/main/java/com/manzil/`.

## Итог

| Файл | Кейсов | Устарело | Пропущено | Кейсы на несуществующее |
|---|---|---|---|---|
| 01_auth | 45 | ~2 | ~4 области | 0 |
| 02_rbac | 28 | ~11 | ~6 областей | 0 |
| 03_superadmin_companies | 38 | ~5 | ~7 | 0 |
| 04_superadmin_drivers_dicts | 35 | ~12 | ~11 | 3 |
| 05_shipper | 73 | ~9 | ~6 | 0 |
| 06_carrier_tender | 77 | ~2 | ~4 | 0 |
| 07_mobile | 41 | ~7 | ~13 | 2 |
| 08_integrations_e2e | 47 | ~3 | ~14 | 0 |

## Корневая причина большинства расхождений

Продукт мигрировал с ролевой модели на **capability-модель**: `@RequiresCapability`
+ `CapabilityAspect` + `RoleCapabilityDefaults` + таблица `user_granted_capabilities`.
Кейсы писались по ролевой модели.

Дефолт `SHIPPER_MANAGER` (`shared/security/RoleCapabilityDefaults.java:21-27`):
`ORDER_REVIEW, ORDER_FULFILL, DEPARTURES, SMS_BLAST, SMS_JOURNAL, WAREHOUSE_DIRECTORY_READ`.
**Нет** `REPORTS`, `TENDER_SELECT`, `ORDER_ENTRY`, `ORDER_DELETE`,
`WAREHOUSE_DIRECTORY_WRITE`, `SEE_PRICES`, `BLACKLIST`.

Второе следствие — **два разных кода для 403**:
- ролевой гейт `@PreAuthorize` → `AccessDeniedException` → code **`FORBIDDEN`**
  (`shared/web/GlobalExceptionHandler.java:85-91,146-151`);
- capability-гейт / `RoleGuard` → `DomainException.forbidden` → code = ключ сообщения,
  т.е. **`error.forbidden`** (`GlobalExceptionHandler.java:59`).

Кейсы почти везде пишут `error.forbidden` там, где реально возвращается `FORBIDDEN`.

## Ложно-позитивные кейсы (ждут 200, код отдаёт 403)

Проверено вручную: `ShipperReportController.java:38-39` несёт
`@RequiresCapability(UserCapability.REPORTS)` на классе.

- `RBAC-009` — офферы, MANAGER → ждёт 200. Реально `@RequiresCapability(TENDER_SELECT)`
  (`tendering/internal/web/ShipperTenderingController.java:42-43`) → **403**.
- `RBAC-028`, `SHP-068`, `SHP-071` — отчёты и дашборд, MANAGER → ждут 200. Реально
  `REPORTS` → **403**.
- `RBAC-013` — утверждает изоляцию `/warehouse/**` под `SHIPPER_WAREHOUSE`. Реально
  класс-гейт пускает и офисные роли (`orders/internal/web/WarehouseController.java:76`).

## Кейсы на несуществующие контракты

- **Vehicle types**: тесты шлют `{name}`; реально `{category, size}`
  (`dictionaries/internal/web/dto/VehicleTypeRequest.java:15-23`). Затронуты
  `SADD-031/032/033/035`.
- **Cities**: тесты шлют `country` (строка); реально `countryId` (UUID FK)
  (`dictionaries/internal/web/dto/CityRequest.java:11-19`). Затронуты
  `SADD-025/026/027/028/030`.
- **MOB-015/016/017**: free-text `cityName`+`country` не существует; реально
  `cityId` XOR `divisionCountry`(CN|KG)+`divisionCode`
  (`fleet/.../AddPersonalWarehouseRequest.java:26-42`).
- **MOB-031**: утверждает, что `cardId` убран из формы водителя — он на месте
  (`DriverRequest.java:31-35`).
- **MOB-018**: ждёт успешный edit заказа в `QUOTED`; реально edit разрешён только
  в `DRAFT/PUBLISHED` (`orders/internal/service/OrderService.java:80-81,188-189`).

## Топ-10 опасных пробелов

1. **429 brute-force логина не покрыт вообще.** `users/internal/security/LoginAttemptLimiter.java`:
   5 неудач/телефон, 30/IP, окно 10 мин, `error.too-many-attempts`. Регресс = открытый
   credential-stuffing.
2. **Ложно-позитивные RBAC-009 / RBAC-028 / SHP-068 / SHP-071** маскируют утечку
   коммерчески чувствительных данных (цены офферов, суммы отчётов).
3. **Per-user granted capabilities не покрыты нигде** (`CapabilityDirectory`,
   `user_granted_capabilities`). Баг в резолве грантов = тихая эскалация привилегий.
4. **Роли `SHIPPER_OPERATOR` и `SHIPPER_DISPATCHER` не тестируются совсем.**
   `RoleCapabilityDefaults.java:31-42`. DISPATCHER без `ORDER_FULFILL` не должен
   отменять/завершать заказы — не проверяется.
5. **`error.driver.blacklisted` при attach не покрыт**
   (`fleet/internal/service/OrderDriverService.java:438`) — прямая цель фичи blacklist.
6. **`RBAC-013` даёт ложную уверенность в границе tenancy** для `/warehouse/**`.
7. **DELETE-гард `error.company.has-active-orders` не покрыт**
   (`users/internal/service/CompanyService.java:145-147,248-250`) — разрушительная операция.
8. **Справочники СА тестируются по несуществующей схеме** → реальные валидации
   (`train-has-no-size`, `size-required`, `city.in-use`, `country.not-found`) не проверяются.
9. **Ветка `error.order.cannot-schedule-with-bids` не покрыта** (`OrderService.java:218`).
10. **Смешение кодов 403 (`FORBIDDEN` vs `error.forbidden`)** — фронт различает их
    (silent-redirect vs toast); регресс в exception-mapping не поймается.

## Прочее пропущенное покрытие

- `effectiveCapabilities` в `MeResponse` (`users/internal/web/dto/MeResponse.java:26`) —
  драйвит видимость секций в web, не ассертится.
- Логин через WEB для `SHIPPER_MANAGER/OPERATOR/DISPATCHER` (`ClientType.java:23-24`).
- `SELECTED → republish` (one-click re-tender): `REPUBLISHABLE_STATUSES = {CANCELLED, SELECTED}`
  (`OrderService.java:101-102`); `SHP-024` утверждает 409.
- `error.offer.carrier-excluded` (`tendering/internal/service/OfferService.java:111`).
- `error.driver.card-id-required` (`OrderDriverService.java:420`).
- CRUD стран (`users/internal/web/SuperAdminController.java:76-105`).
- Device-эндпоинты: `DELETE /me/devices/{id}`, `error.device.register-conflict`.
- 1C batch-дубль `error.webhook.duplicate-event`.

## Что аудит проверить не смог

- Web-кейсы (тосты, редиректы, `isWebUser`-гейт, role-home маршруты) — фронт
  `apps/manzil-web/src` в этом проходе не читался.
- Реальные интеграции с Keycloak (ротация refresh, disable аккаунта) — только по коду.
- Точные RU-тексты части ключей `messages.properties`.
