#!/usr/bin/env python3
"""Contract and invariant tests for the shared data models."""
import pytest

from litreview.models import (Artifacts, ClaimRow, EvidenceGrade, Source, Span,
                              normalize_arxiv_id)


@pytest.mark.parametrize("raw, canonical, version", [
    ("2211.00593", "2211.00593", None),
    ("2211.00593v5", "2211.00593", "2211.00593v5"),
    ("arXiv:2211.00593v2", "2211.00593", "2211.00593v2"),
    ("ARXIV:2202.05262", "2202.05262", None),
])
def test_normalize_arxiv_id(raw, canonical, version):
    """Version is stripped for the join key; the full versioned id is preserved."""
    assert normalize_arxiv_id(raw) == (canonical, version)


def test_source_requires_doc_id_and_an_identifier():
    """A Source needs a non-empty doc_id and at least one of arxiv_id/doi."""
    with pytest.raises(ValueError):
        Source(doc_id="")
    with pytest.raises(ValueError):
        Source(doc_id="arXiv:x")  # no arxiv_id/doi
    Source(doc_id="arXiv:x", arxiv_id="x")  # ok


def test_span_doc_id_mandatory_and_offsets_ordered():
    """Span enforces the unit3 doc_id enhancement and offset ordering."""
    with pytest.raises(ValueError):
        Span(doc_id="", verbatim_text="t", char_offsets=(0, 1))
    with pytest.raises(ValueError):
        Span(doc_id="d", verbatim_text="t", char_offsets=(5, 2))
    Span(doc_id="d", verbatim_text="t", char_offsets=(0, 1))  # ok


def test_claimrow_span_doc_id_must_match_row():
    """A ClaimRow's claim_source_span must belong to the same doc as the row."""
    good = Span(doc_id="arXiv:x", verbatim_text="q", char_offsets=(0, 1))
    ClaimRow(row_id="r0", doc_id="arXiv:x", method="m", claim="q", claim_source_span=good)
    bad = Span(doc_id="arXiv:y", verbatim_text="q", char_offsets=(0, 1))
    with pytest.raises(ValueError):
        ClaimRow(row_id="r1", doc_id="arXiv:x", method="m", claim="q", claim_source_span=bad)


def test_enums_have_expected_values():
    assert Artifacts.CODE_WEIGHTS.value == "code+weights"
    assert {g.value for g in EvidenceGrade} == {"A", "B", "C", "D"}
