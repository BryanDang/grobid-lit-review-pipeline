#!/usr/bin/env python3
"""Corpus integrity checker (pre-commit guard) — JSONL-native adaptation.

Adapted from a CSV-based integrity check for a JSONL master. The guard setup script
refuses iCloud dirs, so the corpus uses a separate git dir (2026-07-09).

Enforces, for every row in master.jsonl:
  1. required fields present + typed (schema.json);
  2. its fragment file exists (fragments/<doc_id-slug>__<row_id>.txt) and matches the
     row's claim_source_span.verbatim_text;
  3. that verbatim quote appears in the stored source (sources/<doc_id-slug>.txt) — the
     span-existence guard, in pre-commit form so bad data cannot survive a commit.

Exit 0 = clean; exit 1 = one or more violations (printed). No network, no model.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WS = re.compile(r"\s+")


def _norm(t: str) -> str:
    return WS.sub(" ", t).strip()


def _slug(doc_id: str) -> str:
    return doc_id.replace(":", "_").replace("/", "_")


def main() -> int:
    schema = json.loads((ROOT / "schema.json").read_text())
    required = [c for c, spec in schema["columns"].items() if spec.get("required")]
    master = ROOT / "master.jsonl"
    if not master.exists():
        print("OK: no master.jsonl yet (empty corpus)")
        return 0

    violations: list[str] = []
    for i, line in enumerate(master.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        for field in required:
            if field not in row or row[field] in (None, ""):
                violations.append(f"row {i} ({row.get('row_id','?')}): missing required '{field}'")
        span = row.get("claim_source_span") or {}
        quote = span.get("verbatim_text", "")
        doc_id = row.get("doc_id", "")
        row_id = row.get("row_id", "")

        frag = ROOT / "fragments" / f"{_slug(doc_id)}__{row_id}.txt"
        if not frag.exists():
            violations.append(f"row {i} ({row_id}): missing fragment file {frag.name}")
        elif _norm(frag.read_text()) != _norm(quote):
            violations.append(f"row {i} ({row_id}): fragment != claim_source_span text")

        src = ROOT / "sources" / f"{_slug(doc_id)}.txt"
        if not src.exists():
            violations.append(f"row {i} ({row_id}): missing source {src.name}")
        elif _norm(quote) not in _norm(src.read_text()):
            violations.append(f"row {i} ({row_id}): claim span NOT found verbatim in source")

    if violations:
        print("INTEGRITY VIOLATIONS:")
        for v in violations:
            print("  -", v)
        return 1
    print(f"OK: master.jsonl integrity verified ({master.read_text().count(chr(10))} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
