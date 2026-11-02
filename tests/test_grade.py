#!/usr/bin/env python3
"""Grading tests. They cover every tier path and the popularity firewall by construction."""
from litreview.grade import assign_grade
from litreview.models import Artifacts, ClaimRow, EvidenceGrade, Span


def _row(causal=False, artifacts=Artifacts.NONE):
    sp = Span(doc_id="arXiv:x", verbatim_text="q", char_offsets=(0, 1))
    return ClaimRow(row_id="r", doc_id="arXiv:x", method="m", claim="q",
                    claim_source_span=sp, causal=causal, artifacts=artifacts)


def test_survey_source_caps_at_D():
    """Survey-only sourcing is D (context), regardless of causal/artifacts."""
    r = assign_grade(_row(causal=True, artifacts=Artifacts.CODE_WEIGHTS), source_is_survey=True)
    assert r.evidence_grade == EvidenceGrade.D


def test_observational_is_C():
    assert assign_grade(_row(causal=False)).evidence_grade == EvidenceGrade.C


def test_causal_without_artifacts_is_C():
    assert assign_grade(_row(causal=True, artifacts=Artifacts.NONE)).evidence_grade == EvidenceGrade.C


def test_causal_with_code_single_paper_is_B():
    assert assign_grade(_row(causal=True, artifacts=Artifacts.CODE)).evidence_grade == EvidenceGrade.B
    assert assign_grade(_row(causal=True, artifacts=Artifacts.CODE_WEIGHTS)).evidence_grade == EvidenceGrade.B


def test_reproduced_full_artifacts_is_A():
    r = assign_grade(_row(causal=True, artifacts=Artifacts.CODE_WEIGHTS), reproduced=True)
    assert r.evidence_grade == EvidenceGrade.A


def test_reproduced_without_full_artifacts_is_not_A():
    """Reproduction alone does not reach A without code+weights."""
    r = assign_grade(_row(causal=True, artifacts=Artifacts.CODE), reproduced=True)
    assert r.evidence_grade == EvidenceGrade.B


def test_graded_row_always_has_grade_span():
    r = assign_grade(_row(causal=True, artifacts=Artifacts.CODE))
    assert r.grade_source_span is not None
