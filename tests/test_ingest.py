#!/usr/bin/env python3
"""Ingest tests: section tree, spans (doc_id is mandatory), carry-forward and anomalies."""
from pathlib import Path

from litreview.ingest import ingest
from litreview.models import Source

FIX = Path(__file__).parent / "fixtures"


def test_ingest_builds_spans_all_carrying_doc_id():
    src = Source(doc_id="arXiv:test04", arxiv_id="test04")
    doc = ingest(src, tei_path=FIX / "fix04_empty_section_tag.tei.xml")
    assert doc.spans, "expected at least one span"
    assert all(sp.doc_id == "arXiv:test04" for sp in doc.spans)
    assert all(sp.char_offsets[0] <= sp.char_offsets[1] for sp in doc.spans)


def test_ingest_surfaces_anomalies_not_silent():
    src = Source(doc_id="arXiv:test04", arxiv_id="test04")
    doc = ingest(src, tei_path=FIX / "fix04_empty_section_tag.tei.xml")
    assert any(a.code == "FIX-04" for a in doc.anomalies)


def test_ingest_carry_forward_no_empty_section_numbers():
    """Dropped-head text is carried forward; no section is emitted with an empty number."""
    src = Source(doc_id="arXiv:test04", arxiv_id="test04")
    doc = ingest(src, tei_path=FIX / "fix04_empty_section_tag.tei.xml")
    assert all(s.number for s in doc.sections)


def test_ingest_missing_pdf_and_tei_raises():
    src = Source(doc_id="arXiv:x", arxiv_id="x")  # no path, no tei
    import pytest
    with pytest.raises(FileNotFoundError):
        ingest(src)
