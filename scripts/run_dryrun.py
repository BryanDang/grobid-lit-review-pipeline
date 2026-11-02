#!/usr/bin/env python3
"""DRY-RUN driver (the DRY-RUN gate) on 3 papers.

Runs the full pipeline on the cached survey (a type-D source) and on two primaries ingested
through live GROBID (IOI and ROME). Output: verified rows, unhealable residual, grade
distribution, fixtures and anomalies caught. Gate: its output is approved before any
full-corpus compute.

The semantic extraction step (extract.SemanticExtractor) goes through ManualExtractor, with
fields authored per selected candidate span. verify.py confirms that every claim is grounded
in its cited span and that the span exists in the source. Trust sits in the deterministic
guard, not in the extractor. One ROME row is authored with a deliberate paraphrase to show
the residual path.
"""
from __future__ import annotations

from pathlib import Path

from litreview.corpus import Corpus
from litreview.extract import ManualExtractor, find_candidates
from litreview.ingest import ingest
from litreview.models import Source
from litreview.pipeline import process_source

HERE = Path(__file__).resolve().parent.parent  # project root (scripts/ is one level down)
CORPUS = Corpus(HERE / "corpus")

# Each entry holds: doc_id, arxiv_id, tei_path, is_survey, title, and the authored rows keyed
# by candidate index. Each authored row maps an index to a must_contain keyword and fields.
# must_contain is asserted against the candidate text. If the candidate order shifts, the
# build fails loudly. It never mislabels a row.
PAPERS = [
    dict(
        doc_id="arXiv:2211.00593", arxiv_id="2211.00593", is_survey=False,
        title="Interpretability in the Wild: a Circuit for IOI in GPT-2 small",
        tei="data/IOI_2211.00593.grobid.tei.xml",
        authored={
            3:  ("26 attention heads", dict(method="path patching (circuit discovery)",
                 model="GPT-2 small", metric="fraction of head-position pairs",
                 metric_value=1.1, metric_unit="%", causal=True, artifacts="code")),
            39: ("5% drop", dict(method="mean-ablation knockout", model="GPT-2 small",
                 metric="logit difference drop", metric_value=5, metric_unit="%",
                 causal=True, artifacts="code")),
            49: ("0.4%", dict(method="adversarial examples", model="GPT-2 small",
                 metric="S-over-IO prediction rate", metric_value=0.4, metric_unit="%",
                 causal=True, artifacts="code")),
            27: ("induce a large drop in logit difference", dict(
                 method="path patching", model="GPT-2 small",
                 causal=True, artifacts="code")),
        },
    ),
    dict(
        doc_id="arXiv:2202.05262", arxiv_id="2202.05262", is_survey=False,
        title="Locating and Editing Factual Associations in GPT (ROME)",
        tei="data/ROME_2202.05262.grobid.tei.xml",
        authored={
            5:  ("more informative than", dict(method="causal tracing", model="GPT-2-XL",
                 causal=True, artifacts="code+weights")),
            24: ("does not yield the same insights", dict(
                 method="causal tracing vs integrated gradients", model="GPT-2-XL",
                 causal=True, artifacts="code+weights")),
            16: ("have not investigated", dict(method="ROME", model="GPT-2-XL",
                 causal=False, artifacts="code+weights")),
            # Deliberate residual: this claim is a paraphrase that is not grounded in the cited span.
            8:  ("used Causal Tracing to identify", dict(
                 method="causal tracing", model="GPT-2-XL", causal=True,
                 artifacts="code+weights",
                 claim="Causal tracing pinpoints the exact neuron storing every fact")),
        },
    ),
    dict(
        doc_id="arXiv:2407.02646", arxiv_id="2407.02646", is_survey=True,
        title="A Primer on the Inner Workings of Transformer-based Language Models",
        tei="data/survey.grobid.tei.xml",
        authored={
            "IND": ("induction heads", dict(method="induction heads / IOI circuit",
                 model="GPT-2 Small", causal=False, artifacts="none")),
        },
    ),
]


def build_mapping(doc, authored: dict) -> dict[str, dict]:
    """Turn {candidate_index: (keyword, fields)} into ManualExtractor's {span_text: fields}.

    Asserts each selected candidate contains its keyword (loud failure on order drift).
    A string index "IND" means: pick the first candidate containing the keyword instead
    of a fixed position (robust for the survey). `claim` defaults to the full span text
    (trivially grounded) unless the authored fields override it (residual demo).
    """
    cands = find_candidates(doc)
    mapping: dict[str, dict] = {}
    for idx, (keyword, fields) in authored.items():
        if idx == "IND":
            cand = next((c for c in cands if keyword.lower() in c.verbatim_text.lower()), None)
            assert cand, f"no candidate containing {keyword!r} in {doc.source.doc_id}"
        else:
            cand = cands[idx]
            assert keyword.lower() in cand.verbatim_text.lower(), (
                f"candidate[{idx}] in {doc.source.doc_id} does not contain {keyword!r}; "
                f"got: {cand.verbatim_text[:80]!r}")
        f = dict(fields)
        f.setdefault("claim", cand.verbatim_text)   # default: claim = the span (grounded)
        mapping[cand.verbatim_text] = f
    return mapping


def main() -> None:
    reports = []
    for p in PAPERS:
        src = Source(doc_id=p["doc_id"], arxiv_id=p["arxiv_id"], title=p["title"])
        doc = ingest(src, tei_path=p["tei"])
        extractor = ManualExtractor(build_mapping(doc, p["authored"]))
        rep = process_source(src, extractor, CORPUS, tei_path=p["tei"],
                             source_is_survey=p["is_survey"])
        reports.append(rep)

    print("\n=== DRY-RUN PER-SOURCE REPORT ===")
    for r in reports:
        print(f"{r['doc_id']:<20} sections={r['sections']:<3} anomalies={r['anomalies']:<3} "
              f"candidates(authored)={r['candidates']:<3} verified={r['verified']:<2} "
              f"residual={r['residual']:<2} grades={r['grade_dist']}")

    # Reduce over the CLEAN corpus (never raw sources)
    from litreview.reduce import load_evidence_units, synthesize_by_method
    units = load_evidence_units(CORPUS)
    synth = synthesize_by_method(units)
    print("\n=== REDUCE (grade-weighted, over master.jsonl) ===")
    for method, agg in synth.items():
        print(f"  {method:<38} weight={agg['weight']:.2f} best={agg['best_grade']} "
              f"rows={agg['n_rows']}")
    print(f"\nmaster.jsonl rows: {len(CORPUS.read_rows())}")
    print(f"exception queue files: {[p.name for p in CORPUS.exceptions.glob('*.jsonl')]}")


if __name__ == "__main__":
    main()
