> **Status: under construction.** This repository is the build setup (spec, domain config, failure fixtures and acceptance tests) for a source-grounded literature-review corpus. The full pipeline is not implemented yet. `docs/TECH-SPEC.md` lists what exists and what is still to do.

# Lit Review Pipeline

Start with `docs/TECH-SPEC.md`. Folder map below. Paths that start with `../Research Extractor/` point outside this repository.

Goal: a verified, source-grounded corpus of mechanistic-interpretability claims.
It front-loads the lit review for the Composition Signatures experiment. This folder is
the build setup: spec, domain config, failure fixtures and acceptance tests. The full
implementation is not here yet.

## Run it
Needs Python 3.11 or newer and `uv`. No network, GROBID server or API key is needed for these.

```
uv sync --frozen
uv run --frozen python -m pytest
```

Result on 2026-11-02 (Python 3.11, CPU only): 57 passed, 0 failed, 3 skipped.

The 3 skips share one cause. `verify.stat_exists` calls an outside helper script that is not in this repository. Set `LITREVIEW_STAT_SCRIPTS` to the folder holding `stat_exists.py` to run them. Without it the stat stays unverified and the row goes to the exception queue. `LITREVIEW_ARXIV_SCRIPTS` does the same for the DOI resolver. Details: `docs/TECH-SPEC.md`, section "How to run and test".
- `tests/test_verify.py::test_metric_value_verified_against_source`
- `tests/test_expand.py::test_total_rows`
- `tests/test_expand.py::test_single_primary_method_inherits_B`

One test: `uv run --frozen python -m pytest tests/test_grade.py::test_name`

Dry-run entry points (not run on 2026-11-02). They write into `corpus/`. Run on a copy only:
```
PYTHONPATH=src uv run --frozen python scripts/build_spine.py
PYTHONPATH=src uv run --frozen python scripts/build_expand.py
PYTHONPATH=src uv run --frozen python scripts/run_dryrun.py
```

Dependency audit: `uv export --frozen --no-hashes --no-emit-project -o req.txt && uvx pip-audit -r req.txt --no-deps`. After the lock update on 2026-11-02 it reports no known vulnerabilities.

## Folders
- `src/litreview/`: the pipeline code, one module per stage (order in `pipeline.py`).
- `tests/`: all tests. `tests/fixtures/` holds small GROBID XML snippets. `tests/acceptance.md` is the done-when list.
- `scripts/`: corpus builders and the dry-run driver. They write into `corpus/`. Run from the project root with `PYTHONPATH=src`.
- `config/`: domain rules (grading rubric, row fields, id scheme).
- `fixtures/`: notes on the four known GROBID failures.
- `data/`: cached GROBID output for three papers (inputs to the scripts and tests).
- `docs/`: `TECH-SPEC.md`, `COMPONENTS.md`, `BUILD-BRIEF.md`, `MODELS.md`.
- `dryrun_pdfs/`: one source PDF for the dry-run. Untracked.
- `corpus/`: output corpus. Its own repository in the original. Read only.
- Moves and deletions: `CHANGES.md`.
- Ignored when reading: `corpus/`, `uv.lock`, `data/*.xml`, `corpus/sources/`, `corpus/fragments/`, `dryrun_pdfs/`.

## What this is
A source-grounded pipeline. The verification stages are the same for every topic. The
build standards I follow gate the build. The per-topic config lives in `config/`. It holds the credibility rubric and the extraction
schema, pre-drafted for the mechanistic-interpretability (MI) domain. The decisions that
define truth are marked as gates. To be confirmed before any ingestion compute.

## Reuse
The ingestion stage already exists in `../Research Extractor/`:
- `grobid_parse.py` turns a PDF into GROBID TEI. It uses a local Docker server at localhost:8070.
- `unit2_section_tree.py` turns TEI into a section tree. It is namespace-qualified. Reviewed clean.
- `unit3_span_store.py` holds the span dataclass and the store. It is a skeleton. Still to add: a document-id field.
- `fork1_review.py` and `fork1_apply.py` do human-in-the-loop table extraction. They are rotation-aware.
These are imported as the ingestion components, not reimplemented.

## Status
- [x] Setup written (this folder).
- [x] Config gates confirmed on 2026-07-09. EMIT-CONFIG is cleared. The paper list is deferred to the dry-run.
- [x] Pipeline built against `BUILD-BRIEF.md` and `tests/` on 2026-07-09. The code is in `src/litreview/`. 49 tests were green.
- [x] The dry-run ran on 3 papers. IOI and ROME went through live GROBID. The survey was cached. The driver is `scripts/run_dryrun.py`. The tag is `dry-run-green`.
- [x] Spine milestone (survey only, depth first): 14 curated grade-D method-claim rows.
      Hardened with full stage coverage. The guards are green. The builder is `scripts/build_spine.py`. The tag is `spine-v1`.
- [x] Expand scope (option b): cross-paper grade inheritance. The code is `link.py` and `scripts/build_expand.py`.
      The tag is `expand-v1`. The corpus has 19 rows: the spine, IOI and ROME. `activation_patching` reaches
      effective grade A, because IOI and ROME reproduce it. Survey rows inherit the effective grade
      and keep their own D source grade. 60 tests are green with the outside helper script present.
- [ ] Add more primary papers. Olsson (2209.11895) and Superposition (2209.10652) go into
      `PRIMARIES` in `scripts/build_expand.py` once arXiv is reachable. Resolving and GROBID are already wired.
- [ ] Full-corpus run. Needs the `AnthropicExtractor` key for large-scale semantic extraction.

## Phase (2026-07-10)
Depth before breadth. The spine (the seed survey) is finished and hardened first. Then the primaries.

The spine is a method map: 14 rows, all grade D. It covers induction heads, superposition,
activation patching, ablation, path patching, logit lens and tuned lens, sparse autoencoders
and dictionary learning, and manual circuit tracing.

The strongest spans are hand-picked for now. Full-coverage extraction waits for the
`AnthropicExtractor` key.

Entry points:
- `scripts/build_spine.py` builds the spine.
- `scripts/build_expand.py` adds the primary papers.
- `scripts/run_dryrun.py` is the demo on the primaries.

## Read order
1. `docs/BUILD-BRIEF.md`: the execution brief.
2. `config/mi-domain-config.md`: the rubric and the schema. Gate: to be confirmed first.
3. `fixtures/known-grobid-failures.md`: the regression fixtures. All must pass.
4. `tests/acceptance.md`: when the build is done.

## AI use disclosure

I used an AI coding assistant to prepare this repository for presentation: dependency updates, security fixes, rewriting documentation and comments, and running the tests. The design and the original code are mine. The history here starts at the cleaned version.
