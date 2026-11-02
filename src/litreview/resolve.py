#!/usr/bin/env python3
"""Stage 1, Resolve: turn a list of ids into a list of Source. Calls the outside arXiv resolvers.

An unresolvable id is never silently dropped. That is part of the contract. An arXiv id resolves
directly to a PDF URL. A DOI goes through the resolve_doi registry of the outside resolvers (Semantic
Scholar, Unpaywall, OpenAlex and Europe PMC). Downloading the PDF is a separate, explicit step.
"""
from __future__ import annotations

import os
import re
import sys
import urllib.request
from pathlib import Path

from .models import Source, normalize_arxiv_id

# Folder holding the outside resolve_doi.py helper. Set LITREVIEW_ARXIV_SCRIPTS to its path.
_ARXIV_SCRIPTS = os.environ.get("LITREVIEW_ARXIV_SCRIPTS")

# Valid arXiv id shapes. New style is YYMM.NNNNN (four digits, a dot, then four or five digits). Old style is archive/NNNNNNN.
_ARXIV_RE = re.compile(r"^(\d{4}\.\d{4,5}|[a-z-]+(\.[A-Z]{2})?/\d{7})$")


def _resolve_doi(doi: str) -> str | None:
    """Call the outside resolve_doi.py's resolve_doi(doi) -> pdf_url | None."""
    if not _ARXIV_SCRIPTS:
        raise RuntimeError("resolve_doi.py not found. Set LITREVIEW_ARXIV_SCRIPTS to its folder.")
    sys.path.insert(0, str(_ARXIV_SCRIPTS))
    try:
        from resolve_doi import resolve_doi  # type: ignore
        return resolve_doi(doi)
    finally:
        if str(_ARXIV_SCRIPTS) in sys.path:
            sys.path.remove(str(_ARXIV_SCRIPTS))


def resolve_sources(ids: list[str]) -> list[Source]:
    """Resolve raw arXiv ids / DOIs into Source records.

    Args:
        ids: list of ids. arXiv form ("2211.00593", "arXiv:2211.00593v5") or DOI form
            ("10.1234/xyz", "doi:10.1234/xyz").

    Returns:
        one Source per id, with canonical namespaced doc_id, arxiv_id/doi split out, a
        version-stripped join key, doc_version anchor, and a resolved pdf_url when found.

    Raises:
        ValueError: on an id that resolves to nothing (never silently dropped) — the
            message names the id so a caller can fix or drop it deliberately.

    Invariants:
        every returned Source has a namespaced doc_id and at least one of arxiv_id/doi.
    """
    sources: list[Source] = []
    for raw in ids:
        s = raw.strip()
        low = s.lower()
        if low.startswith("doi:") or low.startswith("10."):
            doi = s[4:] if low.startswith("doi:") else s
            pdf = _resolve_doi(doi)
            if pdf is None:
                raise ValueError(f"Unresolvable DOI (no OA PDF found): {doi!r}")
            # A DOI may resolve to an arXiv PDF; capture the arxiv id when present.
            arxiv_id = None
            if "arxiv.org/pdf/" in pdf:
                arxiv_id, _ = normalize_arxiv_id(pdf.rsplit("/", 1)[-1])
            sources.append(Source(
                doc_id=f"doi:{doi}" if arxiv_id is None else f"arXiv:{arxiv_id}",
                doi=doi, arxiv_id=arxiv_id, pdf_url=pdf,
            ))
        else:
            canonical, version = normalize_arxiv_id(s)
            if not _ARXIV_RE.match(canonical):
                raise ValueError(
                    f"Unresolvable id (not arXiv/DOI shaped): {raw!r}. Expected an arXiv id "
                    f"like 2211.00593 or a DOI like 10.1234/xyz."
                )
            sources.append(Source(
                doc_id=f"arXiv:{canonical}",
                arxiv_id=canonical,
                doc_version=version,
                pdf_url=f"https://arxiv.org/pdf/{version or canonical}",
            ))
    return sources


MAX_PDF_BYTES = 100 * 1024 * 1024  # size cap for one download


def download_pdf(source: Source, dest_dir: str | Path) -> Path:
    """Download source.pdf_url into dest_dir as <doc_id-slug>.pdf; set source.path.

    Raises:
        ValueError: if source has no pdf_url.
        urllib.error.URLError: on network failure (not swallowed — resolve is a hard dep).
    """
    if not source.pdf_url:
        raise ValueError(f"Source {source.doc_id} has no pdf_url to download")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    slug = source.doc_id.replace(":", "_").replace("/", "_")
    dest = dest_dir / f"{slug}.pdf"
    req = urllib.request.Request(source.pdf_url, headers={"User-Agent": "lit-review-pipeline/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise ValueError(f"PDF from {source.pdf_url} is larger than {MAX_PDF_BYTES} bytes")
    dest.write_bytes(data)
    source.path = str(dest)
    return dest
