#!/usr/bin/env python3
"""Structural validator for GROBID TEI.

Purpose: GROBID's section and table parsing fails silently on the survey PDF in four known
ways (see fixtures/known-grobid-failures.md). This module builds the section tree with
carry-forward. It also flags every known failure as an `Anomaly`. That way extraction never
passes a corrupted structure silently. It runs as a monitor. Unknown structural problems
are reported generically, so new failures become new fixtures.

The four regression fixtures (all must be caught):
    FIX-01  list steps mis-tagged as headings   (<head n="2."> with sentence-shaped text)
    FIX-02  dropped section-heading numbers      (orphan subsection or non-monotonic numbers)
    FIX-03  table row over-segmentation          (table numbers go to the exception queue)
    FIX-04  empty section_tag from dropped heads (flag it and carry the last-seen section forward)

Namespace note: TEI declares a default XML namespace. Every search must be namespace-qualified.
Otherwise it silently finds nothing. Learned in unit2.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .models import Anomaly, Section

TEI_NS = {"t": "http://www.tei-c.org/ns/1.0"}

# A list-step number is one or more digits, then a single trailing dot, and nothing else
# ("2.", "5."). A real section number is a bare integer ("8") or a dotted multi-level
# number ("4.2"). Neither matches this.
_LIST_STEP_N = re.compile(r"^\d+\.$")
# A real numbered section: "1", "4", "4.2", "3.2.1".
_SECTION_N = re.compile(r"^\d+(\.\d+)*$")


@dataclass
class ValidationResult:
    """Output of `validate_structure`.

    Fields:
        sections: section tree in document order, with carry-forward applied (text
            from a dropped-head div is attributed to the last-seen real section).
        anomalies: every structural problem flagged (FIX-01..04 and NEW-* monitor finds).
        table_regions: coords/ids of table figures whose numbers must route to the
            exception queue (human-in-the-loop), never a silent grep-pass.
    """

    sections: list[Section] = field(default_factory=list)
    anomalies: list[Anomaly] = field(default_factory=list)
    table_regions: list[str] = field(default_factory=list)

    def has(self, code: str) -> bool:
        """True if any flagged anomaly carries this code (e.g. "FIX-02")."""
        return any(a.code == code for a in self.anomalies)


def _num_tuple(number: str) -> tuple[int, ...]:
    """Parse a section number like "4.2" into (4, 2). Empty or invalid gives ()."""
    if not _SECTION_N.match(number):
        return ()
    return tuple(int(p) for p in number.split(".") if p != "")


def _is_sentence_shaped(text: str) -> bool:
    """True if heading text reads like a list step, not a section name (>=4 words)."""
    return len(text.split()) >= 4


def _local(tag: str) -> str:
    """Strip the namespace from an ElementTree tag, leaving the local name."""
    return tag.rsplit("}", 1)[-1]


def validate_structure(tei_path: str | Path, doc_id: str = "") -> ValidationResult:
    """Build the section tree with carry-forward and flag every structural anomaly.

    Args:
        tei_path: path to a GROBID `.tei.xml` file.
        doc_id: canonical id of the source (recorded on anomaly locators; optional).

    Returns:
        ValidationResult(sections, anomalies, table_regions). Sections carry text with
        carry-forward applied. Anomalies list FIX-01..04 and any NEW-* monitor finds.

    Raises:
        FileNotFoundError: if tei_path does not exist.
        ValueError: if the TEI has no <body> (namespace or file problem).

    Invariants:
        A div is either a real section (added to sections) or produces an anomaly
        (FIX-01 list step, FIX-04 dropped head) — never silently dropped. Table
        figures are recorded in table_regions AND raise FIX-03.
    """
    tei_path = Path(tei_path)
    if not tei_path.exists():
        raise FileNotFoundError(f"TEI not found: {tei_path}")
    root = ET.parse(tei_path).getroot()
    body = root.find(".//t:text/t:body", TEI_NS)
    if body is None:
        raise ValueError(f"No <body> in {tei_path} - namespace or file problem.")

    result = ValidationResult()
    declared_top: set[int] = set()          # top-level ints that appeared as their own head
    numbered_heads: list[tuple[str, str]] = []  # (number, title) for real sections, in order
    last_section: Section | None = None     # for carry-forward (FIX-04)
    prev_tuple: tuple[int, ...] = ()

    # FIX-03: tables are <figure type="table"> anywhere in the body (GROBID emits them
    # as body-level siblings of <div>, not nested inside sections). Route every one to
    # the exception queue and the human table tool; its numbers are never grep-passed silently.
    for fig in body.findall(".//t:figure", TEI_NS):
        if (fig.get("type") or "").lower() == "table":
            fid = (fig.get("{http://www.w3.org/XML/1998/namespace}id")
                   or fig.get("coords") or "table")
            result.table_regions.append(fid)
            result.anomalies.append(Anomaly(
                code="FIX-03",
                detail=("table figure detected; GROBID row parsing is unreliable "
                        "(over-segmentation) — numbers route to exception queue, "
                        "never a silent grep-pass"),
                locator=f"{doc_id} {fid}".strip(),
            ))

    for div in body.findall("t:div", TEI_NS):
        head = div.find("t:head", TEI_NS)
        body_text = " ".join(
            "".join(p.itertext()).strip()
            for p in div.findall("t:p", TEI_NS)
        ).strip()

        if head is None or not "".join(head.itertext()).strip():
            # FIX-04: div with no usable head gives an empty section_tag. Carry forward.
            if body_text:  # ignore genuinely empty structural divs
                result.anomalies.append(Anomaly(
                    code="FIX-04",
                    detail="div body with dropped/empty head; attributed to last-seen "
                           "section (carry-forward), empty section_tag flagged",
                    locator=f"{doc_id} after {last_section.number if last_section else 'START'}".strip(),
                ))
                if last_section is not None:
                    last_section.text = (last_section.text + " " + body_text).strip()
            continue

        number = head.get("n", "").strip()
        title = "".join(head.itertext()).strip()

        # FIX-04 (real shape): head present but its NUMBER was dropped (no @n). It cannot
        # form a numbered section tag, so section_tag is empty. Flag it and carry the text
        # forward to the last numbered section rather than emitting an empty-number
        # section silently. (The headless-div shape is handled above, same code.)
        if not number:
            result.anomalies.append(Anomaly(
                code="FIX-04",
                detail=f"head with dropped/empty number ({title[:30]!r}); empty "
                       f"section_tag flagged, text carried forward",
                locator=f"{doc_id} after {last_section.number if last_section else 'START'}".strip(),
            ))
            if last_section is not None:
                merged = (title + " " + body_text).strip()
                last_section.text = (last_section.text + " " + merged).strip()
            continue

        # FIX-01: list step mis-tagged as a heading (trailing-dot integer and sentence-shaped text).
        if _LIST_STEP_N.match(number) and _is_sentence_shaped(title):
            result.anomalies.append(Anomaly(
                code="FIX-01",
                detail=f"<head n={number!r}> is a list step (trailing-dot number, "
                       f"sentence-shaped text), not a section; not counted as a section",
                locator=f"{doc_id} {number} {title[:40]}".strip(),
            ))
            if last_section is not None and body_text:
                last_section.text = (last_section.text + " " + body_text).strip()
            continue

        # A head with a number that is neither a valid section number nor a flagged list
        # step is a NEW anomaly (monitor): surface it rather than silently trusting it.
        if number and not _SECTION_N.match(number):
            result.anomalies.append(Anomaly(
                code="NEW-HEAD-N",
                detail=f"unrecognized head number format {number!r}; not FIX-01/section",
                locator=f"{doc_id} {title[:40]}".strip(),
            ))

        nt = _num_tuple(number)
        if nt:
            # FIX-02a: orphan subsection — a dotted number whose top-level was never declared.
            if len(nt) == 1:
                declared_top.add(nt[0])
            else:
                if nt[0] not in declared_top:
                    result.anomalies.append(Anomaly(
                        code="FIX-02",
                        detail=f"subsection {number} appears but top-level {nt[0]} was "
                               f"never declared (dropped section-heading number)",
                        locator=f"{doc_id} {number}".strip(),
                    ))
            # FIX-02b: non-monotonic — number goes backwards in document order.
            if prev_tuple and nt < prev_tuple and nt[0] == prev_tuple[0]:
                result.anomalies.append(Anomaly(
                    code="FIX-02",
                    detail=f"non-monotonic heading sequence: {prev_tuple} -> {nt}",
                    locator=f"{doc_id} {number}".strip(),
                ))
            prev_tuple = nt

        numbered_heads.append((number, title))
        section = Section(
            number=number,
            title=title,
            text=body_text,
            depth=number.count(".") if number else 0,
            page=_first_page(head.get("coords", "")),
        )
        result.sections.append(section)
        last_section = section

    return result


def _first_page(coords: str) -> int | None:
    """Extract the 1-based page from a GROBID coords string "page,x,y,w,h". None if absent."""
    if not coords:
        return None
    try:
        return int(coords.split(";")[0].split(",")[0])
    except (ValueError, IndexError):
        return None
