#!/usr/bin/env python3
"""Regression tests for the deterministic verify stage (residual narrowing).

Locks in the anti-hallucination guard. A claim is grounded in its cited span, and the span
exists in the source. A paraphrase that is not literally in its span is residual, not
verified. Caught a real gap in the 2026-07-09 dry-run. Permanent fixture.
"""
import tempfile
from pathlib import Path

import pytest  # noqa: E402
from litreview.verify import stat_script_available  # noqa: E402

needs_stat_script = pytest.mark.skipif(
    not stat_script_available(), reason="set LITREVIEW_STAT_SCRIPTS to run")
from litreview.models import ClaimRow, Span
from litreview.verify import verify

SOURCE = (
    "## 3 Discovering the circuit\n"
    "We discover a circuit of 26 attention heads that completes the bulk of this task. "
    "To our surprise, the circuit still worked (only 5% drop in logit difference)."
)


def _row(row_id, claim, quote, metric_value=None):
    sp = Span(doc_id="arXiv:x", verbatim_text=quote, char_offsets=(0, len(quote)),
              section_tag="3 Discovering the circuit")
    return ClaimRow(row_id=row_id, doc_id="arXiv:x", method="m", claim=claim,
                    claim_source_span=sp, metric_value=metric_value)


def _run(rows):
    with tempfile.TemporaryDirectory() as d:
        src_path = Path(d) / "src.txt"
        src_path.write_text(SOURCE)
        return verify(rows, SOURCE, src_path, Path(d) / "q.jsonl")


def test_grounded_claim_verifies():
    """A claim that is a verbatim substring of its span (which exists in source) verifies."""
    quote = "the circuit still worked (only 5% drop in logit difference)"
    verified, residual = _run([_row("r1", "the circuit still worked", quote)])
    assert len(verified) == 1 and not residual


def test_paraphrase_not_grounded_goes_to_residual():
    """A claim not literally in its cited span is residual (paraphrase/hallucination)."""
    quote = "We discover a circuit of 26 attention heads that completes the bulk of this task."
    verified, residual = _run([_row("r2", "the circuit has exactly 42 heads", quote)])
    assert not verified and len(residual) == 1
    assert "not grounded" in residual[0].reason


def test_span_not_in_source_goes_to_residual():
    """A cited span that is not in the source is residual, never trusted."""
    quote = "This sentence does not appear anywhere in the source text zzz."
    verified, residual = _run([_row("r3", "does not appear", quote)])
    assert not verified and len(residual) == 1
    assert "not found verbatim in source" in residual[0].reason


@needs_stat_script
def test_metric_value_verified_against_source():
    """A metric_value present in source passes; the row is not dropped."""
    quote = "the circuit still worked (only 5% drop in logit difference)"
    verified, residual = _run([_row("r4", "the circuit still worked", quote, metric_value=5)])
    assert len(verified) == 1 and not residual


def test_no_row_is_ever_dropped():
    """Every input row lands in exactly one of (verified, residual)."""
    rows = [
        _row("a", "the circuit still worked", "the circuit still worked (only 5% drop in logit difference)"),
        _row("b", "invented claim", "invented span not in source qqq"),
    ]
    verified, residual = _run(rows)
    assert len(verified) + len(residual) == len(rows)
