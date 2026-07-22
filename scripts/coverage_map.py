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


def backend_ids() -> set[str]:
    """IDs marked `automation: backend` in the JSON — accounted for by backend
    integration tests, not our black-box suite (see docs/testcases/NON-AUTO.md)."""
    ids: set[str] = set()
    for layer in ("api", "web", "mobile"):
        for f in glob.glob(f"docs/testcases/{layer}/*.json"):
            for c in json.load(open(f, encoding="utf-8")):
                if c.get("automation") == "backend":
                    ids.add(c["id"])
    return ids


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
    backend = backend_ids()
    accounted = covered | backend  # test-covered OR backend-integration-tracked

    total = 0
    total_acc = 0
    total_backend = 0
    print("=== Coverage map (ID кейса ↔ тест/флоу; +automation:backend) ===\n")
    for f, ids in by_file.items():
        acc = [i for i in ids if i in accounted]
        be = [i for i in ids if i in backend]
        total += len(ids)
        total_acc += len(acc)
        total_backend += len(be)
        pct = 100 * len(acc) / len(ids) if ids else 0
        tail = f"  (backend: {len(be)})" if be else ""
        print(f"{f.split('docs/testcases/')[-1]:40} {len(acc):4}/{len(ids):<4} {pct:5.1f}%{tail}")
        if show_missing and len(acc) < len(ids):
            miss = [i for i in ids if i not in accounted]
            print("    не учтено:", ", ".join(miss[:15]), ("…" if len(miss) > 15 else ""))

    pct = 100 * total_acc / total if total else 0
    print(f"\nИТОГО: {total_acc}/{total} = {pct:.1f}%  (из них automation:backend — {total_backend})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
