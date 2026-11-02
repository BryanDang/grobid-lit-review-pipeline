#!/usr/bin/env python3
"""Cross-paper grade inheritance (option b): the A-tier reproduction upgrade.

Rubric rule: the A-tier upgrade trigger is independent reproduction (config). One paper with its own causal result and artifacts is B. A method shown
causally by two independent papers with released artifacts is reproduced: A. Runs over the assembled
corpus, never over raw sources.

  - Each row keeps its own source grade. A survey row stays D. An IOI row stays B.
  - A method-level `effective_grade` is the strongest evidence for the method across the
    corpus (A when reproduced). It is attached to every row for that method.
  - `backed_by` records the primary rows that supply that support.

Deterministic, no model: a join plus a max over grades.
"""
from __future__ import annotations

# Canonical method keys. Collapse surface method strings to the technique they name, so the
# same method joins across papers. To extend as the lexicon grows. An unknown method maps to
# a normalized form of its own string and joins with nothing.
_CANONICAL = {
    "induction heads": "induction_heads",
    "induction heads / ioi circuit": "induction_heads",
    "activation patching": "activation_patching",
    "activation patching & ablation": "activation_patching",
    "causal tracing": "activation_patching",         # ROME's causal tracing IS activation patching
    "path patching": "path_patching",
    "path patching (circuit discovery)": "circuit_discovery",
    "manual circuit tracing (ioi)": "circuit_discovery",
    "ablation": "ablation",
    "ablation (ioi heads)": "ablation",
    "mean-ablation knockout": "ablation",
    "adversarial examples": "adversarial",
    "superposition": "superposition",
    "sparse autoencoders / dictionary learning": "sae",
    "sparse dictionary learning": "sae",
    "causal tracing vs integrated gradients": "activation_patching",
    "rome": "rome",
    "logit lens": "logit_lens",
    "tuned lens": "logit_lens",
}

_RANK = {"A": 4, "B": 3, "C": 2, "D": 1, None: 0}
_ARTIFACT_STRENGTH = {"code+weights": 2, "code": 1, "none": 0}


def canonical_method(method: str) -> str:
    """Map a surface method string to its canonical technique key.

    Args:
        method: the row's `method` field.

    Returns:
        a canonical key; unknown methods normalize to lowercased/underscored self (so they
        never spuriously join with another technique).
    """
    key = method.strip().lower()
    return _CANONICAL.get(key, key.replace(" ", "_").replace("/", "_"))


def _is_primary_support(row: dict) -> bool:
    """A row counts as primary support iff it is causal AND released artifacts (code/weights).

    Survey rows (evidence_grade D from source_is_survey) never count as primary support —
    a survey citing a result is not an independent reproduction of it.
    """
    return bool(row.get("causal")) and _ARTIFACT_STRENGTH.get(row.get("artifacts", "none"), 0) > 0 \
        and row.get("evidence_grade") != "D"


def link_corpus(rows: list[dict]) -> list[dict]:
    """Attach effective_grade and backed_by to every row via cross-paper reproduction.

    Args:
        rows: all ClaimRow dicts from the assembled corpus (master.jsonl).

    Returns:
        the same rows (new list) with `effective_grade` and `backed_by` filled. Rows are
        not otherwise mutated; each keeps its own `evidence_grade`.

    Method-level grade logic:
        - At least 2 distinct primary papers give causal support with artifacts, and at
          least one has code+weights: reproduced, effective A.
        - Exactly 1 primary paper supports: inherit that paper's best grade (B or C).
        - Only causal-no-artifacts or observational rows: C.
        - Only survey rows: D.

    Invariants:
        effective_grade is never weaker than a row's own evidence_grade (upgrade-only).
        backed_by lists the supporting primary row keys, excluding the row itself.
    """
    # index rows by canonical method
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(canonical_method(r.get("method", "")), []).append(r)

    out: list[dict] = []
    for _, group in groups.items():
        supports = [r for r in group if _is_primary_support(r)]
        support_docs = {r["doc_id"] for r in supports}
        has_code_weights = any(r.get("artifacts") == "code+weights" for r in supports)
        support_keys = [f"{r['doc_id']}:{r['row_id']}" for r in supports]

        if len(support_docs) >= 2 and has_code_weights:
            method_grade = "A"                      # independent reproduction
        elif len(support_docs) == 1:
            method_grade = max((r.get("evidence_grade") for r in supports),
                               key=lambda g: _RANK.get(g, 0))
        elif support_docs:                          # >=1 support but no code+weights across >=2
            method_grade = max((r.get("evidence_grade") for r in supports),
                               key=lambda g: _RANK.get(g, 0))
        else:
            # no primary support: effective = best own grade in the group (usually D)
            method_grade = max((r.get("evidence_grade") for r in group),
                               key=lambda g: _RANK.get(g, 0))

        for r in group:
            own = r.get("evidence_grade")
            # upgrade-only: never present a row as weaker than its own source grade
            eff = method_grade if _RANK.get(method_grade, 0) >= _RANK.get(own, 0) else own
            self_key = f"{r['doc_id']}:{r['row_id']}"
            r = dict(r)
            r["effective_grade"] = eff
            r["backed_by"] = [k for k in support_keys if k != self_key]
            out.append(r)
    return out
