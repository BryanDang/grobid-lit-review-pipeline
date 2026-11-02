#!/usr/bin/env python3
"""Cross-paper grade inheritance tests (option b): the upgrade from reproduction to A.

Locks in the A-tier rule of the config. A method shown causally with released artifacts by
two or more independent papers is reproduced: effective A. A single primary is inherited
as B. A survey row keeps its own D grade and carries an effective_grade and a backed_by
pointer.
"""
from litreview.link import canonical_method, link_corpus


def _row(doc_id, row_id, method, grade, causal=False, artifacts="none"):
    return {"doc_id": doc_id, "row_id": row_id, "method": method, "evidence_grade": grade,
            "causal": causal, "artifacts": artifacts}


def _by_key(rows):
    return {f"{r['doc_id']}:{r['row_id']}": r for r in rows}


def test_canonical_method_joins_synonyms():
    assert canonical_method("causal tracing") == canonical_method("activation patching")
    assert canonical_method("induction heads / IOI circuit") == canonical_method("induction heads")
    assert canonical_method("tuned lens") == canonical_method("logit lens")
    # unknown methods normalize to self, do not spuriously join
    assert canonical_method("brand new method") == "brand_new_method"


def test_two_independent_primaries_reproduce_to_A():
    """activation_patching demonstrated by IOI (code) and ROME (code+weights) gives A."""
    rows = [
        _row("arXiv:IOI", "r1", "activation patching", "B", causal=True, artifacts="code"),
        _row("arXiv:ROME", "r2", "causal tracing", "B", causal=True, artifacts="code+weights"),
        _row("arXiv:survey", "r3", "activation patching", "D"),  # survey mention
    ]
    out = _by_key(link_corpus(rows))
    assert out["arXiv:IOI:r1"]["effective_grade"] == "A"
    assert out["arXiv:ROME:r2"]["effective_grade"] == "A"
    # the survey row inherits the method's effective A but keeps its own D source grade
    assert out["arXiv:survey:r3"]["effective_grade"] == "A"
    assert out["arXiv:survey:r3"]["evidence_grade"] == "D"
    assert "arXiv:IOI:r1" in out["arXiv:survey:r3"]["backed_by"]
    assert "arXiv:ROME:r2" in out["arXiv:survey:r3"]["backed_by"]


def test_single_primary_inherits_its_grade():
    """One primary (B) for a method: the survey row inherits B, not A."""
    rows = [
        _row("arXiv:ROME", "r1", "causal tracing", "B", causal=True, artifacts="code+weights"),
        _row("arXiv:survey", "r2", "activation patching", "D"),
    ]
    out = _by_key(link_corpus(rows))
    assert out["arXiv:survey:r2"]["effective_grade"] == "B"
    assert out["arXiv:ROME:r1"]["backed_by"] == []  # only itself supports; excluded


def test_two_primaries_but_no_code_weights_not_A():
    """Reproduction requires >=1 code+weights; two code-only primaries stay B."""
    rows = [
        _row("arXiv:P1", "r1", "activation patching", "B", causal=True, artifacts="code"),
        _row("arXiv:P2", "r2", "activation patching", "B", causal=True, artifacts="code"),
    ]
    out = _by_key(link_corpus(rows))
    assert out["arXiv:P1:r1"]["effective_grade"] == "B"


def test_survey_alone_stays_D():
    rows = [_row("arXiv:survey", "r1", "logit lens", "D")]
    out = _by_key(link_corpus(rows))
    assert out["arXiv:survey:r1"]["effective_grade"] == "D"
    assert out["arXiv:survey:r1"]["backed_by"] == []


def test_effective_never_weaker_than_own_grade():
    """A high-grade primary is never downgraded by an unrelated method group."""
    rows = [
        _row("arXiv:ROME", "r1", "causal tracing", "B", causal=True, artifacts="code+weights"),
        _row("arXiv:survey", "r2", "logit lens", "D"),
    ]
    out = _by_key(link_corpus(rows))
    assert out["arXiv:ROME:r1"]["effective_grade"] == "B"  # single primary, stays B
