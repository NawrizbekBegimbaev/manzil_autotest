# Backend / Frontend Asks

## Frontend: testID/testTag on mobile UI

**Problem:** Android Compose `resource-id` is empty, and iOS accessibility
identifier is likely empty as well. Mobile tests are forced to use text-based
locators, which are brittle across branding and translation changes.

**Ask:** add stable identifiers to key elements such as Kirish/Tizimga kirish
buttons, phone/password fields, and Lenta/Takliflarim/Profil tabs:

- Android Compose: `Modifier.testTag("login.submitButton")`
- iOS SwiftUI: `.accessibilityIdentifier("login.submitButton")`

**Convention:** `<screen>.<element>` in kebab-case or camelCase.

**Impact:** unlocks robust mobile tests and should reduce mobile UI flakiness
substantially.

---

## Mobile (iOS): build .app для симулятора

**Problem:** текущий iOS-билд раздаётся через Diawi как `.ipa`, подписанный
для real device. Для запуска на iOS Simulator (стандартный QA-workflow)
такой `.ipa` не подходит: симулятору нужна другая архитектура
(`arm64-iphonesimulator`) и другой SDK (`iphonesimulator`).

Diawi-`.ipa` мы пытались поставить — `xcrun simctl install` принимает, но
`xcrun simctl launch` падает с `SBMainWorkspace denied` потому что:
- бинарь собран как `Debug` с `Dynamic Replacement` (split на stub + dylib)
- архитектура для device, не simulator

Real-device Maestro automation требует Apple Developer аккаунт + WebDriverAgent
re-signing каждые 7 дней — это не подходит для QA-flow.

**Ask:** собрать `.app` бандл специально для симулятора:

```bash
xcodebuild -workspace Manzil.xcworkspace \
  -scheme "Manzil Driver" \
  -configuration Release \
  -sdk iphonesimulator \
  -derivedDataPath ./build \
  build
```

Получившийся `./build/Build/Products/Release-iphonesimulator/Manzil.app` —
это директория. Архивировать в zip целиком и прислать.

После получения:
```bash
unzip Manzil-simulator.zip -d ~/Manzil-mobile/
xcrun simctl install booted ~/Manzil-mobile/Manzil.app
# затем заполнить IOS_APP_ID + IOS_APP_PATH в .env и прогнать pytest mobile/ -k ios
```

**Impact:** разблокирует ~50% mobile coverage на iOS (сейчас 0% — все тесты
скипаются без `IOS_APP_PATH`). Не требует Apple Developer аккаунта от QA.
