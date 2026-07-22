#!/usr/bin/env python3
"""Generate docs/testcases/NON-AUTO.md from cases marked `automation: backend`.

These cases are intentionally NOT in the black-box suite (they need fault injection,
a forged JWT, the shared IP bucket, real time passage, or proxy-owned headers). They
are covered by backend integration tests in manzil-core and tracked here so the
coverage map still accounts for them and reports show no skips.

Run:  .venv/bin/python scripts/build_non_auto.py
"""

from __future__ import annotations

import glob
import json

OUT = "docs/testcases/NON-AUTO.md"


def main() -> int:
    rows: list[dict] = []
    for layer in ("api", "web", "mobile"):
        for f in sorted(glob.glob(f"docs/testcases/{layer}/*.json")):
            for c in json.load(open(f, encoding="utf-8")):
                if c.get("automation") == "backend":
                    rows.append({"layer": layer, "id": c["id"], "scenario": c.get("scenario", ""),
                                 "note": c.get("automationNote", "")})
    rows.sort(key=lambda r: r["id"])

    lines = [
        "# Не автоматизируется чёрным ящиком (`automation: backend`)",
        "",
        "Эти кейсы **намеренно не входят** в чёрно-ящичный регресс-набор — их нельзя",
        "воспроизвести только через публичный API (fault injection, подделка JWT, общий",
        "IP-бакет, реальное ожидание времени, заголовки за прокси). Они покрываются",
        "**backend-интеграционными тестами** в `manzil-core`, а здесь учтены, чтобы",
        "coverage-map их засчитывал и в отчётах не было `skipped`.",
        "",
        f"Всего: **{len(rows)}**.",
        "",
        "| Слой | ID | Сценарий | Почему только backend |",
        "|---|---|---|---|",
    ]
    for r in rows:
        scn = r["scenario"].replace("|", "\\|")
        note = r["note"].replace("|", "\\|")
        lines.append(f"| {r['layer']} | {r['id']} | {scn} | {note} |")
    lines.append("")

    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    print(f"{OUT}: {len(rows)} кейсов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
