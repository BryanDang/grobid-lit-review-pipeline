#!/usr/bin/env python3
"""Extract tests: deterministic candidate finding, plus ManualExtractor accept and skip."""
from litreview.extract import (ManualExtractor, extract, find_candidates)
from litreview.models import ParsedDoc, Source, Span


def _doc(sentences):
    src = Source(doc_id="arXiv:x", arxiv_id="x")
    spans = [Span(doc_id="arXiv:x", verbatim_text=s, char_offsets=(0, len(s))) for s in sentences]
    return ParsedDoc(source=src, spans=spans)


def test_find_candidates_requires_method_and_number_or_causal():
    doc = _doc([
        "This sentence mentions nothing relevant.",             # no method: skip
        "Sparse autoencoders are discussed generally here.",    # method but no number or causal verb: skip
        "Activation patching restores the corrupted run.",      # method and causal verb: KEEP
        "The circuit spans 26 attention heads.",                # method and number: KEEP
    ])
    cands = find_candidates(doc)
    texts = [c.verbatim_text for c in cands]
    assert "Activation patching restores the corrupted run." in texts
    assert "The circuit spans 26 attention heads." in texts
    assert "This sentence mentions nothing relevant." not in texts
    assert "Sparse autoencoders are discussed generally here." not in texts


def test_find_candidates_is_deterministic():
    doc = _doc(["Activation patching restores the run.", "The circuit has 26 heads."])
    assert [c.verbatim_text for c in find_candidates(doc)] == \
           [c.verbatim_text for c in find_candidates(doc)]


def test_manual_extractor_accepts_mapped_skips_unmapped():
    doc = _doc(["Activation patching restores the corrupted run.",
                "The circuit spans 26 attention heads."])
    mapping = {"Activation patching restores the corrupted run.":
               {"method": "activation patching", "claim": "Activation patching restores",
                "causal": True}}
    rows = extract(doc, ManualExtractor(mapping))
    assert len(rows) == 1
    assert rows[0].method == "activation patching"
    assert rows[0].claim_source_span.doc_id == "arXiv:x"
