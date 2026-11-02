#!/usr/bin/env python3
"""Spine builder: the survey-only corpus (depth before breadth, 2026-07-10).

The spine is the seed survey. Finished and hardened first. Expansion to the primary papers
and cross-paper grade inheritance comes after.

The spine is a method map: curated method-claim pairs for the major interpretability
techniques. Every row is grade D (a survey is context under the rubric). Every claim span
is checked against its source. The primaries (IOI and ROME) belong to the expand phase.
They live in git under the `dry-run-green` tag.

Spans are the strongest and clearest, picked by hand. Full-coverage extraction waits for
the AnthropicExtractor key. `verify.py` checks every span regardless.
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
# The survey TEI is vendored into data/. GROBID produced it from
# ../Research Extractor/Survey on Mech Interp.pdf. The spine build needs no sibling directory.
SURVEY_TEI = str(HERE / "data" / "survey.grobid.tei.xml")
DOC_ID = "arXiv:2407.02646"

# Curated method-claim spans. Each maps a candidate index to an assert-keyword and the
# fields. Claim defaults to the full span text (grounded). causal marks an intervention.
# Grade D comes from source_is_survey. artifacts is none (the survey releases no primary
# artifacts). The keyword assertions fail loudly if the candidates drift.
CURATED = {
    4:  ("implement induction heads that copy tokens",
         dict(method="induction heads / IOI circuit", model="GPT-2 Small", causal=False)),
    29: ("superposition hypothesis",
         dict(method="superposition", causal=False)),
    43: ("two-token copying pattern",
         dict(method="induction heads", causal=False)),
    60: ("Two canonical interventions",
         dict(method="activation patching & ablation", causal=True)),
    63: ("also called causal tracing or causal mediation",
         dict(method="activation patching", causal=True)),
    68: ("selectively disables a neuron",
         dict(method="ablation", causal=True)),
    69: ("removes capacity to test necessity",
         dict(method="ablation", causal=True)),
    71: ("disrupts pronoun resolution",
         dict(method="ablation (IOI heads)", model="GPT-2", causal=True)),
    74: ("one-hop patch swaps the output",
         dict(method="path patching", causal=True)),
    76: ("unembedding matrix to intermediate hidden states",
         dict(method="logit lens", causal=False)),
    78: ("tuned lens improve interpretability",
         dict(method="tuned lens", causal=False)),
    82: ("decompose activations into interpretable",
         dict(method="sparse autoencoders / dictionary learning", causal=False)),
    57: ("find all names in the prompt",
         dict(method="manual circuit tracing (IOI)", model="GPT-2", causal=False)),
    30: ("rotated basis typically obtained via sparse dictionary learning",
         dict(method="sparse dictionary learning", causal=False)),
}


def reset_corpus() -> None:
    """Clear corpus data files for a fresh spine build (git history preserved)."""
    if CORPUS.master.exists():
        CORPUS.master.unlink()
    for d in (CORPUS.fragments, CORPUS.sources, CORPUS.exceptions):
        for f in d.glob("*"):
            f.unlink()
    if CORPUS.manifest_path.exists():
        CORPUS.manifest_path.unlink()


def build_mapping(doc, curated: dict) -> dict[str, dict]:
    """Turn {index: (keyword, fields)} into ManualExtractor's {span_text: fields}."""
    cands = find_candidates(doc)
    mapping: dict[str, dict] = {}
    for idx, (keyword, fields) in curated.items():
        cand = cands[idx]
        assert keyword.lower() in cand.verbatim_text.lower(), (
            f"candidate[{idx}] does not contain {keyword!r}; got {cand.verbatim_text[:80]!r}")
        f = dict(fields)
        f.setdefault("claim", cand.verbatim_text)
        f.setdefault("artifacts", "none")
        mapping[cand.verbatim_text] = f
    return mapping


def main() -> None:
    reset_corpus()
    src = Source(doc_id=DOC_ID, arxiv_id="2407.02646",
                 title="A Primer on the Inner Workings of Transformer-based Language Models")
    doc = ingest(src, tei_path=SURVEY_TEI)
    extractor = ManualExtractor(build_mapping(doc, CURATED))
    rep = process_source(src, extractor, CORPUS, tei_path=SURVEY_TEI, source_is_survey=True)

    print("=== SPINE BUILD (survey only) ===")
    print(f"{rep['doc_id']}: sections={rep['sections']} spans={rep['spans']} "
          f"anomalies={rep['anomalies']} curated_rows={rep['candidates']} "
          f"verified={rep['verified']} residual={rep['residual']} grades={rep['grade_dist']}")

    from litreview.reduce import load_evidence_units, synthesize_by_method
    synth = synthesize_by_method(load_evidence_units(CORPUS))
    print("\n=== SPINE METHOD MAP (reduce over master.jsonl) ===")
    for method, agg in synth.items():
        print(f"  {method:<40} grade={agg['best_grade']} rows={agg['n_rows']}")
    print(f"\nmaster.jsonl rows: {len(CORPUS.read_rows())}")


if __name__ == "__main__":
    main()
