#!/usr/bin/env python3
"""GROBID client wrapper: a liveness probe (the first ingestion step) and PDF to TEI.

Finding (2026-07-09): the GROBID server is a local Docker container, and no tag was
recorded anywhere. The liveness probe is the first step. Ingestion fails loudly with the
bring-up command and does not produce empty TEI.

Pinned tag: lfoppiano/grobid:0.8.0. Recorded in the corpus MANIFEST.grobid_tag.
Rule: re-run the fixtures on any deliberate upgrade (acceptance criterion).
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

GROBID_SERVER = "http://localhost:8070"
GROBID_TAG = "lfoppiano/grobid:0.8.0"
BRING_UP = (
    "docker run -d --name grobid -p 8070:8070 lfoppiano/grobid:0.8.0  "
    "# then wait ~40s for /api/isalive"
)


def is_alive(server: str = GROBID_SERVER, timeout: float = 5.0) -> bool:
    """Return True iff the GROBID server answers /api/isalive with 'true'.

    Args:
        server: base URL of the GROBID server.
        timeout: seconds to wait for the probe.

    Returns:
        True if the server is up and ready; False on any connection error or non-'true'
        body. Never raises — a probe failure is a boolean, not an exception.
    """
    try:
        with urllib.request.urlopen(f"{server}/api/isalive", timeout=timeout) as r:
            return r.read().decode().strip().lower() == "true"
    except Exception:
        return False


def require_alive(server: str = GROBID_SERVER) -> None:
    """Raise a clear, actionable error if GROBID is not reachable. First ingestion step.

    Raises:
        RuntimeError: if the server does not answer isalive, with the bring-up command.
    """
    if not is_alive(server):
        raise RuntimeError(
            f"GROBID not reachable at {server}. Ingestion cannot proceed.\n"
            f"Bring it up (pinned tag {GROBID_TAG}):\n    {BRING_UP}"
        )


def pdf_to_tei(pdf_path: str | Path, server: str = GROBID_SERVER) -> Path:
    """Process a PDF to GROBID TEI (with coordinates) and return the .tei.xml path.

    Runs `require_alive` first. Uses processFulltextDocument with tei_coordinates so
    spans can carry page_coords for PDF trace-back.

    Args:
        pdf_path: path to a born-digital PDF.
        server: GROBID server URL.

    Returns:
        Path to the produced `<name>.grobid.tei.xml` (next to the PDF).

    Raises:
        RuntimeError: if GROBID is not alive.
        FileNotFoundError: if pdf_path does not exist, or TEI was not produced.
    """
    require_alive(server)
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    from grobid_client.grobid_client import GrobidClient

    client = GrobidClient(config_path=None, grobid_server=server)
    client.process(
        "processFulltextDocument",
        input_path=str(pdf_path.parent),
        output=str(pdf_path.parent),
        consolidate_citations=False,
        force=True,
        tei_coordinates=True,
    )
    tei = pdf_path.with_suffix("").with_suffix(".grobid.tei.xml")
    if not tei.exists():
        # GROBID names it <stem>.grobid.tei.xml
        tei = pdf_path.parent / f"{pdf_path.stem}.grobid.tei.xml"
    if not tei.exists():
        raise FileNotFoundError(f"GROBID produced no TEI for {pdf_path}")
    return tei
