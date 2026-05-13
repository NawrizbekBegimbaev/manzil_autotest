"""Thin wrapper over the `maestro test` CLI.

Pytest wraps Maestro YAML so tests can prepare data through the API before a
flow, verify post-conditions after it, and always clean up in fixtures.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class MaestroNotInstalled(RuntimeError):
    """Raised when `maestro` is not available in PATH."""


@dataclass(frozen=True)
class MaestroResult:
    """Result of a single Maestro flow run."""

    flow: Path
    returncode: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def check_maestro_installed() -> str:
    """Return the installed Maestro version or raise if the CLI is missing."""
    if shutil.which("maestro") is None:
        raise MaestroNotInstalled(
            "Maestro CLI not found. Install it with "
            "`curl -Ls 'https://get.maestro.mobile.dev' | bash` "
            "or `brew install maestro`."
        )
    result = subprocess.run(
        ["maestro", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    version = result.stdout.strip() or result.stderr.strip()
    return version


def run_flow(
    flow_path: Path,
    *,
    params: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
    platform: str | None = None,
    timeout_s: int = 600,
) -> MaestroResult:
    """Run one Maestro flow and return stdout, stderr, and exit code."""
    if not flow_path.exists():
        raise FileNotFoundError(flow_path)

    cmd = ["maestro", "test", str(flow_path)]
    merged_params = dict(params or {})
    if platform is not None:
        merged_params.setdefault("PLATFORM", platform)
    for key, value in merged_params.items():
        cmd.extend(["--env", f"{key}={value}"])

    merged_env = {**os.environ}
    if env:
        merged_env.update(env)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env=merged_env,
        check=False,
    )
    return MaestroResult(
        flow=flow_path,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
