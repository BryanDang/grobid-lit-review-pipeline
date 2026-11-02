#!/usr/bin/env python3
"""Corpus writer. It defines "the corpus dir" for the outside corpus guards.

Layout (from the build brief):
    corpus/
      master.jsonl        one ClaimRow per line. Append-only. Keyed by doc_id and row_id.
      fragments/          <doc_id>__<row_id>.txt holds the verbatim quote that stat_exists checks.
      sources/            <doc_id>.txt is the plain text that stat_exists greps. The cached TEI is here too.
      exceptions/         anomalies and the unhealable residual, so nothing passes silently.
      MANIFEST.json       doc_id maps to title, arxiv_id, doi, doc_version and grobid_tag.

A stored fragments/ file makes the span check deterministic and checkable offline.
The exceptions/ folder shows the never-pass-silently rule as files.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from .grobid_client import GROBID_TAG
from .models import Anomaly, ClaimRow, ParsedDoc


def _slug(doc_id: str) -> str:
    """Filesystem-safe form of a namespaced doc_id (arXiv:2211.00593 becomes arXiv_2211.00593)."""
    return doc_id.replace(":", "_").replace("/", "_")


class Corpus:
    """A corpus directory with the fixed layout. Writers here are the only path to it.

    Args:
        root: path to the corpus directory (created if absent, with subdirs).

    Invariants:
        every ClaimRow written also writes its fragment file; every anomaly written
        lands in exceptions/; MANIFEST records the pinned GROBID tag per doc.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.fragments = self.root / "fragments"
        self.sources = self.root / "sources"
        self.exceptions = self.root / "exceptions"
        self.master = self.root / "master.jsonl"
        self.manifest_path = self.root / "MANIFEST.json"
        for d in (self.root, self.fragments, self.sources, self.exceptions):
            d.mkdir(parents=True, exist_ok=True)

    def write_source_text(self, doc: ParsedDoc) -> Path:
        """Write the plaintext source (concatenated section text) that stat_exists greps.

        Returns the path to corpus/sources/<doc_id>.txt. Also records the doc in MANIFEST.
        """
        text = "\n\n".join(f"## {s.number} {s.title}\n{s.text}" for s in doc.sections)
        path = self.sources / f"{_slug(doc.source.doc_id)}.txt"
        path.write_text(text, encoding="utf-8")
        self._record_manifest(doc)
        return path

    def source_path(self, doc_id: str) -> Path:
        """Path to the stored plaintext source for a doc_id (stat_exists --source)."""
        return self.sources / f"{_slug(doc_id)}.txt"

    def write_row(self, row: ClaimRow) -> Path:
        """Append a ClaimRow to master.jsonl and write its fragment file.

        The fragment (verbatim claim quote) is the stat_exists target artifact. Returns
        the fragment path. Uses append mode — the assembler is the only writer (guard 2
        / safe_write enforces this at commit time).
        """
        frag = self.fragments / f"{_slug(row.doc_id)}__{row.row_id}.txt"
        frag.write_text(row.claim_source_span.verbatim_text, encoding="utf-8")
        with self.master.open("a", encoding="utf-8") as f:
            f.write(json.dumps(_row_to_dict(row), ensure_ascii=False) + "\n")
        return frag

    def write_exception(self, kind: str, payload: dict) -> Path:
        """Append an exception record (anomaly or unhealable residual) as a JSONL line.

        kind: e.g. "anomaly", "residual". payload: the record. Returns the queue path.
        """
        queue = self.exceptions / f"{kind}.jsonl"
        with queue.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return queue

    def write_anomalies(self, doc_id: str, anomalies: list[Anomaly]) -> int:
        """Route all structural anomalies to exceptions/anomaly.jsonl. Returns the count."""
        for a in anomalies:
            self.write_exception("anomaly", {"doc_id": doc_id, **dataclasses.asdict(a)})
        return len(anomalies)

    def read_rows(self) -> list[dict]:
        """Read all ClaimRow dicts from master.jsonl (reduce entry point)."""
        if not self.master.exists():
            return []
        return [json.loads(line) for line in self.master.read_text().splitlines() if line.strip()]

    def rewrite_master(self, rows: list[dict]) -> None:
        """Overwrite master.jsonl with `rows` (used by the cross-paper link stage to
        persist enriched rows). Fragments/sources are unchanged, so the integrity checker
        still holds. The assembler is the only caller (safe_write discipline at commit)."""
        with self.master.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def _record_manifest(self, doc: ParsedDoc) -> None:
        manifest = {}
        if self.manifest_path.exists():
            manifest = json.loads(self.manifest_path.read_text())
        s = doc.source
        manifest[s.doc_id] = {
            "title": s.title,
            "arxiv_id": s.arxiv_id,
            "doi": s.doi,
            "doc_version": s.doc_version,
            "grobid_tag": GROBID_TAG,
            "tei_path": doc.tei_path,
        }
        self.manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


def _row_to_dict(row: ClaimRow) -> dict:
    """Flatten a ClaimRow to a JSON-serializable dict (enums become values, spans become nested dicts)."""
    def span_d(sp):
        if sp is None:
            return None
        return {
            "doc_id": sp.doc_id,
            "verbatim_text": sp.verbatim_text,
            "char_offsets": list(sp.char_offsets),
            "page_coords": sp.page_coords,
            "section_tag": sp.section_tag,
        }
    return {
        "row_id": row.row_id,
        "doc_id": row.doc_id,
        "method": row.method,
        "claim": row.claim,
        "claim_source_span": span_d(row.claim_source_span),
        "model": row.model,
        "metric": row.metric,
        "metric_value": row.metric_value,
        "metric_unit": row.metric_unit,
        "baseline_described": row.baseline_described,
        "causal": row.causal,
        "artifacts": row.artifacts.value,
        "evidence_grade": row.evidence_grade.value if row.evidence_grade else None,
        "grade_source_span": span_d(row.grade_source_span),
        "backed_by": row.backed_by,
        "effective_grade": row.effective_grade.value if row.effective_grade else None,
    }
