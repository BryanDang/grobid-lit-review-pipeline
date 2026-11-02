# MI Domain Config

## Contents
- Unit of analysis
- Credibility rubric (MI domain)
- Evidence-grade tiers
- Extraction schema (per-row fields)
- Document-id scheme
- Seed source set

Per-topic config for the pipeline. Decisions marked
**[GATE]** define what counts as truth for this corpus. Gate: to be confirmed before ingestion
compute (the EMIT-CONFIG hard gate). Leans are starting points, not menus.

> **EMIT-CONFIG cleared 2026-07-09.** The three gates that define truth are the unit of
> analysis, the doc_id scheme and the span granularity. All three are **[DECIDED]** below,
> each with its reason. The paper-list gate stays open. It is a DRY-RUN decision, not a
> config decision. A recommended set is pre-filled. A decision is reversed by editing its
> block before ingestion compute begins.

## Unit of analysis
**[DECIDED]** One row is one *method-claim* pair. It pairs a mechanistic-interpretability
technique (for example activation patching, an SAE feature or the IOI circuit) with a specific
claim made about it. The claim says what the technique shows, on which model, and with what
evidence. Lean: method-claim, because the experiment maps techniques to
evidence, not papers to summaries.
> Reason: paper-level rows collapse multiple claims. That destroys the per-claim
> reproducibility grading the rubric depends on. The same (method, claim) pair recurring
> across papers is expected. `doc_id` tells the rows apart. Cross-paper
> dedup is out of scope for the dry-run. Grain confirmed.

## Credibility rubric (MI domain)
This is the evidence hierarchy, strongest first:
- A reproduced causal result with released code and weights. For example activation
  patching or ablation with logit-difference deltas on a named model.
- A single-paper causal result with released code.
- An observational or attribution result (probing, attention visualization). It is
  correlational. Flag it.
- A survey, position paper or blog synthesis. It is context only and not primary evidence.

**The popularity trap:** in MI, GitHub stars and Twitter reach
masquerade as validity. A widely cited technique with no released reproduction is not in a
higher tier than a quiet paper with code and weights. Rule: grade by reproducibility and record
the tier. Never gate by venue or popularity.

## Evidence-grade tiers (A, B, C, D)
- **A**: causal, reproduced, with code and weights released.
- **B**: causal, from a single paper, with code released.
- **C**: observational or correlational, or causal without released artifacts.
- **D**: survey, blog or position paper. Context only.

Upgrade trigger: independent reproduction. Downgrade triggers: no artifacts, or
a claim that exceeds what the method demonstrates (for example "understands" from a probe).

## Extraction schema (per-row fields)
Each field holds one fact. Every claim field gets a paired `_source_span`. Numbers are split
into value, unit and baseline. Stable ids are their own joinable fields.

| Field | Type | Notes |
|---|---|---|
| doc_id | str | **[DECIDED]** The canonical id (see the id-scheme block below). Joinable. |
| doc_version | str | The full versioned arXiv id (for example `2211.00593v5`). It is the reproducibility anchor. |
| method | str | The MI technique named. |
| claim | str | What is asserted about the method. |
| claim_source_span | span | (verbatim_quote, char_offset, page_coords). |
| model | str | The model the result is on (GPT-2-small, Pythia-160M and so on). |
| metric | str | For example logit-difference or faithfulness. |
| metric_value | float\|null | The numeric result. |
| metric_unit | str\|null | Never fused with the value. |
| baseline_described | bool | Whether the comparison baseline is stated. |
| causal | bool | Causal (intervention) or observational. |
| artifacts | enum | code+weights, code, or none. It drives the grade. |
| evidence_grade | enum | A, B, C or D from the tiers above. It rides on every row. |
| grade_source_span | span | Why this grade. It holds the evidence quote. |

**[DECIDED]** Span granularity. Keep both `page_coords` (line-level, as GROBID emits it)
and `char_offset` into the section text. `doc_id` is mandatory on every span (the unit3
document-id enhancement).
> Reason: the two serve different readers, and neither can be rebuilt from the
> other later. `page_coords` traces a quote back to the PDF by eye during
> verification. `char_offset` gives deterministic `stat_exists` text matching against the
> stored `fragments/` artifact. Both are cheap at write time and expensive to
> backfill. `doc_id` on every span is required. Without it a span cannot be traced
> across papers.

## Document-id scheme
**[DECIDED]** The canonical `doc_id` is the arXiv id when present. The DOI is the fallback.
- Primary: the arXiv id **with the version stripped** is the join key (`2211.00593`). MI is
  arXiv-first, and many canonical papers never receive a journal DOI. The full
  versioned id goes in `doc_version` (`2211.00593v5`). That ties reproducibility to the exact
  version. When a DOI also exists, it gets its own field. Both are joinable, and one
  is canonical.
- Fallback: the DOI (`10.xxxx/...`), only for papers with no arXiv presence.
- Normalize ids to `arXiv:<id>` and `doi:<id>` prefixes. The id namespace stays
  unambiguous. The join key never collides across schemes.
> Reason: a version-stripped join key lets the rows of one paper aggregate. `doc_version`
> keeps the reproducibility anchor. A grade-A "reproduced" claim names the version
> it reproduced.

## Seed source set (a starting point, not exhaustive)
The survey already ingested (`../Research Extractor/Survey on Mech Interp.pdf`) is the
spine. Expand from its bibliography. **[GATE: stays open, a DRY-RUN decision]** Paper list:
to be confirmed at the DRY-RUN gate.
> Recommended dry-run set. Final call at the DRY-RUN gate.
> The papers are canonical MI and release code and weights, so the grade-A
> path is exercised, not assumed:
> - **IOI circuit**: Wang et al. 2022, `arXiv:2211.00593` (code released, GPT-2-small).
> - **ROME / activation patching**: Meng et al. 2022, `arXiv:2202.05262` (code and weights).
> - **SAE features**: one released-code SAE paper (for example Cunningham et al. `arXiv:2309.08600`).
> Note: two of these need live GROBID, because only the survey TEI is cached. See the GROBID
> dependency in `BUILD-BRIEF.md`. If GROBID is still down at the DRY-RUN gate: use
> papers whose TEI is already cached. No blocking on the bring-up.
