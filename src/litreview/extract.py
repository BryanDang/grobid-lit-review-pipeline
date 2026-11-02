#!/usr/bin/env python3
"""Stage 3, Extract: turn a ParsedDoc into a list of ClaimRow. Deterministic wherever possible.

Deterministic work stays apart from probabilistic work.
Finding candidates is deterministic: spans that name an MI method and carry a number or a
causal verb. Turning a candidate into ClaimRow fields needs judgment (method normalization,
causal flag, model name, claim paraphrase). Only that step goes to a model, through the
SemanticExtractor protocol.

The extractor is not trusted. AnthropicExtractor is the production extractor. The
2026-07-09 dry-run used ManualExtractor. Either way, the verify stage confirms that every
claim_source_span exists verbatim in the stored source.
"""
from __future__ import annotations

import re
from typing import Protocol

from .models import Artifacts, ClaimRow, ParsedDoc, Span

# MI method lexicon: the deterministic candidate trigger. To extend as the corpus grows.
METHOD_LEXICON = [
    "activation patching", "path patching", "causal tracing", "ablation",
    "sparse autoencoder", "sae", "probing", "linear probe", "logit lens",
    "direct logit attribution", "attention head", "induction head", "circuit",
    "ioi", "rome", "feature", "steering vector", "superposition", "dictionary learning",
]
_NUMBER = re.compile(r"\d")
# Causal-claim verbs. Mark a span that asserts an intervention result, not just a mention.
_CAUSAL_HINT = re.compile(
    r"\b(patch|ablat|intervene|causal|restore|corrupt|steer|knock ?out|remove)\w*\b",
    re.IGNORECASE,
)


class SemanticExtractor(Protocol):
    """The one model-touching seam. Turns a candidate span into ClaimRow field values.

    Implementations: AnthropicExtractor (production, needs ANTHROPIC_API_KEY);
    ManualExtractor (replays pre-computed fields, used in the dry-run). The rest of the
    pipeline stays model-agnostic and testable.
    """

    def fields(self, candidate: Span, doc: ParsedDoc) -> dict | None:
        """Return a dict of ClaimRow fields for this candidate, or None to skip it.

        Expected keys: method, claim, model, metric, metric_value, metric_unit,
        baseline_described, causal, artifacts. `claim` must be a verbatim substring of
        the candidate span's text, or the deterministic verify check fails.
        """
        ...


def find_candidates(doc: ParsedDoc) -> list[Span]:
    """Deterministically locate spans likely to carry a method-claim pair.

    A candidate span (a) names a method from METHOD_LEXICON AND (b) either contains a
    digit (a metric) or a causal-claim verb. Fully deterministic; no model.

    Args:
        doc: the ParsedDoc to scan.

    Returns:
        the subset of doc.spans that qualify, in document order. Never invents spans.
    """
    out: list[Span] = []
    for sp in doc.spans:
        low = sp.verbatim_text.lower()
        if not any(m in low for m in METHOD_LEXICON):
            continue
        if _NUMBER.search(sp.verbatim_text) or _CAUSAL_HINT.search(sp.verbatim_text):
            out.append(sp)
    return out


def extract(doc: ParsedDoc, extractor: SemanticExtractor) -> list[ClaimRow]:
    """Produce ClaimRows from a ParsedDoc via deterministic candidates + a semantic pass.

    Args:
        doc: the ingested document.
        extractor: the SemanticExtractor that fills the semantic fields per candidate.

    Returns:
        one ClaimRow per candidate the extractor accepted (returned non-None fields),
        each with a claim_source_span pointing at the candidate span. row_id is stable
        (<doc_id>__rNN) so (doc_id,row_id) uniquely keys the row.

    Invariants:
        every ClaimRow.claim_source_span.doc_id == doc.source.doc_id; the `claim` text is
        carried from the extractor and verified downstream (never trusted here).
    """
    rows: list[ClaimRow] = []
    candidates = find_candidates(doc)
    for i, cand in enumerate(candidates):
        f = extractor.fields(cand, doc)
        if f is None:
            continue
        rows.append(ClaimRow(
            row_id=f"r{i:03d}",
            doc_id=doc.source.doc_id,
            method=f.get("method", ""),
            claim=f.get("claim", ""),
            claim_source_span=cand,
            model=f.get("model", ""),
            metric=f.get("metric", ""),
            metric_value=f.get("metric_value"),
            metric_unit=f.get("metric_unit"),
            baseline_described=bool(f.get("baseline_described", False)),
            causal=bool(f.get("causal", False)),
            artifacts=Artifacts(f.get("artifacts", "none")),
        ))
    return rows


class ManualExtractor:
    """Replays pre-computed semantic fields keyed by candidate span text.

    Used for the dry-run (no ANTHROPIC_API_KEY). The mapping is {verbatim_span_text:
    fields_dict}. A candidate with no entry is skipped (returns None), so the mapping
    curates which candidates become rows. verify still checks every span.

    Args:
        mapping: {candidate.verbatim_text: fields_dict}.
    """

    def __init__(self, mapping: dict[str, dict]):
        self._mapping = mapping

    def fields(self, candidate: Span, doc: ParsedDoc) -> dict | None:
        return self._mapping.get(candidate.verbatim_text)


class AnthropicExtractor:
    """Production SemanticExtractor: one Anthropic API call per candidate span.

    Requires ANTHROPIC_API_KEY in the environment. Probed 2026-07-09: not present in the
    build environment, hence ManualExtractor for the dry-run. Single-family healing:
    extraction and repair stay in one model family.

    Args:
        model: Anthropic API model id (default "claude-opus-4-8", unverified).
    """

    def __init__(self, model: str = "claude-opus-4-8"):
        self.model = model

    def fields(self, candidate: Span, doc: ParsedDoc) -> dict | None:  # pragma: no cover
        import json
        import os

        import anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("AnthropicExtractor needs ANTHROPIC_API_KEY (use ManualExtractor)")
        client = anthropic.Anthropic()
        prompt = (
            "Extract ONE method-claim pair from this span of a mechanistic-"
            "interpretability paper. Return JSON with keys: method, claim (a VERBATIM "
            "substring of the span), model, metric, metric_value (number|null), "
            "metric_unit, baseline_described (bool), causal (bool), artifacts "
            "(code+weights|code|none). If the span carries no real method-claim, return "
            'null.\n\nSPAN:\n' + candidate.verbatim_text
        )
        msg = client.messages.create(
            model=self.model, max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        if text.lower() == "null":
            return None
        return json.loads(text)
