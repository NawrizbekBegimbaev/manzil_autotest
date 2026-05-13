# Mobile tests (Maestro)

## Setup

Install Maestro once on macOS:

```bash
curl -Ls "https://get.maestro.mobile.dev" | bash
# or
brew tap mobile-dev-inc/tap && brew install maestro

maestro --version
```

Prepare devices:

```bash
# Android
emulator -avd Pixel_7_API_34

# iOS
xcrun simctl boot "iPhone 15"
open -a Simulator
```

Install the app once:

```bash
# Android
adb install /path/to/manzil-driver.apk

# iOS simulator
xcrun simctl install booted /path/to/Manzil.app
```

Fill `.env`:

```bash
ANDROID_APP_ID=uz.manzil.driver
IOS_APP_ID=uz.manzil.driver
```

See `.env.example` for the full list of mobile settings.

## Run

```bash
pytest mobile/
pytest mobile/ -m mobile_smoke
pytest mobile/ -k android
maestro test mobile/flows/smoke/app_launches.yaml --env APP_ID=uz.manzil.driver
```

## Structure

- `flows/` - Maestro YAML flows.
- `flows/_common/` - shared sub-flows for `runFlow:`.
- `runner/` - Python wrapper around `maestro test`.
- `seed/` - API setup through `api/client.py`.
- `tests/` - pytest tests that call flows through the `maestro` fixture.
