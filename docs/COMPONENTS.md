# Reusable components: Lit Review Pipeline

## Contents
1. Summary
2. Components
3. Not reusable as is
4. Rust candidates

## Summary
All paths are inside `projects/lit-review-pipeline/`. Notes on what is reusable in other projects. Reuse column: High = works elsewhere with little change. Medium = works after small edits. Low = tied to this project or to files outside the repo. Test counts come from `python -m pytest --collect-only`. The full test result is 57 passed and 3 skipped. Cause: see `docs/TECH-SPEC.md`, section "How to run and test".

The best candidates for another project are the TEI structure checker, the span-existence check, the corpus integrity checker and the failure-fixture method.

## Components
| Component | File | Purpose | Reuse | Outside dependencies | Tests that cover it |
|---|---|---|---|---|---|
| TEI structure checker | `src/litreview/tei_validator.py` | Reads GROBID TEI (XML from a PDF parser). Flags list steps tagged as headings, dropped section numbers, split table rows, empty section tags and unknown heading formats. Carries the last section forward. | High | Python standard library only | `tests/test_tei_validator.py` (7), fixtures in `tests/fixtures/`, and `tests/test_ingest.py` (4) |
| Failure-fixture method | `fixtures/known-grobid-failures.md`, `tests/fixtures/*.tei.xml` | Each real parser failure becomes a permanent test snippet. The pattern copies to any parser. | High | None | `tests/test_tei_validator.py` |
| Corpus integrity checker | `corpus/check_integrity.py`, `corpus/schema.json` | Pre-commit guard. Checks each JSONL row against the schema, against its quote file, and against the quote in the stored source. Exits with 1 on any violation. `corpus/` was a separate repository in the original. | High | Python standard library only | `tests/test_corpus.py` (4) |
| Span-existence check | `span_exists` in `src/litreview/verify.py:53` | True if a quote is a substring of the source after whitespace cleanup. | High | None | `tests/test_verify.py` (5, and 1 skips in the number check) |
| Number-existence check | `stat_exists` in `src/litreview/verify.py:62` | Hands a number to an outside script for OCR-aware matching. | Low | Outside helper script `stat_exists.py` (path set in `src/litreview/verify.py:26`). Not in the repo | `tests/test_verify.py`. 3 tests skip without the script |
| Data contracts | `src/litreview/models.py` | `Source`, `Span` (quote, offset, page coordinates and a mandatory `doc_id`), `ClaimRow`, `ParsedDoc` and `Anomaly`. The docstrings state the invariants. | Medium | Standard library | `tests/test_models.py` (8) |
| Corpus writer | `src/litreview/corpus.py` | Append-only JSONL corpus with `fragments/`, `sources/`, `exceptions/` and a manifest. The only write path. | Medium | Standard library | `tests/test_corpus.py` (4), `tests/test_spine.py` and `tests/test_expand.py` |
| Ingest | `src/litreview/ingest.py` | Turns a source and its cached TEI into a section tree, sentence spans and anomalies. Can call GROBID for a new PDF. | Medium | `grobid_client.py`. The GROBID server is needed only for new PDFs | `tests/test_ingest.py` (4) |
| GROBID client | `src/litreview/grobid_client.py` | A liveness probe that fails loudly with the Docker bring-up command. Also turns a PDF into TEI. | High | GROBID server `lfoppiano/grobid:0.8.0` on `localhost:8070`, and `grobid-client-python` | None. Unverified that `pdf_to_tei` works, because there is no test and no server here |
| Extraction seam | `src/litreview/extract.py` | A word-list candidate finder, the `SemanticExtractor` interface, `ManualExtractor` (replays hand-written fields) and `AnthropicExtractor` (one hosted-model call per span). | Medium | The `anthropic` package and `ANTHROPIC_API_KEY`, for `AnthropicExtractor` only. The word list `METHOD_LEXICON` is specific to mechanistic interpretability (MI). | `tests/test_extract.py` (3). `AnthropicExtractor` is not tested |
| Pipeline driver | `src/litreview/pipeline.py` | Runs ingest, extract, verify, grade and corpus write for one source. | Medium | The modules above | `tests/test_spine.py` (5), `tests/test_expand.py` (5) |
| Grade rules | `src/litreview/grade.py` | Sets an A to D grade from design, artifacts and reproduction. It enforces the rule that popularity never raises a grade. | Low | None. The rubric is specific to MI (`config/mi-domain-config.md`). | `tests/test_grade.py` (7) |
| Cross-paper linker | `src/litreview/link.py` | Gives each row the best grade for its method across papers (`effective_grade`, `backed_by`). | Low | None. The `_CANONICAL` method map is specific to MI. | `tests/test_link.py` (6) and `tests/test_expand.py` |
| Grade-weighted reduce | `src/litreview/reduce.py` | Loads corpus rows as evidence units and sums grade weights per method. | Medium | None | `tests/test_reduce.py` (3) |
| Source resolver | `src/litreview/resolve.py` | Turns an arXiv id or DOI into a `Source`. Raises on an unknown id. Downloads the PDF. | Low | Outside arXiv resolver scripts (path set in `src/litreview/resolve.py:18`). Not in the repo. Needs network | `tests/test_resolve.py` (3) |
| Domain config template | `config/mi-domain-config.md` | The unit of analysis, rubric, field table and id scheme for the MI domain. A template for other domains. | Medium | None | None (a document) |
| Build scripts | `scripts/build_spine.py`, `scripts/build_expand.py`, `scripts/run_dryrun.py` | Rebuild the corpus or run the 3-paper dry-run. They hold curated, hand-written rows for the MI survey and two papers. | Low | `PYTHONPATH=src`. They write into `corpus/` | `tests/test_spine.py` and `tests/test_expand.py` import the first two. The `run_dryrun.py` script has no test |

## Not reusable as is
- `data/*.grobid.tei.xml` and `corpus/sources/*.txt`: paper text and parser output for three specific papers. This is third-party content. The `THIRD-PARTY.md` at the root of the projects folder does not mention this project (searched for the project name, "grobid" and "arxiv"). To be confirmed.
- `dryrun_pdfs/arXiv_2211.00593.pdf`: one third-party paper used as dry-run input. Untracked.
- `uv.lock`: the dependency lock for this project only.

## Rust candidates
None. Nothing here is an application with an interface and heavy computation. Everything runs in under one second on a CPU (the full test run takes about 1 second). No code converted.
