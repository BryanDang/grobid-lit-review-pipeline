#!/usr/bin/env python3
"""Stage 4, Verify: turn [ClaimRow] into (verified, residual). Deterministic checks come first.

Verification by residual narrowing. A cheap deterministic check tests
whether the claim's verbatim span exists in the stored source. The small residual is all
that would reach an adjudicator model.

Two deterministic checks:
  1. Span existence. The claim quote appears in the source text after whitespace normalization.
  2. Stat existence. Any metric_value appears in the source. Delegated to the outside stat_exists.py
     helper, which normalizes numbers and routes OCR cases.

A row that fails span existence is kept as residual data ("could not verify") in the
exception queue. Never a silent drop.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import ClaimRow

# Folder holding the outside helper stat_exists.py. Set LITREVIEW_STAT_SCRIPTS to its path.
_CSV_SCRIPTS = Path(os.environ["LITREVIEW_STAT_SCRIPTS"]) if os.environ.get("LITREVIEW_STAT_SCRIPTS") else None


def stat_script_available() -> bool:
    """True when the outside stat_exists.py helper is configured and present."""
    return _CSV_SCRIPTS is not None and (_CSV_SCRIPTS / "stat_exists.py").is_file()
_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    """Whitespace-normalize for substring comparison (collapse runs, strip)."""
    return _WS.sub(" ", text).strip()


@dataclass
class VerifyResult:
    """One row's verification outcome.

    Fields:
        row: the ClaimRow.
        span_ok: the claim's verbatim span exists in the source text (deterministic).
        stat_ok: metric_value verified by stat_exists, or True if no metric_value / None
            if not applicable. False only on a hard stat miss.
        reason: why it landed where it did (for the exception queue / residual).
    """

    row: ClaimRow
    span_ok: bool
    stat_ok: bool | None
    reason: str = ""


def span_exists(quote: str, source_text: str) -> bool:
    """True iff the (whitespace-normalized) quote is a substring of the source text.

    The deterministic span-existence check, the load-bearing guard. The extractor is not
    trusted. The string has to be in the source.
    """
    return _norm(quote) in _norm(source_text)


def stat_exists(stat: str, source_path: str | Path, queue: str | Path) -> bool:
    """Call the outside stat_exists.py helper (number normalization and OCR).

    Returns True if the script exits 0 (found, or routed to queue). A hard error (exit 1,
    e.g. file not found) raises. Numbers from OCR/`math: approximate` sources are routed
    to the queue by the script, never hard-failed.
    """
    if not stat_script_available():
        # Helper missing: the stat stays unverified and the row goes to the exception queue.
        return False
    script = _CSV_SCRIPTS / "stat_exists.py"
    proc = subprocess.run(
        ["python3", str(script), "--stat", stat, "--source", str(source_path),
         "--queue", str(queue)],
        capture_output=True, text=True,
    )
    if proc.returncode == 1:
        raise RuntimeError(f"stat_exists hard error: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.returncode == 0


def verify(rows: list[ClaimRow], source_text: str, source_path: str | Path,
           queue: str | Path) -> tuple[list[ClaimRow], list[VerifyResult]]:
    """Split rows into (verified, residual) by deterministic checks.

    Args:
        rows: the extracted ClaimRows for one document.
        source_text: the stored plaintext source (for the span-existence check).
        source_path: path to that source file (for stat_exists delegation).
        queue: path to the stat_exists exception-queue JSONL.

    Returns:
        (verified, residual). verified = rows whose claim span exists in the source AND
        whose metric_value (if any) passed stat_exists. residual = VerifyResult records
        for rows that failed either check (routed to exception queue by the caller).

    Invariants:
        no row is dropped: every input row is in exactly one of (verified, residual-list).
        residual carries a reason so "could not verify" is data, not silence.
    """
    verified: list[ClaimRow] = []
    residual: list[VerifyResult] = []
    for row in rows:
        # Two deterministic conditions, both required for span_ok:
        #   (a) the cited span really exists verbatim in the source, AND
        #   (b) the model's `claim` text is grounded IN that span (a verbatim substring).
        # (b) is the anti-hallucination guard: a paraphrased/invented claim that is not
        # literally in its own cited span is caught here, not trusted.
        span_in_source = span_exists(row.claim_source_span.verbatim_text, source_text)
        claim_in_span = _norm(row.claim) in _norm(row.claim_source_span.verbatim_text)
        s_ok = span_in_source and claim_in_span
        stat_ok: bool | None = None
        if row.metric_value is not None:
            stat_ok = stat_exists(str(row.metric_value), source_path, queue)
        row_ok = s_ok and (stat_ok is not False)
        if row_ok:
            verified.append(row)
        else:
            reason = []
            if not span_in_source:
                reason.append("cited span not found verbatim in source")
            if not claim_in_span:
                reason.append("claim text not grounded in its cited span (paraphrase/hallucination)")
            if stat_ok is False:
                reason.append(f"metric_value {row.metric_value} not found in source")
            residual.append(VerifyResult(row, s_ok, stat_ok, "; ".join(reason)))
    return verified, residual
