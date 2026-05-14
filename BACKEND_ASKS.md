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
