# BUILD BRIEF: Lit Review Pipeline

## Contents
- Mandate
- Hard gates
- Stages
- Contracts
- Regression fixtures
- Definition of done
- Out of scope
- Corpus storage layout
- Dependencies and feasibility

The current state of the build is in `docs/TECH-SPEC.md`.

> The directory name was generalized from "MI Lit Review Pipeline" on 2026-07-09. The pipeline
> harness is domain-agnostic. The mechanistic-interpretability (MI) mandate below is its first
> instantiation. Broader domains go in sibling `config/<domain>-config.md` files. The harness
> stays unchanged for them.

## Mandate
Goal: a verified, source-grounded corpus of mechanistic-interpretability claims.
Method: build the fixed pipeline stages below. Outside helpers are called, not reimplemented.
The build standards I follow apply throughout: contracts in docstrings, regression
fixtures and a validator that acts as a monitor. Judgment calls are logged inline.

## Hard gates
1. **EMIT-CONFIG gate.** `config/mi-domain-config.md` has decisions marked `[GATE]`.
   They define what counts as truth for the corpus. Gate: to be confirmed before any
   ingestion compute.
2. **DRY-RUN gate.** Run the full pipeline on 2 or 3 papers only. Surface the verified rows
   and the unhealable residual. Calibrate the rubric and the schema. Gate: approval
   before any full-corpus compute.

## Stages (ingestion reuses the ../Research Extractor components)
1. **Resolve.** Find MI papers by DOI or arXiv id. Call the outside arXiv resolver scripts.
2. **Ingest.** Turn the PDF into GROBID TEI with `grobid_parse.py`. Turn the TEI into a
   section tree with `unit2_section_tree.py`. Turn the tree into spans with
   `unit3_span_store.py`. This is the highest-risk box. Tables and OCR'd digits corrupt silently. Wire the
   table-extraction check (`fork1_*`). Wire a TEI structural validator that
   flags the failures in `fixtures/`.
3. **Extract.** Write per-claim rows with span attribution: `(value, verbatim_quote,
   char_offset, page_coords)`. The schema is in `config/`. Be deterministic where possible.
   Use models only for judgments that are irreducibly semantic.
4. **Verify.** Run a deterministic span-existence check. Send the residual to an adjudicator.
   Call the outside verification helpers. Set up the corpus guards on the corpus dir before
   fan-out. Then use `stat_exists` and `cite_check`.
5. **Grade.** Assign evidence tiers per row. Use the A to D tiers in `config/mi-domain-config.md`.
6. **Reduce.** Synthesize over the clean corpus, weighted by grade. Use the outside reduce adapter
   (structured corpus).

## Contracts (written in docstrings; code review checks against these)
- `resolve_sources(ids: list[str]) -> list[Source]`. A Source carries {doc_id, title,
  path, tier_hint}. It raises on an unresolvable id. It never silently drops one.
- `ingest(source: Source) -> ParsedDoc`. A ParsedDoc carries the section tree and the span
  store. It runs the structural validator. Anomalies go to an exception queue. They do
  not pass silently.
- `extract(doc: ParsedDoc) -> list[ClaimRow]`. One fact per field. Every claim field is
  paired with a `_source_span`. The schema is in config.
- `verify(rows) -> (verified, residual)`. The deterministic span check comes first. Only the
  residual reaches an adjudicator model.
- Every public function and dataclass has a docstring. It states the purpose, the Args
  (type and range), the Returns, the Raises and the invariants.

## Regression fixtures (all must pass)
`fixtures/known-grobid-failures.md` holds the real failures already found in the
survey PDF. Each one becomes a permanent test. The validator must flag it. Extraction handles
it, either by skipping gracefully or by routing it to the exception queue. It never
passes silently.

## Definition of done
See `tests/acceptance.md`. In short, the dry-run produces a clean, span-verified corpus on
2 or 3 papers. All the fixtures are caught. The config gates are confirmed. Reduce runs
over the corpus and not over raw sources.

## Out of scope
Fixing GROBID upstream. It is a pinned local Docker image. Rule: pin the tag and re-run the
fixtures on a deliberate upgrade. Also out of scope: cross-vendor verification chains.
Single-family healing only.

## Corpus storage layout (this defines "the corpus dir" for the stage 4 guards)
The outside corpus guards run on this layout. It is fixed before
fan-out:
```
corpus/
  master.jsonl            # one ClaimRow per line. Append-only. Keyed by doc_id and row_id.
  fragments/              # one file per source span: <doc_id>__<row_id>.txt holding the
                          #   verbatim_quote, so stat_exists checks a stored artifact
                          #   and not a live re-fetch
  sources/                # resolved PDFs and the cached <doc_id>.grobid.tei.xml (GROBID output)
  exceptions/             # rows and tables routed out of the silent path (FIX-03 tables,
                          #   FIX-04 empty section_tag, adjudicator residual)
  MANIFEST.json           # doc_id maps to {title, arxiv_id, doi, doc_version, grobid_tag}
```
Reason for the layout: a stored `fragments/` artifact makes span existence deterministic and checkable
offline. The `exceptions/` folder makes the "never pass silently" contract visible as
files, not only as log lines.

## Dependencies and feasibility (probed 2026-07-09)
- **GROBID is qualified and blocks new-paper ingestion.** At probe time the Docker daemon was down. No
  GROBID image was pulled. Nothing listened on `:8070`. `../Research Extractor/grobid_parse.py:3`
  hardcodes `http://localhost:8070`, and **no tag is pinned anywhere** (no compose file, no
  Dockerfile, no notes). The `.grobid.tei.xml` of the seed survey is already cached, so the
  seed needs no GROBID. Any new dry-run paper needs it. The first ingestion step is
  a liveness probe (`GET /api/isalive`). It fails loudly with the bring-up command if
  the server is down. The tag is pinned on first bring-up (`lfoppiano/grobid:0.8.0`)
  and recorded in `MANIFEST.json.grobid_tag`. That satisfies the acceptance criterion "pin
  the tag", which had nothing to pin before.
- **The outside reduce adapter (structured corpus) is qualified, and it is a stub.** The
  contract sketch exists. A row is an evidence unit. A stored span is a pointer. The
  evidence_grade feeds confidence. Its full interface is not specified. So stage 6 Reduce is
  not a turnkey call. The row-reading interface is specified in this build: read
  `master.jsonl`, filter rows by grade, feed each row as an evidence unit. Then Reduce runs
  the unchanged outside reasoning loop over it.
