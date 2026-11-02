#!/usr/bin/env python3
"""Shared data contracts for the Lit Review Pipeline.

Every dataclass here is a contract that the rest of the pipeline is written against.
Code review checks against these contracts. Each field holds one fact. Every claim field is
paired with a `_source_span`. Stable ids are their own joinable fields, never buried in free text.

The stages consume and produce these types in this order:
    resolve_sources returns [Source].
    ingest(Source) returns ParsedDoc, a section tree plus a span store.
    extract(ParsedDoc) returns [ClaimRow], each claim field paired with a Span.
    verify([ClaimRow]) returns (verified, residual).
    grade and reduce operate on verified ClaimRows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


def normalize_arxiv_id(raw: str) -> tuple[str, str | None]:
    """Split a raw arXiv id into (version-stripped canonical, full versioned) form.

    Purpose: the join key must aggregate all rows of one paper, while reproducibility
    must tie to the exact version reproduced (config doc_id decision, 2026-07-09).

    Args:
        raw: an arXiv id, optionally with a version suffix and/or `arXiv:` prefix.
            Examples: "2211.00593", "2211.00593v5", "arXiv:2211.00593v2".

    Returns:
        (canonical, version): canonical is the id without version and without prefix
        (e.g. "2211.00593"); version is the full versioned id (e.g. "2211.00593v5")
        or None when no version suffix was present.

    Invariants:
        canonical never contains 'v<digits>' at the end; canonical never carries the
        'arXiv:' prefix (that prefix belongs to doc_id, applied by Source).
    """
    s = raw.strip()
    if s.lower().startswith("arxiv:"):
        s = s[len("arxiv:"):]
    import re
    m = re.match(r"^(?P<core>.+?)(?P<ver>v\d+)?$", s)
    core = m.group("core")
    ver = m.group("ver")
    version = f"{core}{ver}" if ver else None
    return core, version


class Artifacts(str, Enum):
    """What reproducibility artifacts a claim's source released. Drives the grade."""

    CODE_WEIGHTS = "code+weights"
    CODE = "code"
    NONE = "none"


class EvidenceGrade(str, Enum):
    """A to D tiers, filled by the MI domain rubric (config)."""

    A = "A"  # causal, reproduced, code+weights released
    B = "B"  # causal, single-paper, code released
    C = "C"  # observational/correlational, or causal without released artifacts
    D = "D"  # survey/blog/position; context only


@dataclass
class Source:
    """A resolvable paper the pipeline will ingest.

    Contract for `resolve_sources(ids) -> list[Source]`. Carries the canonical id
    plus everything ingestion needs to fetch and trace the document.

    Fields:
        doc_id: canonical, namespaced stable id — "arXiv:<id>" (version stripped) or
            "doi:<id>". Joinable; mandatory on every downstream Span.
        title: paper title (may be filled at ingest from TEI if unknown at resolve).
        path: local path to the fetched PDF, or None until downloaded.
        tier_hint: a first-guess evidence tier from resolve-time metadata (never final;
            grade is set by the grade stage against extracted artifacts). None if unknown.
        arxiv_id: version-stripped arXiv id when the paper is on arXiv, else None.
        doi: DOI when present, else None (both stored when both exist; one is canonical).
        doc_version: full versioned arXiv id (reproducibility anchor), else None.
        pdf_url: the resolved direct PDF URL, or None if unresolved.

    Invariants:
        doc_id is non-empty and namespaced. At least one of {arxiv_id, doi} is set.
    """

    doc_id: str
    title: str | None = None
    path: str | None = None
    tier_hint: EvidenceGrade | None = None
    arxiv_id: str | None = None
    doi: str | None = None
    doc_version: str | None = None
    pdf_url: str | None = None

    def __post_init__(self) -> None:
        if not self.doc_id:
            raise ValueError("Source.doc_id must be non-empty")
        if not (self.arxiv_id or self.doi):
            raise ValueError(f"Source {self.doc_id!r} needs at least one of arxiv_id/doi")


@dataclass
class Span:
    """One retrievable, source-traceable chunk of a paper.

    Extends the Research Extractor unit3 `Span` with the mandatory `doc_id` (the unit3
    document-id enhancement): a span is not traceable across papers without it. Keeps
    BOTH page_coords (PDF trace-back) and char_offsets (deterministic stat_exists),
    per the span-granularity config decision (2026-07-09).

    Fields:
        doc_id: canonical id of the source paper. MANDATORY. Joins the span to Source.
        verbatim_text: exact extracted text, unmodified (what stat_exists greps for).
        char_offsets: (start, end) within the section's text; start <= end.
        page_coords: GROBID coord strings "page,x,y,w,h" (may be [] if TEI lacked coords).
        section_tag: e.g. "3.2 Sparse Autoencoders"; "" if the source div had a dropped
            head (FIX-04) — an empty tag is a flagged anomaly, not a silent value.

    Invariants:
        doc_id non-empty; char_offsets[0] <= char_offsets[1].
    """

    doc_id: str
    verbatim_text: str
    char_offsets: tuple[int, int]
    page_coords: list[str] = field(default_factory=list)
    section_tag: str = ""

    def __post_init__(self) -> None:
        if not self.doc_id:
            raise ValueError("Span.doc_id is mandatory (unit3 document-id enhancement)")
        if self.char_offsets[0] > self.char_offsets[1]:
            raise ValueError(f"Span char_offsets out of order: {self.char_offsets}")


@dataclass
class Section:
    """A node in the document section tree produced by ingest.

    Fields:
        number: section number as GROBID emits it ("3.2.1"); "" if dropped (FIX-02).
        title: heading text; "" if the div had no head.
        text: the concatenated body text of the section (char_offset domain for spans).
        depth: nesting depth = number.count('.') when numbered, else carried/0.
        page: 1-based first page of the section when known, else None.
    """

    number: str
    title: str
    text: str
    depth: int
    page: int | None = None


@dataclass
class Anomaly:
    """A structural problem the TEI validator flags. Never silently dropped.

    Fields:
        code: fixture/rule id, e.g. "FIX-01".."FIX-04" or "NEW-*" for monitor finds.
        detail: human-readable description of the specific instance.
        locator: where it occurred (section number, page, or head text).
    """

    code: str
    detail: str
    locator: str = ""


@dataclass
class ParsedDoc:
    """Contract for `ingest(source) -> ParsedDoc`.

    Carries the section tree, the span store and the anomalies the structural validator
    raised. Anomalies go here (exception queue), never silently through.

    Fields:
        source: the Source this was parsed from.
        sections: ordered section tree (document order).
        spans: all extracted spans (each carries doc_id, page_coords and char_offsets).
        anomalies: structural-validator findings (FIX-01..04 and monitor finds).
        tei_path: path to the GROBID TEI xml this was parsed from.

    Invariants:
        every span.doc_id == source.doc_id.
    """

    source: Source
    sections: list[Section] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)
    tei_path: str | None = None


@dataclass
class ClaimRow:
    """One method-claim pair — the unit of analysis (config [DECIDED] 2026-07-09).

    Contract for `extract(doc) -> list[ClaimRow]`. One fact per field; every claim
    field is paired with a `_source_span`; numbers split into value/unit/baseline.

    Fields:
        row_id: stable within-doc id (e.g. "<doc_id>__r03"); with doc_id, uniquely keys.
        doc_id: canonical source id. Joinable.
        method: the MI technique named (e.g. "activation patching").
        claim: what is asserted about the method.
        claim_source_span: Span backing the claim text. MANDATORY.
        model: model the result is on (e.g. "GPT-2-small"), or "" if unstated.
        metric: e.g. "logit-difference", "faithfulness", or "" if none.
        metric_value: numeric result, or None.
        metric_unit: unit; never fused with value; None if not applicable.
        baseline_described: is the comparison baseline stated in the source?
        causal: causal (intervention) vs observational.
        artifacts: code+weights / code / none (drives the grade).
        evidence_grade: A/B/C/D — this row's OWN source
            grade (set by the grade stage; a survey row stays D even after linking).
        grade_source_span: Span justifying the grade (the evidence quote). MANDATORY
            once graded; None before the grade stage runs.
        backed_by: row keys ("doc_id:row_id") of PRIMARY rows in the corpus that
            independently support this row's method (set by the cross-paper link stage).
            Empty until linking runs.
        effective_grade: the method-level grade after cross-paper reasoning — the
            strongest evidence available for this method across the corpus (A when a
            method is independently reproduced). Distinct from evidence_grade, which is
            this single source's grade. None until linking runs.

    Invariants:
        claim_source_span.doc_id == doc_id; metric_value and metric_unit are never
        fused; a graded row has a grade_source_span; effective_grade is never weaker
        than evidence_grade (linking only upgrades, never downgrades a row's own grade).
    """

    row_id: str
    doc_id: str
    method: str
    claim: str
    claim_source_span: Span
    model: str = ""
    metric: str = ""
    metric_value: float | None = None
    metric_unit: str | None = None
    baseline_described: bool = False
    causal: bool = False
    artifacts: Artifacts = Artifacts.NONE
    evidence_grade: EvidenceGrade | None = None
    grade_source_span: Span | None = None
    backed_by: list[str] = field(default_factory=list)
    effective_grade: EvidenceGrade | None = None

    def __post_init__(self) -> None:
        if self.claim_source_span.doc_id != self.doc_id:
            raise ValueError(
                f"ClaimRow {self.row_id}: claim_source_span.doc_id "
                f"{self.claim_source_span.doc_id!r} != row doc_id {self.doc_id!r}"
            )
