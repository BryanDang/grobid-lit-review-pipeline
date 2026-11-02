#!/usr/bin/env python3
"""Pipeline orchestrator: wires the six stages over a corpus directory.

Order: resolve, ingest, extract, verify, grade, write corpus, reduce.

Each stage lives in its own module. This file runs them in order, sends anomalies and
residual rows to the exception queue, and writes only verified rows to the master corpus.
It is the map half, one source at a time. Reduce reads the assembled clean corpus.
"""
from __future__ import annotations

from pathlib import Path

from .corpus import Corpus
from .extract import SemanticExtractor, extract
from .grade import assign_grade
from .ingest import ingest
from .models import Source
from .verify import verify


def process_source(source: Source, extractor: SemanticExtractor, corpus: Corpus,
                   *, tei_path: str | Path | None = None,
                   source_is_survey: bool = False) -> dict:
    """Run stages 2-5 for one Source and write verified rows and exceptions to the corpus.

    Args:
        source: the Source to process (already resolved).
        extractor: the SemanticExtractor for stage 3.
        corpus: the target Corpus (guards must already be initialized on its dir).
        tei_path: optional cached TEI to skip GROBID (dry-run seed reuse).
        source_is_survey: passed to grade — caps this doc's rows at D (survey context).

    Returns:
        a per-source report dict: counts of sections, spans, anomalies, candidates,
        verified rows, residual rows, and the grade distribution of verified rows.

    Invariants:
        anomalies and residual are always written to exceptions/ (never dropped); only
        span-verified rows reach master.jsonl.
    """
    doc = ingest(source, tei_path=tei_path)
    corpus.write_anomalies(source.doc_id, doc.anomalies)
    source_txt_path = corpus.write_source_text(doc)
    source_text = Path(source_txt_path).read_text(encoding="utf-8")

    rows = extract(doc, extractor)

    queue = corpus.exceptions / "stat_queue.jsonl"
    verified, residual = verify(rows, source_text, source_txt_path, queue)

    for vr in residual:
        corpus.write_exception("residual", {
            "doc_id": source.doc_id, "row_id": vr.row.row_id,
            "claim": vr.row.claim, "reason": vr.reason,
        })

    grade_dist: dict[str, int] = {}
    for row in verified:
        assign_grade(row, source_is_survey=source_is_survey)
        corpus.write_row(row)
        g = row.evidence_grade.value if row.evidence_grade else "?"
        grade_dist[g] = grade_dist.get(g, 0) + 1

    return {
        "doc_id": source.doc_id,
        "sections": len(doc.sections),
        "spans": len(doc.spans),
        "anomalies": len(doc.anomalies),
        "candidates": len(rows),
        "verified": len(verified),
        "residual": len(residual),
        "grade_dist": grade_dist,
    }
