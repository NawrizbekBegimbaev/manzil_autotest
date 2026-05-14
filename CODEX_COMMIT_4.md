# CODEX_COMMIT_4.md — 8-й + 9-й коммиты (FIX_5 + Wave 3)

> **Контекст:** после 7-го коммита накопились две логически разные правки:
> 1. Один-файл fix submit_valid_offer (mutation теперь PASS на real device)
> 2. Wave 3 — Profile edit flows (8 flow, 16 параметризованных тестов)
>
> Делаем **2 атомарных коммита**. Каждый — отдельный logical change.

## Pre-check

```bash
git log --oneline -3
# Должно быть 7 коммитов (последний — e42c074 fix(mobile): Maestro 2.x compat...)

git status --short
# Ожидается:
#   M mobile/flows/driver/offers/submit_valid_offer.yaml
#   M pyproject.toml
#   ?? mobile/flows/driver/_common/login_and_open_profile.yaml
#   ?? mobile/flows/driver/_common/login_and_open_profile_edit.yaml
#   ?? mobile/flows/driver/profile/<8 yaml файлов>
#   ?? mobile/tests/driver/profile/

ruff check .
mypy --strict .
.venv/bin/pytest mobile/ --collect-only -q 2>&1 | tail -1   # 58 tests
```

Если что-то не сходится — стоп, доложить.

## Коммит 8 — `fix(mobile): submit_valid_offer tap by placeholder, not label`

Файлы:
```
mobile/flows/driver/offers/submit_valid_offer.yaml
```

Команда:
```bash
git add mobile/flows/driver/offers/submit_valid_offer.yaml
git status   # должен быть ровно 1 M

git commit -m "$(cat <<'EOF'
fix(mobile): submit_valid_offer tap by placeholder, not label

First mutation test run uncovered that `tapOn: text: "Izoh"` was tapping
the section label "Izoh" (group title above the input area), not the
EditText input itself. Result: both price and comment values went into
the Narx field, Yuborish button got obscured by an unsaved-changes popup,
and the test failed with `Element not found: Yuborish`.

Fix: tap by placeholder text instead of label. Placeholders ("Masalan,
1 200" for Narx and "Ixtiyoriy, 250 belgigacha" for Izoh) are inside the
actual input areas and disappear once the field has content — Maestro's
tapOn lands focus on the correct EditText.

Final assert also tightened: now waits for the price placeholder to
disappear (form closed) and explicitly verifies the "O'zgarishlar
saqlanmaydi" popup did not appear.

Result: mutation test passes on real Android emulator; creates a real
offer on dev backend (cleanup via maintenance task later).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

После — `git status` должен показать только W3 файлы (untracked + pyproject.toml M).

## Коммит 9 — `test(mobile): Wave 3 — driver profile edit flows`

Файлы:

**Новые:**
```
mobile/flows/driver/_common/login_and_open_profile.yaml
mobile/flows/driver/_common/login_and_open_profile_edit.yaml
mobile/flows/driver/profile/profile_sections_render.yaml
mobile/flows/driver/profile/edit_screen_opens.yaml
mobile/flows/driver/profile/save_disabled_unchanged.yaml
mobile/flows/driver/profile/edit_back_no_save.yaml
mobile/flows/driver/profile/edit_full_name.yaml
mobile/flows/driver/profile/edit_city.yaml
mobile/flows/driver/profile/edit_vehicle.yaml
mobile/flows/driver/profile/license_date_picker.yaml
mobile/tests/driver/profile/__init__.py
mobile/tests/driver/profile/test_sections_render.py
mobile/tests/driver/profile/test_edit_screen_opens.py
mobile/tests/driver/profile/test_save_disabled_unchanged.py
mobile/tests/driver/profile/test_edit_back_no_save.py
mobile/tests/driver/profile/test_edit_full_name.py
mobile/tests/driver/profile/test_edit_city.py
mobile/tests/driver/profile/test_edit_vehicle.py
mobile/tests/driver/profile/test_license_date_picker.py
```

**Модифицированный:**
```
pyproject.toml   (добавлен mobile.tests.driver.profile package)
```

Команда:
```bash
git add mobile/flows/driver/_common/login_and_open_profile.yaml \
        mobile/flows/driver/_common/login_and_open_profile_edit.yaml \
        mobile/flows/driver/profile/ \
        mobile/tests/driver/profile/ \
        pyproject.toml

git status   # должен быть чисто после этого

git commit -m "$(cat <<'EOF'
test(mobile): Wave 3 — driver profile edit flows

8 Maestro flows / 16 pytest tests (Android + iOS parametrized) covering
the driver Profile screen and its single shared edit form
"Profilni tahrirlash".

Read-only coverage:
- profile_sections_render: all three sections (Shaxsiy, Haydovchilik
  guvohnomasi, Transport) and their labeled fields are visible
- edit_screen_opens: tap Tahrirlash → full edit form renders with all
  fields and Saqlash button
- save_disabled_unchanged: Saqlash tap with no edits keeps the form open
- edit_back_no_save: system back from edit returns to profile view
- license_date_picker: tap Berilgan sana opens picker, OK closes back to
  edit form (date itself not mutated)

Mutation coverage (with `mutation` + `requires_real_account` markers):
- edit_full_name: opens edit, verifies F.I.O. field is editable (revert
  via UI was unreliable due to eraseText residue, so kept as no-save
  verification)
- edit_city: changes the "Nawrizbek_20" anomaly value to "Toshkent" —
  positive-edit test that also doubles as a one-time fix for the bad
  Shahar value on the test driver account
- edit_vehicle: changes Marka+Model (MAN TAHOE → SCANIA R450), saves,
  then reverts back

New reusable sub-flows:
- login_and_open_profile.yaml
- login_and_open_profile_edit.yaml

Coverage progress: ~20% → ~30% of senior manual QA work after this
wave. All 8 Android tests pass on Pixel emulator with the pre-registered
driver account; iOS tests skip pending the simulator-build ask in
BACKEND_ASKS.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

## Финальная проверка

```bash
git log --oneline                       # 9 коммитов
git status                              # должен быть полностью чистым
ruff check .                            # All checks passed!
mypy --strict .                         # Success
.venv/bin/pytest --collect-only -q 2>&1 | tail -1   # 598 tests
```

`git push` НЕ делать без явной команды.

## Чего НЕ делать

- НЕ объединять оба коммита в один. FIX_5 и W3 — разная логика.
- НЕ амендить предыдущие 7 коммитов.
- НЕ ставить `git commit -a` / `git add .` — стейджить только указанные пути.
- НЕ коммитить `.env`. Проверить `git status` после каждого `git add`.
- НЕ делать `git push`.
