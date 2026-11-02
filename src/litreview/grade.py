#!/usr/bin/env python3
"""Stage 5, Grade: assign tiers (A, B, C or D) to each row.

Rubric: config/mi-domain-config.md, in the style of GRADE.
Start tier: the claim's design (causal or observational) and its artifacts (code and
weights, code only, or none). Up for independent reproduction. Down for missing artifacts
or over-claiming.

Popularity firewall: stars, citations and reach never set or raise a grade.
The function takes only reproducibility signals.
"""
from __future__ import annotations

from .models import Artifacts, ClaimRow, EvidenceGrade, Span


def assign_grade(row: ClaimRow, *, reproduced: bool = False,
                 source_is_survey: bool = False,
                 grade_span: Span | None = None) -> ClaimRow:
    """Set row.evidence_grade from reproducibility signals. Returns the row.

    Args:
        row: the ClaimRow to grade (mutated in place and returned).
        reproduced: True iff the claim is independently reproduced (upgrade trigger).
            A single paper reporting its own result is NOT reproduced.
        source_is_survey: True iff the ONLY source for this row is a survey/blog/position
            synthesizing others' work (the seed survey). Caps the grade at D per the
            tier definition ("context only, not primary evidence") unless the primary
            artifacts were themselves extracted — which requires resolving the primary.
        grade_span: the Span justifying the grade (the evidence quote). Recorded on the
            row so reduce can trace WHY a grade was assigned. Defaults to the claim span.

    Returns:
        the row with evidence_grade and grade_source_span set.

    Grade logic (MI):
        D  survey-only sourcing (context), OR no method/claim substance.
        C  observational/correlational, OR causal without released artifacts.
        B  causal, single-paper, code (or code+weights) released, not yet reproduced.
        A  causal, code+weights released, AND independently reproduced.

    Invariants:
        a graded row always has a grade_source_span; a popularity signal is never an input.
    """
    row.grade_source_span = grade_span or row.claim_source_span

    if source_is_survey:
        row.evidence_grade = EvidenceGrade.D
        return row

    if not row.causal:
        row.evidence_grade = EvidenceGrade.C            # observational/correlational
        return row

    # causal from here
    if row.artifacts == Artifacts.NONE:
        row.evidence_grade = EvidenceGrade.C            # causal but no released artifacts
    elif row.artifacts == Artifacts.CODE_WEIGHTS and reproduced:
        row.evidence_grade = EvidenceGrade.A            # reproduced + full artifacts
    else:
        row.evidence_grade = EvidenceGrade.B            # single-paper causal w/ code
    return row
