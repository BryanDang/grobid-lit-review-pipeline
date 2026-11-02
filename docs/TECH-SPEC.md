# Technical Specification: Lit Review Pipeline

## Contents
1. Start here
2. What it is
3. What is built (architecture, stages, data contracts, corpus layout, quality rules)
4. TBD
5. How to run and test
6. Open questions

## Start here
- What this is: a Python pipeline that turns research papers into a corpus of graded, source-checked claims about mechanistic interpretability (MI, the study of how neural networks compute internally).
- Where to start: this file, then `src/litreview/pipeline.py` (the stage order), then `docs/COMPONENTS.md`.
- How to run: `README.md`, section "Run it". No GROBID server, no model and no API key are needed.
- What is broken: 3 of 60 tests skip here because a helper script that lives outside this repo is missing (section "How to run and test"). The full-corpus run is not done. The dry-run is not approved yet (section "TBD").
- Next: section "Open questions". Then the choice on the outside helper scripts (TBD item 1).

## What it is
The pipeline builds a corpus for a lit review ahead of the "Composition Signatures" experiment. `README.md` names it. The experiment itself is not in this folder. Each corpus row is one method-claim pair: an MI technique plus one claim a paper makes about it. Every claim must point to an exact quote in its source, and every row gets an evidence grade (A best, D weakest).

The design rules come from `docs/BUILD-BRIEF.md` and `config/mi-domain-config.md`:
- Deterministic code does the exact work (finding spans, checking quotes, joining rows). A language model is used only at one seam (`SemanticExtractor`, `src/litreview/extract.py`).
- Nothing fails silently. Parsing problems and unverified rows are written to files under `corpus/exceptions/`.
- Popularity (stars, citations) never raises a grade. Only reproducibility does (`src/litreview/grade.py`, module docstring).

Two things are separate from this repo (see `.gitignore`):
- `corpus/` was its own git repository in the original. It is included here as a read-only copy. Not edited.
- The ingestion helpers named in `README.md` ("../Research Extractor/") are not in this repository. `src/litreview/ingest.py` re-implements their idea, so the pipeline does not need them. See the module docstring, lines 1-10.

## What is built

### Pipeline in one line
Six stages, wired by `process_source` in `src/litreview/pipeline.py:23`:

The order is: resolve, ingest, extract, verify, grade, write corpus, link, reduce.

`link` and `reduce` run over the finished corpus. They do not run over raw papers.

### Stage table
| # | Stage | Entry point | What it does | Tests |
|---|---|---|---|---|
| 1 | Resolve | `resolve_sources` in `src/litreview/resolve.py:35` | Turns arXiv ids or DOIs into `Source` records. Raises on an id it cannot resolve. It calls outside arXiv resolver scripts. | `tests/test_resolve.py` (3) |
| 2 | Ingest | `ingest` in `src/litreview/ingest.py:41` | Reads a GROBID TEI file (GROBID is a tool that turns a PDF into structured XML called TEI), builds a section tree and sentence spans, runs the structure checker. | `tests/test_ingest.py` (4) |
| 2a | Structure check | `validate_structure` in `src/litreview/tei_validator.py:76` | Flags the four known GROBID failures (FIX-01 to FIX-04). Also flags unknown heading formats (`NEW-*`). | `tests/test_tei_validator.py` (7) |
| 3 | Extract | `extract` in `src/litreview/extract.py:78` | Finds candidate spans with a word list, then asks a `SemanticExtractor` to fill the row fields. | `tests/test_extract.py` (3) |
| 4 | Verify | `verify` in `src/litreview/verify.py:80` | Checks that the quote is in the source text. Checks any number through an outside helper script. Failures go to a residual list. | `tests/test_verify.py` (5) |
| 5 | Grade | `assign_grade` in `src/litreview/grade.py:17` | Sets grade A to D from the design (causal or not), the released artifacts and reproduction. | `tests/test_grade.py` (7) |
| 6a | Link | `link_corpus` in `src/litreview/link.py:73` | Gives each row an `effective_grade`: the best grade for the same method across papers. Two independent causal papers with code and weights give A. | `tests/test_link.py` (6) |
| 6b | Reduce | `synthesize_by_method` in `src/litreview/reduce.py:80` | Sums grade weights per method (A 1.0 down to D 0.1). | `tests/test_reduce.py` (3) |

Corpus writing is in `src/litreview/corpus.py` (`Corpus`, line 30). Its tests are in `tests/test_corpus.py` (4). Whole-pipeline checks are in `tests/test_spine.py` (5) and `tests/test_expand.py` (5).

### Grade rules
From `src/litreview/grade.py` (docstring, "Grade logic"):

| Grade | Meaning |
|---|---|
| A | Causal result, code and weights released, independently reproduced. |
| B | Causal result, one paper, code released, not reproduced. |
| C | Observational result, or causal with no released artifacts. |
| D | Survey, blog or position paper. Context only. |

A row keeps its own source grade in `evidence_grade`. `effective_grade` is the method-level grade after linking and is never weaker (`src/litreview/models.py:201`, class docstring).

### Data contracts
All in `src/litreview/models.py`. Each has a docstring with Args, Returns, Raises and invariants.

| Type | Line | Purpose |
|---|---|---|
| `Source` | 69 | A paper to ingest: `doc_id`, title, path, tier hint. |
| `Span` | 108 | A quote with `doc_id`, character offset and page coordinates. `doc_id` is required. |
| `Section`, `Anomaly`, `ParsedDoc` | 142, 161, 176 | Output of ingest. |
| `ClaimRow` | 201 | One method-claim pair. Fields: method, claim, claim span, model, metric, value, unit, baseline flag, causal flag, artifacts, grades, `backed_by`. |

Document ids look like `arXiv:2211.00593` (the version is stripped for joining, and the full version is kept for reproducibility). Rule: `config/mi-domain-config.md`, heading "Document-id scheme". Helper: `normalize_arxiv_id`, `src/litreview/models.py:21`.

### Corpus layout
Written only through `Corpus` (`src/litreview/corpus.py`). Defined in `docs/BUILD-BRIEF.md`, heading "Corpus storage layout".

| Path under `corpus/` | Content |
|---|---|
| `master.jsonl` | One verified `ClaimRow` per line. |
| `fragments/` | One text file per quote, named `<doc>__<row>.txt`. Lets quote checks run offline. |
| `sources/` | Plain text of each ingested paper. |
| `exceptions/` | `anomaly.jsonl` (structure problems), residual rows, number-check queue. |
| `MANIFEST.json` | Per paper: title, ids, GROBID tag. |
| `schema.json`, `check_integrity.py` | Row schema and a pre-commit checker. It re-checks every quote against its source. |

The current corpus has 19 rows from three papers (a survey, the IOI paper and the ROME paper). `README.md` "Status" says so, and `corpus/master.jsonl` holds 19 rows (counted). The IOI paper is Wang et al., 2022, arXiv 2211.00593. The ROME paper is Meng et al., 2022, arXiv 2202.05262.

### GROBID failure fixtures
Four real failures are permanent tests. `fixtures/known-grobid-failures.md` describes them. The snippets are in `tests/fixtures/`.

| Code | Failure | Handling |
|---|---|---|
| FIX-01 | List steps tagged as headings | Flagged, not counted as a section. |
| FIX-02 | Section numbers dropped | Flagged. The last seen section is carried forward. |
| FIX-03 | Table rows split into phantom rows | Numbers go to the exception queue. |
| FIX-04 | Empty section tag | Flagged and filled by carry-forward. |

The validator also acts as a monitor: an unknown heading format raises a `NEW-*` code so it can become a new fixture (`src/litreview/tei_validator.py:181`).

### External pieces the code expects
| Piece | Where used | In this repo? |
|---|---|---|
| GROBID server `lfoppiano/grobid:0.8.0` on `localhost:8070` | `src/litreview/grobid_client.py:18-22` | No. Only needed for new PDFs. Cached TEI files are in `data/`. |
| Outside helper script `stat_exists.py` | `src/litreview/verify.py:26` | No. |
| Outside arXiv resolver scripts | `src/litreview/resolve.py:18` | No. |
| Hosted language-model API, key in `ANTHROPIC_API_KEY` | `AnthropicExtractor`, `src/litreview/extract.py:136` | No key here. Not run (marked `pragma: no cover`). |

### Folder map
See `README.md`, section "Folders". Reusable pieces: `docs/COMPONENTS.md`.

## TBD
Sources: `README.md` "Status" (two unchecked boxes), `tests/acceptance.md` (one unchecked box), code comments and the test run. The original folder had no git history.

1. **Ship or replace the two outside helper scripts.**
   - Current state: the code calls `stat_exists.py` and the outside arXiv resolver scripts by an environment variable (`LITREVIEW_STAT_SCRIPTS`, `LITREVIEW_ARXIV_SCRIPTS`). They are not in the repo. Three tests skip without `stat_exists.py`.
   - Stopped at: `src/litreview/verify.py` and `src/litreview/resolve.py`.
   - Done when: `python -m pytest` shows 0 skipped on a machine that has only this repo and its dependencies.
2. **Dry-run approval gate.**
   - Current state: the dry-run ran on 3 papers and the output looks right. Not approved yet.
   - Stopped at: `tests/acceptance.md`, heading "Gates", unchecked box "DRY-RUN gate cleared".
   - Done when: that box in `tests/acceptance.md` is ticked.
3. **Widen primary coverage.**
   - Current state: only IOI and ROME are in the corpus. Named but not added: Olsson (arXiv 2209.11895) and Superposition (arXiv 2209.10652). `config/mi-domain-config.md` also suggests a sparse-autoencoder paper (arXiv 2309.08600). It is not in the corpus.
   - Stopped at: `scripts/build_expand.py`, list `PRIMARIES` (line 36).
   - Done when: `corpus/master.jsonl` has rows from each added paper, and `python -m pytest` passes with the expected counts in `tests/test_expand.py` updated.
4. **Full-corpus run with model-based extraction.**
   - Current state: rows are written by hand (`ManualExtractor`, `scripts/build_spine.py`). `AnthropicExtractor` is written but never run here.
   - Stopped at: `src/litreview/extract.py:136`. It also hard-codes a model id (`claude-opus-4-8`). Unverified: whether this id exists.
   - Done when: a run with the key set produces rows for the full paper list, each row passes `verify`, and a test covers `AnthropicExtractor` with a fake client.
5. **Table numbers have no repair path.**
   - Current state: FIX-03 sends table numbers to `corpus/exceptions/`. The human table tool named in `docs/BUILD-BRIEF.md` (`fork1_*`) is not in this repo. Unverified: `git ls-files` did not list those files.
   - Stopped at: `src/litreview/tei_validator.py:119`.
   - Done when: a documented step corrects a table and releases its numbers, with one test.
6. **Reduce is not the real outside reduce adapter.**
   - Current state: `src/litreview/reduce.py` weights rows and groups by method. `docs/BUILD-BRIEF.md` says the outside reduce adapter interface is a stub, to be specified here. The prose synthesis is out of scope for the dry-run. See `tests/acceptance.md`, "Out of scope".
   - Stopped at: `src/litreview/reduce.py:80`.
   - Done when: a written synthesis of the corpus exists, built only from `corpus/master.jsonl`.
7. **Manifest has desktop paths.**
   - Current state: the `tei_path` values in `corpus/MANIFEST.json` were absolute desktop paths. Now relative (`data/...`). `src/litreview/corpus.py` writes absolute paths again on a rebuild.
   - Stopped at: `src/litreview/corpus.py`, `_record_manifest`.
   - Done when: the writer records relative paths. The same edit is needed in the corpus repository.
8. **Stale notes in older docs.**
   - Current state: `README.md`, `fixtures/known-grobid-failures.md` and `config/mi-domain-config.md` still point to `../Research Extractor/`. `tests/acceptance.md` named `run_dryrun.py` at the old root location. That pointer is updated (see `CHANGES.md`).
   - Done when: those pointers match the real layout in `README.md`, section "Folders".

## How to run and test
From the project root. Tests need Python 3.11 or newer and `pytest`. They import only the standard library and `litreview` (`pytest.ini` sets `pythonpath = src`). `anthropic` and `grobid-client-python` are imported only inside functions that tests do not reach. Unverified for `grobid_client.pdf_to_tei`: no test covers it.

```
uv sync --frozen
uv run --frozen python -m pytest                      # all tests
uv run --frozen python -m pytest tests/test_grade.py  # one file
uv run --frozen python -m pytest tests/test_grade.py::test_name   # one test
```

Result (2026-11-02, Python 3.11, CPU only, no network use): 57 passed, 0 failed, 3 skipped, 0 errors, about 1 second.

The 3 skips share one cause. `verify.stat_exists` calls an outside `stat_exists.py` helper. Its folder is set with `LITREVIEW_STAT_SCRIPTS`. Unset, the call returns "not verified" and the row goes to the exception queue.
- `tests/test_verify.py::test_metric_value_verified_against_source`
- `tests/test_expand.py::test_total_rows` (17 rows instead of 19. Two corpus rows carry a number, counted in `corpus/master.jsonl`)
- `tests/test_expand.py::test_single_primary_method_inherits_B`

Cause check (before the tests were made to skip): with a stand-in `stat_exists.py` (it always exits 0) under a temporary home folder, all 60 tests passed. That confirms the cause. Whether the real script behaves the same is unverified. The stand-in is not in the repo.

The scripts write into `corpus/`, so they run only on a copy. Not run for these notes:
```
PYTHONPATH=src uv run --frozen python scripts/build_spine.py     # survey-only corpus (14 rows)
PYTHONPATH=src uv run --frozen python scripts/build_expand.py    # survey, IOI and ROME (19 rows)
PYTHONPATH=src uv run --frozen python scripts/run_dryrun.py      # dry-run report, from the project root
```
A new PDF needs the GROBID server: `docker run -d --name grobid -p 8070:8070 lfoppiano/grobid:0.8.0`. Command source: `src/litreview/grobid_client.py`. Not run here.

## Open questions
1. Which copy of the GROBID output is current? `data/` and `dryrun_pdfs/` held byte-identical copies of the IOI and ROME files. The scripts and tests use `data/`, so the `dryrun_pdfs/` copies were removed (see `CHANGES.md`). Reversible if both are wanted.
2. Copy the two outside helper scripts into this project? Done for now: the tests skip when `LITREVIEW_STAT_SCRIPTS` is unset. Shipping the helpers is still open.
3. `claude-opus-4-8` as the default model id for `AnthropicExtractor`: unverified.
4. Dry-run approval (TBD item 2). Only the full-corpus run is gated on it.
5. `docs/BUILD-BRIEF.md` moved from the project root to `docs/`. Open: keep it there or return it to the root.
