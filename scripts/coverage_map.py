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


def _ids_with_automation(value: str) -> set[str]:
    ids: set[str] = set()
    for layer in ("api", "web", "mobile"):
        for f in glob.glob(f"docs/testcases/{layer}/*.json"):
            for c in json.load(open(f, encoding="utf-8")):
                if c.get("automation") == value:
                    ids.add(c["id"])
    return ids


def backend_ids() -> set[str]:
    """IDs marked `automation: backend` — accounted for by backend integration tests
    (see docs/testcases/NON-AUTO.md); counted as covered."""
    return _ids_with_automation("backend")


def pending_ids() -> set[str]:
    """IDs marked `automation: pending` — deferred (need cross-domain helpers).
    NOT counted as covered; reported on their own line."""
    return _ids_with_automation("pending")


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
    pending = pending_ids()
    accounted = covered | backend  # test-covered OR backend-integration-tracked (pending is NOT here)

    total = 0
    total_acc = 0
    total_backend = 0
    total_pending = 0
    print("=== Coverage map (ID кейса ↔ тест/флоу; backend=covered, pending=deferred) ===\n")
    for f, ids in by_file.items():
        acc = [i for i in ids if i in accounted]
        be = [i for i in ids if i in backend]
        pe = [i for i in ids if i in pending]
        total += len(ids)
        total_acc += len(acc)
        total_backend += len(be)
        total_pending += len(pe)
        pct = 100 * len(acc) / len(ids) if ids else 0
        tail = "".join([f"  (backend: {len(be)})" if be else "", f"  (pending: {len(pe)})" if pe else ""])
        print(f"{f.split('docs/testcases/')[-1]:40} {len(acc):4}/{len(ids):<4} {pct:5.1f}%{tail}")
        if show_missing and len(acc) < len(ids):
            miss = [i for i in ids if i not in accounted and i not in pending]
            if miss:
                print("    не покрыто:", ", ".join(miss[:15]), ("…" if len(miss) > 15 else ""))
            if pe:
                print("    ⏳ pending:", ", ".join(pe))

    pct = 100 * total_acc / total if total else 0
    print(f"\nИТОГО: {total_acc}/{total} = {pct:.1f}%  (backend: {total_backend}, pending/отложено: {total_pending})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
