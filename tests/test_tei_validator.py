#!/usr/bin/env python3
"""Regression fixtures for the structural TEI validator.

Each of the four known GROBID failures (fixtures/known-grobid-failures.md) is a permanent
test. The validator flags it. A bug counts as fixed only when its fixture is green.
The snippets in tests/fixtures/*.tei.xml are extracted from the real survey TEI.
"""
from pathlib import Path

import pytest

from litreview.tei_validator import validate_structure

FIX = Path(__file__).parent / "fixtures"


def test_fix01_list_steps_flagged_not_counted_as_sections():
    """FIX-01: <head n="2."> / <head n="5."> list steps flagged, not real sections."""
    r = validate_structure(FIX / "fix01_list_steps.tei.xml", doc_id="arXiv:test01")
    assert r.has("FIX-01"), "list steps must be flagged FIX-01"
    # exactly the two list steps flagged
    assert sum(a.code == "FIX-01" for a in r.anomalies) == 2
    # the real sections 4.1 and 4.2 survive; the "2." / "5." steps are NOT sections
    numbers = {s.number for s in r.sections}
    assert "4.1" in numbers and "4.2" in numbers
    assert "2." not in numbers and "5." not in numbers


def test_fix02_dropped_numbers_flagged():
    """FIX-02: orphan subsection 9.2 with no declared top-level 9 is flagged."""
    r = validate_structure(FIX / "fix02_dropped_numbers.tei.xml", doc_id="arXiv:test02")
    assert r.has("FIX-02"), "dropped/gapped section numbers must be flagged FIX-02"
    detail = " ".join(a.detail for a in r.anomalies if a.code == "FIX-02")
    assert "top-level" in detail  # names the missing top-level


def test_fix03_table_routed_to_exception_queue():
    """FIX-03: a table figure is flagged and recorded as an exception-queue region."""
    r = validate_structure(FIX / "fix03_table_oversegmentation.tei.xml", doc_id="arXiv:test03")
    assert r.has("FIX-03"), "table figures must be flagged FIX-03"
    assert r.table_regions, "table must be recorded for exception-queue routing"


def test_fix04_empty_section_tag_flagged_and_carried_forward():
    """FIX-04: dropped-head div flagged; its text carried forward to last-seen section."""
    r = validate_structure(FIX / "fix04_empty_section_tag.tei.xml", doc_id="arXiv:test04")
    assert r.has("FIX-04"), "empty section_tag must be flagged FIX-04"
    # no section carries an empty tag silently
    assert all(s.number for s in r.sections), "no section emitted with empty number"
    # carry-forward: the orphaned paragraph text landed in section 7.4
    s74 = next(s for s in r.sections if s.number == "7.4")
    assert "GROBID dropped entirely" in s74.text


def test_clean_structure_has_no_false_positives():
    """A well-formed snippet raises none of the FIX anomalies (guards against over-flagging)."""
    clean = FIX / "clean_minimal.tei.xml"
    clean.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div><head n="1" coords="1,0,0,0,0">Introduction</head><p>Intro text.</p></div>'
        '<div><head n="1.1" coords="1,0,0,0,0">Background</head><p>Background text.</p></div>'
        '<div><head n="2" coords="2,0,0,0,0">Methods</head><p>Methods text.</p></div>'
        '</body></text></TEI>'
    )
    r = validate_structure(clean, doc_id="arXiv:clean")
    for code in ("FIX-01", "FIX-02", "FIX-03", "FIX-04"):
        assert not r.has(code), f"clean structure should not raise {code}"
    assert {s.number for s in r.sections} == {"1", "1.1", "2"}


def test_missing_body_raises():
    """A TEI with no <body> raises ValueError, not a silent empty result."""
    bad = FIX / "no_body.tei.xml"
    bad.write_text('<?xml version="1.0"?><TEI xmlns="http://www.tei-c.org/ns/1.0"></TEI>')
    with pytest.raises(ValueError):
        validate_structure(bad, doc_id="x")


def test_validator_as_monitor_flags_unknown_head_format():
    """Monitor: a head number that is neither a section nor a known list step is flagged
    NEW-* (so a novel GROBID failure becomes a new fixture rather than passing silently)."""
    mon = FIX / "monitor_new_head.tei.xml"
    mon.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div><head n="1" coords="1,0,0,0,0">Introduction</head><p>Intro.</p></div>'
        '<div><head n="A.7.x" coords="2,0,0,0,0">Weird numbering scheme</head><p>Body.</p></div>'
        '</body></text></TEI>'
    )
    r = validate_structure(mon, doc_id="arXiv:mon")
    assert any(a.code.startswith("NEW-") for a in r.anomalies)
