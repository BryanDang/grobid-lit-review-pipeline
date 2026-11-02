#!/usr/bin/env python3
"""Resolve tests: the arXiv id path and the never-silently-drop contract. No network calls."""
import pytest

from litreview.resolve import resolve_sources


def test_resolve_arxiv_id_builds_canonical_source():
    [s] = resolve_sources(["2211.00593"])
    assert s.doc_id == "arXiv:2211.00593"
    assert s.arxiv_id == "2211.00593"
    assert s.pdf_url == "https://arxiv.org/pdf/2211.00593"


def test_resolve_versioned_arxiv_keeps_version_anchor():
    [s] = resolve_sources(["arXiv:2202.05262v3"])
    assert s.doc_id == "arXiv:2202.05262"        # version-stripped join key
    assert s.doc_version == "2202.05262v3"        # reproducibility anchor
    assert s.pdf_url.endswith("2202.05262v3")     # pdf points at the exact version


def test_resolve_unresolvable_raises_never_silent():
    with pytest.raises(ValueError):
        resolve_sources(["not-an-id-or-doi"])
