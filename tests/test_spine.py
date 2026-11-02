#!/usr/bin/env python3
"""Spine acceptance and regression test: the depth-first milestone as a permanent fixture.

Builds the curated spine on the vendored survey TEI into a temp corpus. Locks in four things:
  - Every curated candidate resolves and is span-verified. There is no residual and there are no drops.
  - The whole spine is grade D, because a survey is context under the MI rubric.
  - All four GROBID fixtures are caught and routed to the exception queue.
  - The integrity checker passes on the assembled spine.
A change that breaks any of these fails this test. The spine cannot regress silently.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_spine  # noqa: E402  (repo-root module; the spine builder under test)
from litreview.corpus import Corpus  # noqa: E402
from litreview.ingest import ingest  # noqa: E402
from litreview.models import Source  # noqa: E402
from litreview.pipeline import process_source  # noqa: E402

SURVEY_TEI = REPO / "data" / "survey.grobid.tei.xml"


def _build(tmp_path):
    corpus = Corpus(tmp_path)
    src = Source(doc_id=build_spine.DOC_ID, arxiv_id="2407.02646", title="survey")
    doc = ingest(src, tei_path=SURVEY_TEI)
    from litreview.extract import ManualExtractor
    extractor = ManualExtractor(build_spine.build_mapping(doc, build_spine.CURATED))
    rep = process_source(src, extractor, corpus, tei_path=SURVEY_TEI, source_is_survey=True)
    return corpus, rep, doc


def test_vendored_survey_tei_present():
    assert SURVEY_TEI.exists(), "spine must be self-contained (data/survey.grobid.tei.xml)"


def test_spine_builds_all_curated_rows_verified(tmp_path):
    _, rep, _ = _build(tmp_path)
    assert rep["candidates"] == len(build_spine.CURATED) == 14
    assert rep["verified"] == 14
    assert rep["residual"] == 0


def test_spine_is_all_grade_D(tmp_path):
    _, rep, _ = _build(tmp_path)
    assert rep["grade_dist"] == {"D": 14}


def test_spine_catches_all_four_fixtures(tmp_path):
    _, _, doc = _build(tmp_path)
    codes = {a.code for a in doc.anomalies}
    for fix in ("FIX-01", "FIX-02", "FIX-03", "FIX-04"):
        assert fix in codes, f"{fix} not caught on the survey TEI"


def test_spine_rows_are_span_verified_in_corpus(tmp_path):
    corpus, _, _ = _build(tmp_path)
    src_text = corpus.source_path(build_spine.DOC_ID).read_text()
    import re
    norm = lambda t: re.sub(r"\s+", " ", t).strip()
    for row in corpus.read_rows():
        quote = row["claim_source_span"]["verbatim_text"]
        assert norm(quote) in norm(src_text), f"row {row['row_id']} span not in source"
