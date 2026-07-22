# Не автоматизируется чёрным ящиком (`automation: backend`)

Эти кейсы **намеренно не входят** в чёрно-ящичный регресс-набор — их нельзя
воспроизвести только через публичный API (fault injection, подделка JWT, общий
IP-бакет, реальное ожидание времени, заголовки за прокси). Они покрываются
**backend-интеграционными тестами** в `manzil-core`, а здесь учтены, чтобы
coverage-map их засчитывал и в отчётах не было `skipped`.

Всего: **4**.

| Слой | ID | Сценарий | Почему только backend |
|---|---|---|---|
| api | API-AUTH-043 | IP определяется по правому хопу X-Forwarded-For | X-Forwarded-For правый хоп — nginx перебивает заголовок, извне не задать; backend-тест резолвера IP. |
| api | API-AUTH-058 | Refresh fail-open при неразрешимом аккаунте (defensive) | Refresh fail-open при внутреннем сбое БД — fault injection; backend-тест с моком сбоя. |
| api | API-AUTH-081 | Валидный JWT, но subject не UUID → 401 (локализованный, другой code) | JWT с не-UUID subject — нужен ключ подписи Keycloak; backend/security-тест. |
| api | API-SHP-182 | Негатив: пользователь без shipperCompanyId → 403 |  |
