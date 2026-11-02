#!/usr/bin/env python3
"""Stage 6, Reduce: synthesize over the clean corpus, weighted by grade.

Map-reduce, grade-weighted. Reads the clean structured corpus
(master.jsonl), never raw sources. Weights by evidence grade, not flat row counts.

Specifies the outside reduce adapter for a structured corpus, which is a stub (probed
2026-07-09). Adapter contract: each corpus row is an
evidence unit, its stored span is the source pointer, its evidence grade feeds confidence.
The outside reasoning loop is unchanged. It filters rows instead of issuing web
searches. This file holds the row reader and the grade weights. Hypothesis and confidence
reasoning stay in the outside reasoning loop.
"""
from __future__ import annotations

from dataclasses import dataclass

from .corpus import Corpus

# Grade weights. A strongest. D is context only. One reproduced A outweighs many survey-only Ds.
GRADE_WEIGHT = {"A": 1.0, "B": 0.7, "C": 0.4, "D": 0.1}


@dataclass
class EvidenceUnit:
    """One corpus row presented to the outside reduce adapter as an evidence unit.

    Fields:
        method: the MI technique.
        claim: what is asserted.
        grade: the grade used for weighting — `effective_grade` (cross-paper) when the
            link stage has run, else the row's own `evidence_grade`. A when reproduced.
        own_grade: the row's own source grade (survey stays D even if the method is A).
        weight: GRADE_WEIGHT[grade].
        source_pointer: (doc_id, row_id, verbatim_quote) — the traceable source pointer.
        backed_by: primary row keys that supply the cross-paper support (may be empty).
    """

    method: str
    claim: str
    grade: str
    own_grade: str
    weight: float
    source_pointer: tuple[str, str, str]
    backed_by: list[str]


def load_evidence_units(corpus: Corpus) -> list[EvidenceUnit]:
    """Read master.jsonl rows into evidence units.

    Reads ONLY the clean structured corpus (never raw sources). A row missing a grade is
    skipped. Weighting uses `effective_grade` when present (cross-paper reasoning has run),
    otherwise the row's own `evidence_grade`.

    Returns:
        one EvidenceUnit per graded row in master.jsonl.
    """
    units: list[EvidenceUnit] = []
    for r in corpus.read_rows():
        own = r.get("evidence_grade")
        if not own:
            continue
        grade = r.get("effective_grade") or own
        span = r.get("claim_source_span") or {}
        units.append(EvidenceUnit(
            method=r.get("method", ""),
            claim=r.get("claim", ""),
            grade=grade,
            own_grade=own,
            weight=GRADE_WEIGHT.get(grade, 0.0),
            source_pointer=(r.get("doc_id", ""), r.get("row_id", ""), span.get("verbatim_text", "")),
            backed_by=r.get("backed_by", []),
        ))
    return units


def synthesize_by_method(units: list[EvidenceUnit]) -> dict[str, dict]:
    """Grade-weighted reduction grouped by method (a deterministic reduce over the corpus).

    For each method: total grade-weighted support, best (highest) grade seen, row count,
    and the supporting evidence units. This is the structured input the outside reasoning loop
    works over; it does not itself write prose synthesis.

    Returns:
        {method: {"weight": float, "best_grade": str, "n_rows": int, "units": [...]}}
        sorted by descending weighted support.
    """
    by_method: dict[str, dict] = {}
    for u in units:
        m = by_method.setdefault(u.method, {"weight": 0.0, "best_grade": "D", "n_rows": 0, "units": []})
        m["weight"] += u.weight
        m["n_rows"] += 1
        m["units"].append(u)
        if _grade_rank(u.grade) > _grade_rank(m["best_grade"]):
            m["best_grade"] = u.grade
    return dict(sorted(by_method.items(), key=lambda kv: kv[1]["weight"], reverse=True))


def _grade_rank(grade: str) -> int:
    """A>B>C>D as 4>3>2>1 for best-grade comparison."""
    return {"A": 4, "B": 3, "C": 2, "D": 1}.get(grade, 0)
