"""Run Maestro flows from pytest (warehouse mobile UAT)."""

from __future__ import annotations

import os
import shutil
import subprocess

HOME = os.path.expanduser("~")
JAVA_HOME = os.environ.get("JAVA_HOME") or "/Applications/Android Studio.app/Contents/jbr/Contents/Home"
ANDROID_HOME = os.environ.get("ANDROID_HOME") or "/opt/homebrew/share/android-commandlinetools"
MAESTRO = os.path.join(HOME, ".maestro", "bin", "maestro")
ADB = os.path.join(ANDROID_HOME, "platform-tools", "adb")
APP_ID = "uz.logos.manzil.warehouse.staging"
FLOWS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mobile", "flows")


def _env() -> dict:
    e = dict(os.environ)
    e["JAVA_HOME"] = JAVA_HOME
    e["ANDROID_HOME"] = ANDROID_HOME
    e["ANDROID_SDK_ROOT"] = ANDROID_HOME
    e["PATH"] = f"{HOME}/.maestro/bin:{JAVA_HOME}/bin:{ANDROID_HOME}/platform-tools:{ANDROID_HOME}/emulator:" + e.get("PATH", "")
    return e


def emulator_ready() -> bool:
    if not (os.path.exists(MAESTRO) and os.path.exists(ADB)):
        return False
    try:
        out = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return False
    return any(line.strip().endswith("\tdevice") for line in out.splitlines()[1:])


def run_flow(flow: str, **env_vars) -> None:
    """Run a Maestro flow file under mobile/flows; raise AssertionError on failure."""
    cmd = [MAESTRO, "test", os.path.join(FLOWS, flow), "-e", f"APP_ID={APP_ID}"]
    for k, v in env_vars.items():
        cmd += ["-e", f"{k}={v}"]
    r = subprocess.run(cmd, env=_env(), capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        tail = (r.stdout or "")[-1500:] + "\n" + (r.stderr or "")[-500:]
        raise AssertionError(f"Maestro flow {flow} failed (rc={r.returncode}):\n{tail}")
