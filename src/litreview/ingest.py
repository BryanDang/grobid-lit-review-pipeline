#!/usr/bin/env python3
"""Stage 2, Ingest: turn a Source into a ParsedDoc (section tree, span store and anomalies).

Highest-risk box in the pipeline. Tables and
OCR'd digits corrupt silently. This stage runs the structural validator.
Every known GROBID failure is flagged and routed to the exception queue.

Same ideas as the Research Extractor components (unit2 section tree, unit3 span store),
expressed against the typed models with the mandatory doc_id.
"""
from __future__ import annotations

import re
from pathlib import Path

from .grobid_client import pdf_to_tei
from .models import ParsedDoc, Source, Span
from .tei_validator import validate_structure

# Sentence splitter. Breaks after a period, exclamation mark or question mark that is
# followed by whitespace and then a capital letter, a quote or a digit.
# Over-splitting (abbreviations) is harmless for span attribution. A wrong merge would hide a claim.
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'0-9])")


def _sentences(text: str) -> list[tuple[str, int, int]]:
    """Split text into (sentence, start_offset, end_offset) triples within `text`."""
    out: list[tuple[str, int, int]] = []
    pos = 0
    for piece in _SENT.split(text):
        piece = piece  # keep as-is; find its offset from pos
        idx = text.find(piece, pos)
        if idx < 0:
            idx = pos
        out.append((piece.strip(), idx, idx + len(piece)))
        pos = idx + len(piece)
    return [(s, a, b) for (s, a, b) in out if s]


def ingest(source: Source, tei_path: str | Path | None = None) -> ParsedDoc:
    """Parse a Source into a ParsedDoc, running the structural validator.

    Args:
        source: the Source to ingest. If tei_path is None, source.path must be a PDF
            and GROBID is invoked (liveness-probed first).
        tei_path: optional path to an already-produced GROBID TEI (dry-run seed reuse).
            When given, GROBID is not invoked.

    Returns:
        ParsedDoc with sections (carry-forward applied), spans (each carrying doc_id,
        char_offsets within its section text, and the section's page as coarse
        page_coords), and anomalies (FIX-01..04 and monitor finds, routed to the exception queue).

    Raises:
        RuntimeError: if GROBID must run but is not alive.
        FileNotFoundError: if neither tei_path nor a valid source.path PDF is available.
        ValueError: if the TEI has no body.

    Invariants:
        every span.doc_id == source.doc_id; anomalies are never dropped; a section whose
        text came from a dropped head is not orphaned (carry-forward in the validator).
    """
    if tei_path is None:
        if not source.path:
            raise FileNotFoundError(
                f"Source {source.doc_id}: no tei_path and no source.path PDF to ingest"
            )
        tei_path = pdf_to_tei(source.path)
    tei_path = Path(tei_path)

    result = validate_structure(tei_path, doc_id=source.doc_id)

    spans: list[Span] = []
    for sec in result.sections:
        page_coords = [str(sec.page)] if sec.page is not None else []
        for sent, start, end in _sentences(sec.text):
            spans.append(Span(
                doc_id=source.doc_id,
                verbatim_text=sent,
                char_offsets=(start, end),
                page_coords=page_coords,
                section_tag=f"{sec.number} {sec.title}".strip(),
            ))

    return ParsedDoc(
        source=source,
        sections=result.sections,
        spans=spans,
        anomalies=result.anomalies,
        tei_path=str(tei_path),
    )
