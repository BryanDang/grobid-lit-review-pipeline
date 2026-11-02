#!/usr/bin/env python3
"""Corpus writer round trip, plus the pre-commit integrity checker as a permanent guard test.

Locks in the filesystem guard shown during the dry-run. A fabricated span is a claim quote
that is not in the stored source. check_integrity.py rejects it with exit 1.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from litreview.corpus import Corpus
from litreview.grade import assign_grade
from litreview.models import Artifacts, ClaimRow, ParsedDoc, Section, Source, Span

REPO = Path(__file__).resolve().parent.parent
CHECKER = REPO / "corpus" / "check_integrity.py"
SCHEMA = REPO / "corpus" / "schema.json"


def _doc():
    src = Source(doc_id="arXiv:x", arxiv_id="x", title="t")
    sec = Section(number="1", title="Intro",
                  text="Activation patching transfers activations from a clean run.", depth=0, page=1)
    return ParsedDoc(source=src, sections=[sec])


def test_write_row_round_trip():
    """write_row appends to master, writes the fragment, and read_rows returns it."""
    c = Corpus(tempfile.mkdtemp())
    c.write_source_text(_doc())
    sp = Span(doc_id="arXiv:x", verbatim_text="Activation patching transfers activations",
              char_offsets=(0, 10), section_tag="1 Intro")
    row = assign_grade(ClaimRow(row_id="r0", doc_id="arXiv:x", method="activation patching",
                                claim="Activation patching", claim_source_span=sp,
                                causal=True, artifacts=Artifacts.CODE))
    frag = c.write_row(row)
    assert frag.exists() and frag.read_text() == sp.verbatim_text
    rows = c.read_rows()
    assert len(rows) == 1 and rows[0]["method"] == "activation patching"
    assert rows[0]["evidence_grade"] == "B"


def test_manifest_records_grobid_tag():
    c = Corpus(tempfile.mkdtemp())
    c.write_source_text(_doc())
    manifest = json.loads(c.manifest_path.read_text())
    assert manifest["arXiv:x"]["grobid_tag"] == "lfoppiano/grobid:0.8.0"


def _temp_corpus_with_checker():
    d = Path(tempfile.mkdtemp())
    shutil.copy(CHECKER, d / "check_integrity.py")
    shutil.copy(SCHEMA, d / "schema.json")
    (d / "fragments").mkdir()
    (d / "sources").mkdir()
    return d


def test_checker_passes_on_grounded_row():
    d = _temp_corpus_with_checker()
    (d / "sources" / "arXiv_x.txt").write_text("Activation patching transfers activations from a clean run.")
    (d / "fragments" / "arXiv_x__r0.txt").write_text("Activation patching transfers activations")
    (d / "master.jsonl").write_text(json.dumps({
        "row_id": "r0", "doc_id": "arXiv:x", "method": "activation patching",
        "claim": "Activation patching transfers activations", "evidence_grade": "D",
        "claim_source_span": {"verbatim_text": "Activation patching transfers activations"},
    }) + "\n")
    r = subprocess.run(["python3", str(d / "check_integrity.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_checker_rejects_fabricated_span():
    """A claim quote absent from the stored source is rejected (exit 1) — the guard bites."""
    d = _temp_corpus_with_checker()
    (d / "sources" / "arXiv_x.txt").write_text("Activation patching transfers activations from a clean run.")
    (d / "fragments" / "arXiv_x__r9.txt").write_text("this fabricated quote is not in the source zzz")
    (d / "master.jsonl").write_text(json.dumps({
        "row_id": "r9", "doc_id": "arXiv:x", "method": "fake",
        "claim": "this fabricated quote is not in the source zzz", "evidence_grade": "A",
        "claim_source_span": {"verbatim_text": "this fabricated quote is not in the source zzz"},
    }) + "\n")
    r = subprocess.run(["python3", str(d / "check_integrity.py")], capture_output=True, text=True)
    assert r.returncode == 1
    assert "NOT found verbatim" in r.stdout
