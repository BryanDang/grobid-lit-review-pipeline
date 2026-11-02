# Known GROBID Failures: Regression Fixtures

Real failures found in `../Research Extractor/Survey on Mech Interp.grobid.tei.xml`.
Each one is a permanent fixture. The structural
validator flags it. Extraction handles it, by routing it to the exception queue or
by skipping gracefully. Nothing passes silently. A bug counts as fixed only when its fixture is
green. Each test uses the minimal TEI snippet taken from the survey TEI.

## FIX-01: list steps mis-tagged as headings
Input: the "Manual Circuit Tracing: Key Steps" list. GROBID promoted steps "2." and
"5." to `<head n="2.">` and `<head n="5.">`. Steps 1, 3 and 4 stayed in `<p>`.
Expected: the validator flags any `<head>` whose `n` looks like a list step (a number with a
trailing dot and sentence-shaped text). A real section number looks different (for example
"4.2"). A list step is not counted as a real section.

## FIX-02: dropped section-heading numbers
Input: sections 2, 5, 7, 7.1, 9, 9.1 and 10 lost their heads and numbers. The head skeleton
jumps (from 8.4 to 9.2). Expected: the validator flags a heading sequence that is
non-monotonic or has gaps. It also flags missing top-level numbers. Section text with no head
is not orphaned: the parser carries the last-seen section forward.

## FIX-03: table row over-segmentation
Input: Table 1. GROBID exploded one multi-line "This Study" cell into 6 phantom
`<row>` elements, dropped other cells, and lost 4 survey rows. Expected: table numbers go to
the exception queue and to the human-in-the-loop table tool (`fork1_*`), never to a
silent grep pass. Numbers whose source is a mis-parsed table are marked unverified.

## FIX-04: empty section_tag (derived from FIX-02)
Input: spans whose source div had a dropped or None head. Expected: an empty `section_tag`
is flagged, not silently emitted. The spans cluster on the dropped-head pages (cross-reference
the head skeleton). The fix may live in this repo (carry the last-seen section forward), even
though the cause is GROBID.
