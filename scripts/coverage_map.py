#!/usr/bin/env python3
"""Coverage map: which testcase IDs from docs/testcases/ are covered by an
automated test or Maestro flow.

A case ID counts as *covered* if it appears anywhere in:
  * a Python test under tests/regression/ (docstring, parametrize id, comment), or
  * a Maestro flow filename or body under mobile/.

Prints per-file covered/total and an overall percentage. Exit code 0 always —
this is an informational control, not a gate (wire it into CI separately).

Run:  .venv/bin/python scripts/coverage_map.py [--missing]
"""

from __future__ import annotations

import glob
import json
import re
import sys

ID_RE = re.compile(r"\b(?:API|WEB|MOB)-[A-Z]+-\d{3}\b")


def case_ids_by_file() -> dict[str, list[str]]:
    # The 1497-case library lives strictly in these three layer dirs. Other dirs
    # under docs/testcases/ (data/, _refs/, _non-automatable/) are out of scope.
    out: dict[str, list[str]] = {}
    for layer in ("api", "web", "mobile"):
        for f in sorted(glob.glob(f"docs/testcases/{layer}/*.json")):
            rows = json.load(open(f, encoding="utf-8"))
            out[f] = [c["id"] for c in rows]
    return out


def covered_ids() -> set[str]:
    seen: set[str] = set()
    for f in glob.glob("tests/regression/**/*.py", recursive=True):
        seen |= set(ID_RE.findall(open(f, encoding="utf-8").read()))
    for f in glob.glob("mobile/**/*.yaml", recursive=True) + glob.glob("mobile/**/*.yml", recursive=True):
        seen |= set(ID_RE.findall(f))  # filename
        seen |= set(ID_RE.findall(open(f, encoding="utf-8").read()))
    return seen


def main() -> int:
    show_missing = "--missing" in sys.argv
    by_file = case_ids_by_file()
    covered = covered_ids()

    total = 0
    total_cov = 0
    print("=== Coverage map (ID кейса ↔ тест/флоу) ===\n")
    for f, ids in by_file.items():
        cov = [i for i in ids if i in covered]
        total += len(ids)
        total_cov += len(cov)
        pct = 100 * len(cov) / len(ids) if ids else 0
        print(f"{f.split('docs/testcases/')[-1]:40} {len(cov):4}/{len(ids):<4} {pct:5.1f}%")
        if show_missing and len(cov) < len(ids):
            miss = [i for i in ids if i not in covered]
            print("    не покрыто:", ", ".join(miss[:15]), ("…" if len(miss) > 15 else ""))

    pct = 100 * total_cov / total if total else 0
    print(f"\nИТОГО: {total_cov}/{total} = {pct:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
