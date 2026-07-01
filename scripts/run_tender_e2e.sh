#!/usr/bin/env bash
# Cross-role tender E2E: mobile publishes an order → web carrier offers → web
# shipper selects the winner. Provisions its own tenants and cleans them up.
#
# Needs: a running Android emulator/device with the staging warehouse APK,
# Maestro CLI, and .env with SUPER_ADMIN creds + NEW_ACCOUNT_PASSWORD.
set -euo pipefail
cd "$(dirname "$0")/.."

export JAVA_HOME="${JAVA_HOME:-/Applications/Android Studio.app/Contents/jbr/Contents/Home}"
export ANDROID_HOME="${ANDROID_HOME:-/opt/homebrew/share/android-commandlinetools}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$HOME/.maestro/bin:$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"
export ADB="$ANDROID_HOME/platform-tools/adb"

command -v maestro >/dev/null 2>&1 || { echo "maestro CLI not found (~/.maestro/bin)." >&2; exit 1; }
if ! "$ADB" devices | sed '1d' | grep -qw device; then
  echo "No Android device/emulator detected. Start one: emulator -avd manzil &" >&2
  exit 1
fi

PY="${VENV:-.venv}/bin/python"
exec "$PY" scripts/tender_e2e.py
