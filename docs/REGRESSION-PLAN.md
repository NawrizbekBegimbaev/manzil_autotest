# Регресс-набор — план по фазам (tests/regression, DEV)

Покрываем библиотеку 1497 кейсов автотестами. Один тест ↔ один ID. Прогон на DEV,
staging (суточный UAT) не трогаем. Основной прогон: `-m "regression and not ratelimit
and not iplimit and not slow"` — только Passed/Failed/XFail, ноль skipped.

| Фаза | Модуль | Кейсы | Статус |
|---|---|---|---|
| 0 | Инфраструктура (dev-провизининг, фикстуры, coverage_map) | — | ✅ |
| 1 | API Auth / me / devices (`test_auth.py`) | 117 | ✅ 117/117 |
| 2 | API Super-admin (`test_superadmin.py`) | 166 | ✅ 166/166 |
| 3 | API Shipper (staff+orders, `test_shipper.py` + `test_shipper_orders.py`) | 182 | ✅ 182/182 (1 backend: SHP-182) |
| 4a | API Tendering/Transport (`test_tender_*.py`) | 157 | ✅ 157/157 (backend: TND-061) |
| 4b-i | API Warehouse/Dispatch (`test_warehouse_*.py`) | 138 | ✅ 138/138 (backend: 2, pending: 3, slow: WH-120) |
| 4b-ii | API Integrations/SMS · RBAC | ~205 | ⏳ |
| 5 | Web (Playwright) | 370 | ⏳ |
| 6 | Mobile (Maestro) | 119 | ⏳ |

## ✅ Отложенные кейсы (pending) — обнулены

- **API-SA-074** (division-склад CN/KG) — ЗАКРЫТ 2026-07-22 (`test_warehouse_division_resolve_074`).
- **API-SA-108/129** — закрыты в Фазе 3 (order-lifecycle хелпер).

**pending по всему набору = 0.** Backend-кейсы (не покрываются ЧЯ, считаются покрытыми):
AUTH-043/058/081, SA (нет), SHP-182, TND-061 — итого 5.


## Order-lifecycle хелпер (Фаза 3)

`OrderFactory.make(status)` строит заказ в любом статусе честной API-цепочкой (create→bid→select→
drivers+start→communication+goods-sent→complete; cancel из SELECTED). Teardown гонит в терминал +
удаляет. ACTIVE_STATUSES (блокируют удаление компании) = DRAFT/PUBLISHED/QUOTED/SELECTED/IN_WORK/
IN_TRANSIT. Refs (vehicleType + 2 локации) кэшируются по токену склада (лимит складов на пользователя).

## Находки (dev опережает staging — при промоуте обновить кейсы библиотеки)

- **MNZL-269** — DRIVER входит в `TRANSPORT_COMPANY_APP` (кейс API-AUTH-011: staging 403 → dev 200).
- **MNZL-245** — пагинация вложена в `page` (16 list-кейсов помечены; `_page` строгий по
  `cfg.page_shape`).
- **BUG-035** (MNZL-275, открыт) — гонка cancel/enter-1c → 500 вместо 409 (нет лока). SHP-080/116 xfail(strict).
- **BUG-038** (MNZL-280, открыт) — гонка attach одного водителя на два заказа → двойное назначение (лок на заказ, не на водителя). test_race_attach_driver_two_orders xfail(strict).
- **BUG-030/031** — по API-верификации КЛИЕНТСКИЕ (сервер отдаёт различимые коды / available по контракту).
