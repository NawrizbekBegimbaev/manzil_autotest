#!/usr/bin/env bash
# Daily MOBILE (Android, Maestro) sanity. Runs the warehouse flows the web suite
# can't cover (order creation is mobile-only). Each create-order run publishes a
# REAL order on staging under the configured warehouse account.
#
# Prerequisites (set up locally 2026-06-23 — see mobile/README.md):
#   - Maestro CLI (~/.maestro/bin)
#   - Android SDK at /opt/homebrew/share/android-commandlinetools (adb, emulator)
#   - Java: Android Studio JBR
#   - A running emulator/device with the staging APK installed
#   - mobile/config/maestro.env  (APP_ID + warehouse creds)
set -euo pipefail
cd "$(dirname "$0")/.."

# Self-contained toolchain env (override by exporting before the call).
export JAVA_HOME="${JAVA_HOME:-/Applications/Android Studio.app/Contents/jbr/Contents/Home}"
export ANDROID_HOME="${ANDROID_HOME:-/opt/homebrew/share/android-commandlinetools}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$HOME/.maestro/bin:$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

ENV_FILE="config/maestro.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE — copy config/maestro.env.example and fill it." >&2
  exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

command -v maestro >/dev/null 2>&1 || { echo "maestro CLI not found (~/.maestro/bin)." >&2; exit 1; }
if ! adb devices | sed '1d' | grep -qw device; then
  echo "No Android device/emulator detected. Start one: emulator -avd manzil &" >&2
  exit 1
fi

mkdir -p ../reports
maestro test flows/ \
  -e APP_ID="$APP_ID" \
  -e WAREHOUSE_PHONE="$WAREHOUSE_PHONE" \
  -e WAREHOUSE_PASSWORD="$WAREHOUSE_PASSWORD" \
  --format junit --output ../reports/mobile-junit.xml

echo "Mobile sanity finished. Report: reports/mobile-junit.xml"
