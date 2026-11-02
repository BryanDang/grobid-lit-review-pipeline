#!/usr/bin/env python3
"""Expanded corpus builder (option b): spine, primaries and cross-paper grade inheritance.

Expand phase, after the spine was hardened. Reads the survey (the spine, grade D) and two
hand-picked primaries (IOI and ROME) through their GROBID TEI files. Each row is graded by
its own paper. Then the cross-paper linker runs. A method shown causally by at least two
independent primaries with released artifacts counts as reproduced: effective grade A. The
survey's D rows get an `effective_grade` and a `backed_by` pointer to the supporting primaries.

Example: IOI (code) and ROME's causal tracing (code and weights) both show
`activation_patching`. Two independent primaries, so effective grade A. The survey's
activation-patching spine rows inherit it.

Network note (2026-07-10): arXiv was unreachable mid-session, so this uses the IOI/ROME TEIs
already fetched. To do when the network returns: add Olsson (2209.11895) and Superposition
(2209.10652) to PRIMARIES. Resolving and GROBID are already wired.
"""
from __future__ import annotations

from pathlib import Path

import build_spine  # reuse the curated spine set and build_mapping
from litreview.corpus import Corpus
from litreview.extract import ManualExtractor
from litreview.ingest import ingest
from litreview.link import canonical_method, link_corpus
from litreview.models import Source
from litreview.pipeline import process_source
from litreview.reduce import GRADE_WEIGHT, load_evidence_units

HERE = Path(__file__).resolve().parent.parent  # project root (scripts/ is one level down)
CORPUS = Corpus(HERE / "corpus")

# Curated primary rows (candidate index to a tuple of assert-keyword and fields). Chosen so
# activation_patching appears in both IOI and ROME: reproduction, grade A.
PRIMARIES = [
    dict(doc_id="arXiv:2211.00593", arxiv_id="2211.00593",
         title="Interpretability in the Wild: a Circuit for IOI in GPT-2 small",
         tei=str(HERE / "data" / "IOI_2211.00593.grobid.tei.xml"),
         authored={
             2:  ("activation patching to understand", dict(method="activation patching",
                  model="GPT-2 small", causal=True, artifacts="code")),
             3:  ("26 attention heads", dict(method="path patching (circuit discovery)",
                  model="GPT-2 small", metric="fraction of head-position pairs",
                  metric_value=1.1, metric_unit="%", causal=True, artifacts="code")),
             39: ("5% drop", dict(method="mean-ablation knockout", model="GPT-2 small",
                  metric="logit difference drop", metric_value=5, metric_unit="%",
                  causal=True, artifacts="code")),
         }),
    dict(doc_id="arXiv:2202.05262", arxiv_id="2202.05262",
         title="Locating and Editing Factual Associations in GPT (ROME)",
         tei=str(HERE / "data" / "ROME_2202.05262.grobid.tei.xml"),
         authored={
             5:  ("more informative than", dict(method="causal tracing", model="GPT-2-XL",
                  causal=True, artifacts="code+weights")),
             24: ("does not yield the same insights", dict(
                  method="causal tracing vs integrated gradients", model="GPT-2-XL",
                  causal=True, artifacts="code+weights")),
         }),
]


def _build_primary_mapping(doc, authored):
    from litreview.extract import find_candidates
    cands = find_candidates(doc)
    mapping = {}
    for idx, (kw, fields) in authored.items():
        cand = cands[idx]
        assert kw.lower() in cand.verbatim_text.lower(), (
            f"candidate[{idx}] in {doc.source.doc_id} lacks {kw!r}: {cand.verbatim_text[:70]!r}")
        f = dict(fields)
        f.setdefault("claim", cand.verbatim_text)
        mapping[cand.verbatim_text] = f
    return mapping


def main() -> None:
    build_spine.reset_corpus()

    # 1) spine (survey, grade D)
    ssrc = Source(doc_id=build_spine.DOC_ID, arxiv_id="2407.02646", title="survey")
    sdoc = ingest(ssrc, tei_path=build_spine.SURVEY_TEI)
    process_source(ssrc, ManualExtractor(build_spine.build_mapping(sdoc, build_spine.CURATED)),
                   CORPUS, tei_path=build_spine.SURVEY_TEI, source_is_survey=True)

    # 2) primaries (own grades B/C by artifacts)
    for p in PRIMARIES:
        src = Source(doc_id=p["doc_id"], arxiv_id=p["arxiv_id"], title=p["title"])
        doc = ingest(src, tei_path=p["tei"])
        process_source(src, ManualExtractor(_build_primary_mapping(doc, p["authored"])),
                       CORPUS, tei_path=p["tei"], source_is_survey=False)

    # 3) cross-paper link stage: rewrite master with effective_grade and backed_by
    rows = CORPUS.read_rows()
    linked = link_corpus(rows)
    CORPUS.rewrite_master(linked)

    # 4) report
    print("=== EXPANDED CORPUS (spine + primaries + links) ===")
    print(f"total rows: {len(linked)}")
    upgraded = [r for r in linked if r.get("effective_grade") != r.get("evidence_grade")]
    print(f"rows upgraded by cross-paper reproduction: {len(upgraded)}")
    # a backed_by key is "<doc_id>:<row_id>"; doc_id itself contains ':', so recover it
    # with rsplit(':', 1) (row_id never contains a colon).
    def doc_of(key: str) -> str:
        return key.rsplit(":", 1)[0]

    print("\n=== REPRODUCTION EVIDENCE (methods reaching effective A) ===")
    seen = set()
    for r in linked:
        m = canonical_method(r.get("method", ""))
        if r.get("effective_grade") == "A" and m not in seen:
            seen.add(m)
            backers = sorted({doc_of(b) for b in r.get("backed_by", [])} | {r["doc_id"]})
            print(f"  {m:<22} effective=A  reproduced across: {backers}")

    print("\n=== SURVEY SPINE ROWS: own grade -> effective (with backing) ===")
    for r in linked:
        if r["doc_id"] == build_spine.DOC_ID and r.get("backed_by"):
            backers = sorted({doc_of(b) for b in r["backed_by"]})
            print(f"  {r['method']:<38} D -> {r['effective_grade']}  backed_by={backers}")

    units = load_evidence_units(CORPUS)
    print(f"\nmaster.jsonl rows: {len(CORPUS.read_rows())} | "
          f"grade-weighted total (effective): "
          f"{sum(GRADE_WEIGHT.get(u.grade,0) for u in units):.2f}")


if __name__ == "__main__":
    main()
