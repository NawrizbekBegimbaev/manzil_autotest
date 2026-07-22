# Регресс-набор — план по фазам (tests/regression, DEV)

Покрываем библиотеку 1497 кейсов автотестами. Один тест ↔ один ID. Прогон на DEV,
staging (суточный UAT) не трогаем. Основной прогон: `-m "regression and not ratelimit
and not iplimit and not slow"` — только Passed/Failed/XFail, ноль skipped.

| Фаза | Модуль | Кейсы | Статус |
|---|---|---|---|
| 0 | Инфраструктура (dev-провизининг, фикстуры, coverage_map) | — | ✅ |
| 1 | API Auth / me / devices (`test_auth.py`) | 117 | ✅ 117/117 |
| 2 | API Super-admin (`test_superadmin.py`) | 166 | ✅ 165/166 (1 pending: SA-074) |
| 3 | API Shipper (staff+orders, `test_shipper.py` + `test_shipper_orders.py`) | 182 | ✅ 182/182 (1 backend: SHP-182) |
| 4 | API Tendering/Transport · Warehouse/Dispatch · Integrations/SMS · RBAC | 500 | ⏳ |
| 5 | Web (Playwright) | 370 | ⏳ |
| 6 | Mobile (Maestro) | 119 | ⏳ |

## ⏳ Отложенные кейсы (automation: pending) — добрать в Фазе 4

- **API-SA-074** — резолв division-склада (CN/KG): нужен склад, привязанный к району Китая/
  Кыргызстана (не к городу справочника). Хелпер создания division-склада появится при
  warehouse/dispatch-модуле (Фаза 4). **Единственный оставшийся pending.**

**Снято в Фазе 3** (order-lifecycle хелпер `tests/regression/order_lifecycle.py::OrderFactory`):
- ✅ **API-SA-108/129** — удаление shipper/transport с активными заявками → 409 `has-active-orders`
  (`test_superadmin.py::test_shipper_delete_active_orders_409_108` / `..._transport_..._129`).

## Order-lifecycle хелпер (Фаза 3)

`OrderFactory.make(status)` строит заказ в любом статусе честной API-цепочкой (create→bid→select→
drivers+start→communication+goods-sent→complete; cancel из SELECTED). Teardown гонит в терминал +
удаляет. ACTIVE_STATUSES (блокируют удаление компании) = DRAFT/PUBLISHED/QUOTED/SELECTED/IN_WORK/
IN_TRANSIT. Refs (vehicleType + 2 локации) кэшируются по токену склада (лимит складов на пользователя).

## Находки (dev опережает staging — при промоуте обновить кейсы библиотеки)

- **MNZL-269** — DRIVER входит в `TRANSPORT_COMPANY_APP` (кейс API-AUTH-011: staging 403 → dev 200).
- **MNZL-245** — пагинация вложена в `page` (16 list-кейсов помечены; `_page` строгий по
  `cfg.page_shape`).
- **BUG-035** (открыт) — гонка cancel/enter-1c заказа отдаёт 500 вместо 409 concurrent-modification
  (нет пессимистичного лока, `@Version`-конфликт не мапится). Тесты SHP-080/116 — `xfail(strict)`.
