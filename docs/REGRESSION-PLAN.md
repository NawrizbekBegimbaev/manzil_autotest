# Регресс-набор — план по фазам (tests/regression, DEV)

Покрываем библиотеку 1497 кейсов автотестами. Один тест ↔ один ID. Прогон на DEV,
staging (суточный UAT) не трогаем. Основной прогон: `-m "regression and not ratelimit
and not iplimit and not slow"` — только Passed/Failed/XFail, ноль skipped.

| Фаза | Модуль | Кейсы | Статус |
|---|---|---|---|
| 0 | Инфраструктура (dev-провизининг, фикстуры, coverage_map) | — | ✅ |
| 1 | API Auth / me / devices (`test_auth.py`) | 117 | ✅ 117/117 |
| 2 | API Super-admin (`test_superadmin.py`) | 166 | ✅ 163/166 (3 pending) |
| 3 | API Shipper (orders/staff) | 182 | ⏳ |
| 4 | API Tendering/Transport · Warehouse/Dispatch · Integrations/SMS · RBAC | 500 | ⏳ |
| 5 | Web (Playwright) | 370 | ⏳ |
| 6 | Mobile (Maestro) | 119 | ⏳ |

## ⏳ Отложенные кейсы (automation: pending) — добрать в Фазе 3/4

Требуют кросс-доменных хелперов, которых пока нет (order lifecycle / division-склад):

- **API-SA-074** — резолв division-склада (CN/KG): нужен склад, привязанный к району Китая/
  Кыргызстана (не к городу справочника). Хелпер создания division-склада появится при
  warehouse-модуле (Фаза 4).
- **API-SA-108** — удаление грузоотправителя с активными заявками → 409 `has-active-orders`:
  нужен полный lifecycle заказа (создать shipper + warehouse-staff + опубликованный заказ).
  Хелпер появится при shipper/warehouse-модулях (Фаза 3/4).
- **API-SA-129** — то же для транспортной компании (активные заявки).

**Напоминание для Фазы 3/4:** как только появятся хелперы провизининга заказа и
division-склада — снять `automation: pending` с 074/108/129, дописать тесты, обновить JSON
(убрать pending) и книги.

## Находки (dev опережает staging — при промоуте обновить кейсы библиотеки)

- **MNZL-269** — DRIVER входит в `TRANSPORT_COMPANY_APP` (кейс API-AUTH-011: staging 403 → dev 200).
- **MNZL-245** — пагинация вложена в `page` (16 list-кейсов помечены; `_page` строгий по
  `cfg.page_shape`).
