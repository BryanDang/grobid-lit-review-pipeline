#!/usr/bin/env python3
"""Expand (option b) integration and regression test: cross-paper reproduction, end to end.

Builds the expanded corpus (spine, IOI and ROME) into a temp corpus from vendored TEIs.
Locks in three things:
  - activation_patching reaches effective A, because two independent primaries reproduce it.
  - The survey's activation-patching spine rows inherit A and keep their own D source grade.
  - Single-primary methods inherit B.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_expand  # noqa: E402
import build_spine  # noqa: E402
from litreview.corpus import Corpus  # noqa: E402
from litreview.extract import ManualExtractor  # noqa: E402
from litreview.ingest import ingest  # noqa: E402
from litreview.link import canonical_method, link_corpus  # noqa: E402
import pytest  # noqa: E402
from litreview.verify import stat_script_available  # noqa: E402

needs_stat_script = pytest.mark.skipif(
    not stat_script_available(), reason="set LITREVIEW_STAT_SCRIPTS to run")
from litreview.models import Source  # noqa: E402
from litreview.pipeline import process_source  # noqa: E402


def _build(tmp_path):
    corpus = Corpus(tmp_path)
    ssrc = Source(doc_id=build_spine.DOC_ID, arxiv_id="2407.02646", title="survey")
    sdoc = ingest(ssrc, tei_path=build_spine.SURVEY_TEI)
    process_source(ssrc, ManualExtractor(build_spine.build_mapping(sdoc, build_spine.CURATED)),
                   corpus, tei_path=build_spine.SURVEY_TEI, source_is_survey=True)
    for p in build_expand.PRIMARIES:
        src = Source(doc_id=p["doc_id"], arxiv_id=p["arxiv_id"], title=p["title"])
        doc = ingest(src, tei_path=p["tei"])
        process_source(src, ManualExtractor(build_expand._build_primary_mapping(doc, p["authored"])),
                       corpus, tei_path=p["tei"], source_is_survey=False)
    linked = link_corpus(corpus.read_rows())
    corpus.rewrite_master(linked)
    return corpus, linked


def test_vendored_primary_teis_present():
    for p in build_expand.PRIMARIES:
        assert Path(p["tei"]).exists(), f"vendored TEI missing: {p['tei']}"


def test_activation_patching_reproduced_to_A(tmp_path):
    _, linked = _build(tmp_path)
    ap = [r for r in linked if canonical_method(r["method"]) == "activation_patching"]
    assert ap, "expected activation_patching rows"
    assert all(r["effective_grade"] == "A" for r in ap), "activation_patching must reach A"
    # reproduced across >=2 distinct primary docs
    docs = {b.rsplit(":", 1)[0] for r in ap for b in r["backed_by"]}
    assert len([d for d in docs if d != build_spine.DOC_ID]) >= 2


def test_survey_row_keeps_own_D_but_effective_upgrades(tmp_path):
    _, linked = _build(tmp_path)
    survey_ap = [r for r in linked
                 if r["doc_id"] == build_spine.DOC_ID
                 and canonical_method(r["method"]) == "activation_patching"]
    assert survey_ap
    for r in survey_ap:
        assert r["evidence_grade"] == "D"        # own source grade unchanged
        assert r["effective_grade"] == "A"       # method reproduced, so effective A


@needs_stat_script
def test_single_primary_method_inherits_B(tmp_path):
    _, linked = _build(tmp_path)
    # ablation is only in IOI (code) among primaries, so effective B, not A
    abl = [r for r in linked
           if r["doc_id"] == build_spine.DOC_ID and canonical_method(r["method"]) == "ablation"]
    assert abl and all(r["effective_grade"] == "B" for r in abl)


@needs_stat_script
def test_total_rows(tmp_path):
    _, linked = _build(tmp_path)
    assert len(linked) == 14 + 3 + 2  # spine (14), IOI (3), ROME (2)
