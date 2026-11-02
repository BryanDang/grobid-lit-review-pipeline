# Acceptance: Definition of Done

Done for the dry-run milestone when all of these hold:

## Gates
- [x] EMIT-CONFIG gate cleared (2026-07-09). The three truth-defining `[GATE]`s in
      `config/mi-domain-config.md` are resolved as `[DECIDED]`: the unit of analysis, the doc_id scheme and the
      span granularity. The paper-list gate is reclassified
      as a DRY-RUN decision (with a recommended set pre-filled). That matches the brief's split between
      EMIT-CONFIG (define truth) and DRY-RUN (paper list).
- [ ] DRY-RUN gate cleared: the rubric and schema are calibrated against real output on 2 or 3
      papers, and approval comes before full-corpus compute. **Open: approval. The dry-run
      ran green on 2026-07-09 (output of `scripts/run_dryrun.py`, and `corpus/`). This box is the gate.**

## Correctness
- [x] All four fixtures in `fixtures/known-grobid-failures.md` are caught. The validator
      flags each one on both the minimal snippets (tests/test_tei_validator.py, 6 green) and the
      real TEIs. The dry-run routed FIX-01:2, FIX-02:18, FIX-03:18 and FIX-04:35 to
      `corpus/exceptions/anomaly.jsonl`. None was silent.
- [x] Every extracted claim row carries a `claim_source_span` whose verbatim quote is
      confirmed in the source. Checks: the deterministic span check and stat_exists. The
      pre-commit checker re-verifies on every commit. A fabricated span was rejected with exit 1.
- [x] Every span carries a `doc_id`. `Span.__post_init__` makes it mandatory (the unit3 enhancement).
- [x] Reduce reads the clean structured corpus (`master.jsonl`), never raw sources.
      It weights by grade (reduce.GRADE_WEIGHT: A=1.0 down to D=0.1).

## Build standards
- [x] Every public function and dataclass has a contract-shaped docstring
      (purpose, Args with types and ranges, Returns, Raises, invariants).
- [x] The outside corpus guards were initialized on the corpus dir before
      fan-out. Done through the separate-git-dir recipe, because the guard setup script refuses iCloud
      dirs. Git, the pre-commit checker and schema.json are installed. stat_exists is delegated in verify.py.
- [x] The structural validator runs as a monitor. NEW-* codes surface unrecognized head
      formats, and those become new fixtures. It is not a one-time check.
- [x] The GROBID Docker image tag is pinned (`grobid_client.GROBID_TAG` is lfoppiano/grobid:0.8.0).
      It is recorded per document in `corpus/MANIFEST.json.grobid_tag`. Rule: re-run the fixtures on a
      deliberate upgrade.

## Out of scope for the dry-run
The full corpus, cross-paper dedup at scale, and the synthesis write-up. All three follow a green
dry-run.
