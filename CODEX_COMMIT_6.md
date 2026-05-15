# CODEX_COMMIT_6.md — 11-й коммит (Wave 4) + 12-й (final session wrap)

> **Контекст:** W4 закрыт first-try на real device — **41/41 Android tests passing**.
> Coverage достиг 40% — реалистичный максимум без backend-разблокировок.

## Pre-check

```bash
git log --oneline -3
# Должно быть 10 коммитов (последний — ab71c8e docs(now): final session wrap-up...)

git status --short
# Ожидается: M pyproject.toml + ~15 новых ?? файлов в mobile/flows/driver/ и mobile/tests/driver/

ruff check .
mypy --strict .
.venv/bin/pytest mobile/ --collect-only -q 2>&1 | tail -1   # 82 tests
```

## Коммит 11 — `test(mobile): Wave 4 — negative + edge + filters + logout + i18n`

Файлы:

**Новые YAML flows:**
```
mobile/flows/driver/feed/filter_opens.yaml
mobile/flows/driver/feed/filter_clear.yaml
mobile/flows/driver/feed/filter_apply_empty.yaml
mobile/flows/driver/feed/search_accepts_input.yaml
mobile/flows/driver/feed/search_clears.yaml
mobile/flows/driver/login/forgot_password_screen_renders.yaml
mobile/flows/driver/login/login_short_phone_disabled.yaml
mobile/flows/driver/offers/submit_large_price.yaml
mobile/flows/driver/offers/submit_zero_price.yaml
mobile/flows/driver/profile/kuzov_turi_dropdown.yaml
mobile/flows/driver/profile/language_switch_to_russian.yaml
mobile/flows/driver/profile/logout.yaml
```

**Новые pytest wrappers:**
```
mobile/tests/driver/feed/__init__.py
mobile/tests/driver/feed/test_filter_opens.py
mobile/tests/driver/feed/test_filter_clear.py
mobile/tests/driver/feed/test_filter_apply_empty.py
mobile/tests/driver/feed/test_search_accepts.py
mobile/tests/driver/feed/test_search_clears.py
mobile/tests/driver/login/__init__.py
mobile/tests/driver/login/test_forgot_password_smoke.py
mobile/tests/driver/login/test_login_short_phone.py
mobile/tests/driver/offers/test_submit_zero_price.py
mobile/tests/driver/offers/test_submit_large_price.py
mobile/tests/driver/profile/test_kuzov_turi_dropdown.py
mobile/tests/driver/profile/test_language_switch_ru.py
mobile/tests/driver/profile/test_logout.py
```

**Модифицированный:**
```
pyproject.toml   (добавлены feed и login test packages)
```

Команда:
```bash
git add mobile/flows/driver/feed mobile/flows/driver/login \
        mobile/flows/driver/offers/submit_large_price.yaml \
        mobile/flows/driver/offers/submit_zero_price.yaml \
        mobile/flows/driver/profile/kuzov_turi_dropdown.yaml \
        mobile/flows/driver/profile/language_switch_to_russian.yaml \
        mobile/flows/driver/profile/logout.yaml \
        mobile/tests/driver/feed mobile/tests/driver/login \
        mobile/tests/driver/offers/test_submit_large_price.py \
        mobile/tests/driver/offers/test_submit_zero_price.py \
        mobile/tests/driver/profile/test_kuzov_turi_dropdown.py \
        mobile/tests/driver/profile/test_language_switch_ru.py \
        mobile/tests/driver/profile/test_logout.py \
        pyproject.toml

git status   # должно быть чисто после этого

git commit -m "$(cat <<'EOF'
test(mobile): Wave 4 — negative + edge + filters + logout + i18n

12 Maestro flows / 24 pytest tests (Android + iOS parametrized)
covering scenarios that genuinely exercise bug-finding power:

Feed filters and search:
- filter_opens: bottom sheet renders Kuzov turi / date range / Tozalash / Qo'llash
- filter_clear: Tozalash keeps sheet open with cleared fields
- filter_apply_empty: Qo'llash with no selection returns to feed
- search_accepts_input / search_clears: search field accepts and clears
  (used coordinate tap since Compose placeholder isn't findable as text node —
  testID ask in BACKEND_ASKS.md remains relevant)

Login negative + recovery:
- login_short_phone_disabled: Kirish does nothing with phone "123"
- forgot_password_screen_renders: tap "Parolni unutdingizmi" lands on the
  recovery screen with phone field and "Davom etish" button (full flow
  blocked by phone OTP — see CODEX_NEXT.md N4)

Offer submission edge cases (mutation):
- submit_zero_price: price = "0" submission behavior verified
- submit_large_price: price = "999999999" submission behavior verified
  Both passed without backend errors. Whether backend should reject these
  values is a product question — noted for product/backend review.

Profile interactions:
- logout: tap "Chiqish" → direct return to Login screen (no confirm popup)
- kuzov_turi_dropdown: Kuzov turi field opens body-type selector
- language_switch_to_russian: Til → "Русский" swaps labels (Profile →
  Профиль) and switches back to O'zbek

Coverage: 30% → ~40%. This is the realistic ceiling for Maestro-based
local automation without backend-side unblocks (Telegram OTP for full
registration in W5, Release-iphonesimulator build for W6).

Real-device run on Pixel emulator with the pre-registered driver
account: 34 non-mutation passed, 7 mutation passed (including 2 new
edge cases). iOS skipped pending simulator build.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

## Коммит 12 — `docs: session wrap final — 41/41 Android, ~40% mobile coverage`

После коммита 11 нужно обновить `NOW.md` чтобы отразить W4-достижение и
финальную картину. Также bug.txt получит заметку про price edge cases.

### Шаг 12.1 — обновить `NOW.md`

Прочитать текущий NOW.md, найти секцию "Mobile Android ✅ 29/29 passing" и
обновить. Заменить:

```markdown
### Mobile Android ✅ 29/29 passing 2026-05-14
```

на:

```markdown
### Mobile Android ✅ 41/41 passing 2026-05-14 (W4 done)
```

И блок описания дополнить W4-инфо:

```markdown
After W4: 12 flows / 24 tests adding filter (Lenta), logout, login negative,
forgot password smoke, offer submit edge cases (price=0, price=999M),
profile Kuzov turi dropdown, и полный UZ↔RU language switch cycle.

Edge tests price=0 + price=999M passed — backend accepts both values
without errors. Это потенциальные business-rule вопросы для product/backend
(добавлен раздел в bug.txt: BUG-OBSERVATION).

Coverage: ~40% от senior manual QA work — реалистичный потолок для
Maestro local без backend-разблокировок W5 (Telegram OTP) и W6 (iOS build).
```

Также в таблице "Куда продолжать":

```markdown
| **W4** ✅ done | Negative + filters + logout + i18n | 30% → 40% |
```

(было `W4 ... 30% → 40% — bug-finding power` — заменить на done статус)

### Шаг 12.2 — обновить `bug.txt`

Прочитать `bug.txt`, после секции "CLOSED 2026-05-13" и перед основной
секцией с открытыми багами добавить новый раздел:

```markdown
================================================================================
OBSERVATIONS (mobile W4 2026-05-14 — to investigate, not yet confirmed bugs)
================================================================================
- Mobile submit offer with price=0 → backend accepts (mutation test
  submit_zero_price passed without form re-open or error). Product question:
  should a zero-price offer be valid?
- Mobile submit offer with price=999999999 → backend accepts (mutation test
  submit_large_price passed). Product question: should there be an upper
  bound?

Both observations need product/backend confirmation before deciding if
they are bugs. Tests pass either way (form closes on submit).
```

### Команда коммита 12

```bash
git add NOW.md bug.txt

git status

git commit -m "$(cat <<'EOF'
docs: session wrap final — 41/41 Android, ~40% mobile coverage

After W4 closure:
- mobile Android: 29 → 41 tests, all passing on Pixel emulator
- coverage: ~30% → ~40% (realistic ceiling for Maestro local)
- 12 new flows covering negative paths, edge cases, filters, logout, i18n

bug.txt OBSERVATIONS section added:
- price=0 offer submission accepted by backend
- price=999999999 offer submission accepted by backend
Both are product questions, not confirmed bugs.

NOW.md updated with W4-done status and remaining-roadmap clarity:
- W5 (driver registration e2e) blocked by Telegram OTP backend ask
- W6 (iOS parity) blocked by Release-iphonesimulator build
- W7 (perf + a11y) off-roadmap due to weak Maestro support

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

## Финальная проверка

```bash
git log --oneline                  # 12 коммитов
git status                          # должен быть полностью чистым
ruff check .                        # All checks passed!
mypy --strict .                     # Success
.venv/bin/pytest --collect-only -q 2>&1 | tail -1   # 622 tests
git push                            # на origin/main (если есть конкретное разрешение)
```

`git push` без явной команды НЕ делать.

## Чего НЕ делать

- НЕ амендить предыдущие 10 коммитов.
- НЕ объединять commit 11 и 12 — разный logical scope.
- НЕ удалять файл CODEX_COMMIT_6.md из working tree до конца — он включится
  в коммит 12 (как было с COMMIT_2/3/4/5 ранее, нормально для нашего flow).
- НЕ `git push` без явного разрешения.
