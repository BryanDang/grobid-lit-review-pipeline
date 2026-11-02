#!/usr/bin/env python3
"""Reduce tests: grade weighting and method grouping over the clean corpus."""
import tempfile
from pathlib import Path

from litreview.corpus import Corpus
from litreview.grade import assign_grade
from litreview.models import Artifacts, ClaimRow, Span
from litreview.reduce import (GRADE_WEIGHT, load_evidence_units, synthesize_by_method)


def _corpus_with(rows_spec):
    d = tempfile.mkdtemp()
    c = Corpus(d)
    # a source file so write flows work (not needed by reduce, but keeps corpus coherent)
    for i, (method, causal, artifacts) in enumerate(rows_spec):
        sp = Span(doc_id="arXiv:x", verbatim_text=f"quote {i}", char_offsets=(0, 3))
        row = ClaimRow(row_id=f"r{i}", doc_id="arXiv:x", method=method, claim=f"quote {i}",
                       claim_source_span=sp, causal=causal, artifacts=artifacts)
        assign_grade(row)
        c.write_row(row)
    return c


def test_grade_weights_ordering():
    assert GRADE_WEIGHT["A"] > GRADE_WEIGHT["B"] > GRADE_WEIGHT["C"] > GRADE_WEIGHT["D"]


def test_load_units_only_graded_rows():
    c = _corpus_with([("m1", True, Artifacts.CODE)])
    units = load_evidence_units(c)
    assert len(units) == 1 and units[0].grade == "B"
    assert units[0].source_pointer[0] == "arXiv:x"


def test_synthesize_groups_and_weights_by_method():
    c = _corpus_with([
        ("patching", True, Artifacts.CODE),      # B
        ("patching", False, Artifacts.NONE),     # C
        ("ablation", True, Artifacts.NONE),      # C
    ])
    synth = synthesize_by_method(load_evidence_units(c))
    assert synth["patching"]["n_rows"] == 2
    assert synth["patching"]["best_grade"] == "B"
    # patching (B and C: 0.7 + 0.4) outweighs ablation (C: 0.4), so it sorts first
    assert list(synth.keys())[0] == "patching"
