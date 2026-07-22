# Manzil — Project Reference for Test-Case Design

Authoritative, test-oriented model of the Manzil platform (UZ↔CN freight tendering),
synthesized from a full read of backend (Spring Modulith) + frontend (manzil-web) +
mobile API + BRD/design docs at `/tmp/manzil-core` (branch `main`, latest).

> When code and docs disagree, **trust the controllers/DTOs/services** (newest). Key
> drifts to verify live are flagged with ⚠.

---

## 1. Actors & roles

Backend roles (Keycloak realm roles → `ROLE_*`):
`SUPER_ADMIN, SHIPPER_ADMIN, SHIPPER_MANAGER, SHIPPER_WAREHOUSE, TRANSPORT_ADMIN, DRIVER`.

Channels:
- **Web** (manzil-web) roles (internal map): `SUPER_ADMIN`, `ADMIN`(=SHIPPER_ADMIN),
  `MANAGER`(=SHIPPER_MANAGER), `CARRIER`(=TRANSPORT_ADMIN).
  **SHIPPER_WAREHOUSE and DRIVER cannot log into web** (`isWebUser` gate → toast
  "Эта учётная запись не поддерживается").
- **Warehouse mobile app** (`uz.logos.manzil.warehouse.staging`, Uzbek UI) = SHIPPER_WAREHOUSE.
- **Carrier mobile app** = TRANSPORT_ADMIN. **DRIVER is not a login** (just a name+phone record).

Post-login web redirect: SUPER_ADMIN→`/super-admin/partners/shipper-companies`,
ADMIN→`/dashboard`, MANAGER→`/shipper/storeroom`, CARRIER→`/transport/orders`.

---

## 2. Auth & clientType

`POST /api/v1/auth/login {phone, password, clientType}` — all 3 required.
`phone` regex `^\+[0-9]{10,15}$`; `password` `@Size(max=128)` (no policy regex at login).
Response `TokenResponse{accessToken, refreshToken, expiresIn(sec), tokenType="Bearer"}`.
Also `POST /auth/refresh {refreshToken}`, `POST /auth/logout {refreshToken}`→204 (always).

**ClientType → allowed roles:**
| clientType | roles |
|---|---|
| `WEB` | SUPER_ADMIN, SHIPPER_ADMIN, SHIPPER_MANAGER, TRANSPORT_ADMIN |
| `WAREHOUSE_APP` | SHIPPER_WAREHOUSE only |
| `TRANSPORT_COMPANY_APP` | TRANSPORT_ADMIN only |

Login order: (1) Keycloak password grant — wrong creds → **401 `error.invalid-credentials`**;
(2) app user exists & not soft-deleted, else 401; (3) account active & company not blocked,
else **401** (generic, never reveals which); (4) `clientType.permits(role)` else **403 `error.wrong-app`**.
So **bad password→401, good password+wrong app→403**. DRIVER is in no clientType set → always 403.

`GET /me` → `MeResponse{id, fullName, phone, role, company{id,name,type SHIPPER|TRANSPORT}|null,
allowedFromWarehouseIds, allowedToWarehouseIds, defaultFromWarehouseId, defaultToWarehouseId}`.
company null only for SUPER_ADMIN/DRIVER. `allowedFrom/ToWarehouseIds` hold the assigned
warehouses for SHIPPER_WAREHOUSE; office roles with `ORDER_ENTRY` (incl. SHIPPER_ADMIN — web
«Создать заказ») also receive these lists but **empty** (`[]` = no warehouse restriction).
`defaultFrom/ToWarehouseId` are omitted when unset.
Blocked company → **403 `error.company.blocked`**; deactivated user → **401**.
Block a company: `PATCH /super-admin/shipper-companies/{id}` with `{name, prefix, tin, address,
active:false, admin:{…}}` (all fields required, incl. `admin`).

Refresh rotation ON (old refresh invalidated). TTL: ~1d access / 1w refresh (KC-driven).

---

## 3. Order lifecycle (the spine)

`OrderStatus`: **DRAFT → PUBLISHED → QUOTED → SELECTED → IN_WORK → IN_TRANSIT → COMPLETED**,
plus **CANCELLED**. Forward-only; terminal = COMPLETED, CANCELLED.

`CommunicationStatus` (orthogonal, only meaningful while IN_WORK): **PENDING, CONFIRMED, DECLINED,
UNAVAILABLE**. Re-settable; never changes order status. ⚠ some docs say REACHED/NOT_REACHED — code uses the 4 above.

`OrderType`: AUTO, RAIL. `Currency`: USD, CNY (default CNY). `displayNumber = PREFIX-%05d(seq)`
(per-company gapless sequence; prefix snapshot at create).

| Step | Actor | Endpoint | Pre → Post |
|---|---|---|---|
| Create | ORDER_ENTRY roles: SHIPPER_WAREHOUSE (mobile) **+ office ADMIN/OPERATOR (web «Создать заказ»)** | `POST /warehouse/orders` (`@RequiresCapability(ORDER_ENTRY)`; class-gate admits all shipper roles; there is no separate office endpoint) | future `scheduledPublishDate`→DRAFT; else/today→PUBLISHED |
| Auto-publish | system job (00:00 Asia/Tashkent + startup) | — | DRAFT(`scheduledPublishDate<=today`)→PUBLISHED |
| Bid | TRANSPORT_ADMIN | `POST /transport/orders/{id}/offers` | first bid PUBLISHED→QUOTED |
| Select winner | **SHIPPER_ADMIN only** | `POST /shipper/orders/{orderId}/offers/{offerId}/select` | QUOTED→SELECTED; winner SELECTED, others REJECTED |
| Assign drivers | TRANSPORT_ADMIN | `POST /transport/orders/{id}/drivers {drivers:[{driverId,licensePlate}]}` | on SELECTED/IN_WORK |
| Start | TRANSPORT_ADMIN | `POST /transport/orders/{id}/start` | SELECTED→IN_WORK (needs full driver count); resets commStatus PENDING |
| Communication | SHIPPER_WAREHOUSE | `POST /warehouse/orders/{id}/communication {status}` | only IN_WORK |
| Goods sent | SHIPPER_WAREHOUSE | `POST /warehouse/orders/{id}/goods-sent` | IN_WORK & commStatus=CONFIRMED → IN_TRANSIT |
| Complete | SHIPPER_ADMIN/MANAGER OR 1C webhook | `POST /shipper/orders/{id}/complete` / `POST /integrations/1c/shipments/status` | IN_TRANSIT→COMPLETED |
| Cancel | SHIPPER_ADMIN/MANAGER | `POST /shipper/orders/{id}/cancel {reason}` | only SELECTED/IN_WORK/IN_TRANSIT |
| Republish | SHIPPER_ADMIN/MANAGER | `POST /shipper/orders/{id}/republish` | source CANCELLED → brand-new order |

**Edit/delete order:** allowed only DRAFT/PUBLISHED/QUOTED (delete also COMPLETED/CANCELLED);
SELECTED/IN_WORK/IN_TRANSIT → 409. Order DELETE is SHIPPER_ADMIN-only. **No order creation on web.**

Forbidden transitions (expect 409): bid on non-PUBLISHED/QUOTED; select on non-QUOTED or twice;
start with < full driver count or non-SELECTED; goods-sent when commStatus≠CONFIRMED or not IN_WORK;
communication outside IN_WORK; cancel from DRAFT/PUBLISHED/QUOTED; complete from non-IN_TRANSIT;
republish from non-CANCELLED; future schedule on QUOTED order (`cannot-schedule-with-bids`).

**API-контракты (по факту dev, проверено провизинингом):** order id — **числовой (Long)**, не UUID.
Деталь `GET /shipper/orders/{id}` обёрнута: `{order:{…}, winningOffer, history[]}` (сам заказ — в `order`).
Bid body `{price}`; offer id — UUID. Attach-driver `POST /transport/orders/{id}/drivers
{drivers:[{driverId, licensePlate, cardId}]}` — **`cardId` обязателен** (иначе 400
`error.driver.card-id-required`). `start` требует полного `driversCount`. Transport-driver create
`POST /transport/drivers {fullName, phone, cardId?}`. Cancel body `{reason}`; communication
`{status: CONFIRMED|PENDING|DECLINED|UNAVAILABLE}`; start/goods-sent/complete — без тела.

---

## 4. Tendering (offers) & fleet (drivers)

`OfferStatus`: **PENDING, SELECTED, REJECTED** (no withdraw endpoint). One active offer per
(order, transport company). Submit on PUBLISHED/QUOTED only; dup → 409 `error.offer.already-submitted`;
first bid flips PUBLISHED→QUOTED; currency inherited from order. Edit (`PATCH /transport/offers/{id}`)
only while PENDING; foreign offer → 404. price `@Positive @DecimalMax("9999999999999.99")`; notes ≤250.
Select winner: only SHIPPER_ADMIN; order must be QUOTED, offer PENDING & on this order, carrier active
(blocked carrier → 409 `error.offer.transport-blocked`). Rejected offers soft-deleted **24h** later (hourly job).

**Feed visibility** (`GET /transport/feed`) — order visible iff ALL:
1. status ∈ {PUBLISHED, QUOTED};
2. caller hasn't already bid on it (bid orders move to `/my-offers`);
3. served-cities: `isAll=true`→no filter; else from/to warehouse in carrier's cities (empty set→sees nothing);
4. neither leg in carrier's blacklist warehouses.
⚠ **No vehicle/body-type matching** — a RAIL-only carrier still sees AUTO orders. Blacklist applies only
to the feed LIST, not `/feed/{id}` detail or offer submit.

**Driver model (changed 2026-06-23):** `{fullName, phone}` only (vehicleType/license/birthday/cardId removed).
phone `^\+[0-9]{10,15}$`, unique per company. `licensePlate` is **per-assignment** (`@NotBlank @Size(max=20)`).
Assignment: 1–2 drivers (`@NotEmpty @Size(max=2)` AND ≤ order.driversCount); driver must belong to caller (else 404);
driver busy on another active order {SELECTED,IN_WORK,IN_TRANSIT} → 409 `busy-on-another-order`.
**Start requires the FULL requested driver count** (`attached < driversCount` → 409 `drivers-incomplete`)
⚠ swagger says "≥1"; code enforces full count. Detach last driver while IN_WORK → 409 `must-keep-driver`.
`available-drivers` excludes busy-elsewhere drivers, includes those already on this order, no vehicle-type filter.
`error.driver.vehicle-type-mismatch` removed.

---

## 5. RBAC matrix (controllers)

| Surface | SUPER_ADMIN | SHIPPER_ADMIN | SHIPPER_MANAGER | SHIPPER_WAREHOUSE | TRANSPORT_ADMIN | DRIVER |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `/me`, `/auth/**` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/super-admin/**` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `/shipper/staff/**`, warehouse write, order DELETE | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| `/shipper` order review/cancel/republish/complete/communication, offers list, warehouses read | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| winner-select | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| `/warehouse/**` | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| `/transport/**` | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |

Status semantics: **no/invalid token → 401** (`code=UNAUTHORIZED`); **wrong role → 403** (`error.forbidden`);
**right role, out-of-tenant resource → 404** (BOLA defense — id can't be probed); **blocked company → 403
`error.company.blocked`**; **deactivated user → 401**.

---

## 6. Validation cheat-sheet (exact)

- Password policy: `^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$` (≥8, lower+upper+digit+special).
- Company prefix: `^[A-Z]{4}$` (exactly 4 uppercase). Unique (case-insensitive) among live companies.
- Phone: `^\+[0-9]{10,15}$`. Company/staff/driver fullName 2–255. tin ≤18 (no checksum). address ≤500.
- Order: cargoType AUTO/RAIL @NotNull; driversCount @Min(1)@Max(2); notes ≤2000; vehicleType/warehouse must exist (else 404).
  Date window (Asia/Tashkent): `scheduledPublishDate` not in past, `<= loadDate`; immediate publish needs `loadDate >= today`.
- Offer: price >0 & ≤`9999999999999.99`; notes ≤250.
- Cancel reason ≤500. Personal warehouse name @NotBlank ≤255, city/country 1–255, exactly one of cityId vs cityName+country; max 100 personal warehouses.
- File upload `POST /api/v1/files` (part `file`): ≤5 MiB (5–6 MiB→400 `file.too-large`, >6 MiB→413); MIME by Tika magic-bytes ∈ {image/jpeg, image/png, image/webp} else 400 `file.invalid-type`; empty→400 `file.missing`.
- Device `language` clamped to {ru,uz,ky,zh,ug} (unsupported silently→ru); `language` ≤8 chars, emasDeviceId ≤256.
- Non-multipart JSON body >256 KiB on `/api/*` → 413 `error.request.too-large`.

---

## 7. Error model

ProblemDetail (RFC 9457): `{type,title,status,detail,instance,code,message,[errors]}`. Assert on **`code`**:
for `DomainException` it's the **i18n key** (e.g. `error.offer.already-submitted`); for framework/security it's
the HTTP status name. Validation 400 carries `errors:[{field,message}]`. DataIntegrity→409 `error.conflict`;
Optimistic lock→409 `error.concurrent-modification`. Key RU values: `error.forbidden`="Доступ запрещён",
`error.unauthorized`="Требуется авторизация", `error.city.duplicate`="Город … уже существует",
`error.webhook.no-active-shipment`, `error.webhook.ambiguous-plate`, etc.

---

## 8. 1C completion webhook

`POST /api/v1/integrations/1c/shipments/status` (+ `/batch`). Public path; gated by header
**`X-Webhook-Token`** (constant-time; blank secret→always 401). Body `{eventId, licensePlate, event?=DELIVERED, occurredAt?}`.
Matches active **IN_TRANSIT** order by normalized plate (`[\s.\-/·]` stripped, uppercased) on `order_drivers.license_plate`.
**Idempotent by `eventId`** (duplicate→200 no-op). Errors: 400 missing eventId/plate or bad batch; 401 bad token;
404 no active shipment; 409 ambiguous plate (>1 IN_TRANSIT) / not completable / duplicate-event race.
Batch `items` 1–500, each processed in its own tx (one failure doesn't abort others); batch HTTP always 200 when token+envelope valid.

---

## 9. Other modules

- **Dictionaries** (SUPER_ADMIN only, under `/super-admin/*`): cities (unique lower(name,country)→409 `city.duplicate`),
  vehicle-types (unique lower(name)→409), warehouses read-only here. No public `/dictionaries/*`.
- **Notifications** `/me/notifications` (list, unread-count, {id}/read, read-all, delete) + **Devices** `/me/devices`
  (register upsert by emasDeviceId, patch language, delete). Channels enum PUSH+SMS but **only PUSH implemented**.
  Types: TRANSPORT_SELECTED, DRIVERS_ATTACHED.
- **SMS**: ⚠ **not implemented** — placeholder. SMS-log endpoint/page returns empty; web "Отправить СМС" & dashboard
  "SMS отправлено=0" are stubs. Don't write SMS-delivery tests.
- **Blacklist**: backend `TransportCompany.blacklistWarehouseIds` applied in feed only. (Web archive blacklist pages
  exist; remove fires with no confirm.)
- **Reports** `/shipper/reports/{orders,companies}` + `/shipper/dashboard/stats` (native SQL, needs real Postgres).

---

## 10. Web UI testing notes (Playwright)

- **No data-testid.** Locate by ARIA role + RU text, `getByLabel`, `getByPlaceholder`, row-scoping.
- **Default UI language = zh.** Pin RU before load: `localStorage['__tolgee_currentLanguage']='ru'` (done in conftest).
- Forbidden access = **silent redirect to role home** (assert URL, not a 403 page).
- Phone field defaultCountry: login & transport-driver form = **CN** (type full +998…); shipper/transport-company/staff/
  self-employed-driver forms = **UZ** (type national part only).
- Create/edit dialogs: shipper-company, transport-company, staff (role Менеджер/Сотрудник склада + warehouse city
  assignment), self-employed-driver (rich), transport-driver (**now name+phone only**), transport-quotation (offer:
  "Предложить цену"→price/notes→"Отправить"→toast "Предложение отправлено"), order-republish.
- Winner select on `/shipper/orders/$id`: row "Принять" → confirm "Принять предложение?" → "Принять" → toast "Перевозчик выбран".
- RBAC pages: Edit buttons are inert placeholders; delete/blacklist-remove fire with no confirm.

## 11. Mobile testing notes (Maestro)

- Warehouse app Uzbek. Order create flow → `POST /warehouse/orders` (cargoType, vehicleTypeId, driversCount 1-2,
  from/to warehouse, loadDate, notes). Inline "Manzil qoʻshish" (Shahar/Davlat/Tuman, free text) → `POST /warehouse/locations`
  (reusable warehouse on both from+to lists). Addresses persist per account (later orders default them).
- Status tabs: Rejalashtirilgan=DRAFT, Eʼlon qilindi=PUBLISHED+QUOTED, Olingan=SELECTED, Ishda=IN_WORK,
  Yoʻlda=IN_TRANSIT, Tugallangan=COMPLETED.
- `docs/api/seed-test-order.sh` seeds a SELECTED order (warehouse create→publish, carrier bid, manager select) for
  driver-attach testing.

---

## 12. ⚠ Live-verification list (code vs docs)

1. Start requires FULL driver count (code) vs "≥1 driver" (swagger).
2. communicationStatus enum PENDING/CONFIRMED/DECLINED/UNAVAILABLE (code) vs REACHED/NOT_REACHED (mobile guide).
3. Mobile guide `fromLocationId`/`toLocationId` vs actual `fromWarehouseId`/`toWarehouseId`.
4. Currency: order allows USD/CNY; offers inherit order currency (not fixed CNY).
5. SMS endpoints return empty (no sender) — empty ≠ bug.
6. Blacklist enforced only in feed list, not on `/feed/{id}` or offer submit (possible gap).
</content>
