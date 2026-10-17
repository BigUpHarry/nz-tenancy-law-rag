"""Parse legislation.govt.nz reprint XML into citable provisions.

The schema is pleasantly simple -- no namespaces, and `prov` is the universal
unit for sections, regulations and schedule clauses alike. The hard part is not
the structure, it is knowing which text is *law*. Six traps, each of which fails
silently: the parser keeps running and the output still looks like legislation.

1. Repealed provisions stay in the reprint. 28 sections of the Residential
   Tenancies Act 1986 carry deletion-status="repealed". Their prov.body is
   empty, but the label and heading survive, so a naive parser emits
   "6 Long fixed-term tenancies" as retrievable law twenty-nine years after it
   was repealed. These are kept -- a user asking about section 6 deserves to be
   told it is gone -- but marked status="repealed" and excluded from the
   operative index.

2. Amendment history is not law. Every provision carries a `notes`/`history`
   block ("Section 6: repealed, on 1 December 1996, by section 4(1) of ...").
   Unlike the UK's equivalent, these sit *inside* the provision as a sibling of
   prov.body, so flattening a provision pulls editorial annotation into the
   statute text. They are excluded from the text and mined for metadata
   instead: the repeal date comes from the note, because it is recorded nowhere
   else in the document.

3. `prov` nests, but only in amendment Acts. The principal Act has no nested
   provisions; the Residential Tenancies Amendment Act 2024 has eleven, because
   an amending section that replaces a section quotes the whole replacement.
   Only outermost `prov` elements are provisions.

4. Amendment Acts are retrieval decoys. "Replace section 18 with: 18 General
   bonds (1) A landlord may require payment of a bond ..." is near-identical to
   the operative section 18 of the principal Act. Both are kept, and tagged, so
   the eval can detect a system that cites the instruction instead of the law.

5. Invisible characters. The text carries 2,521 no-break spaces (U+00A0) and
   762 zero-width no-break spaces (U+FEFF) embedded mid-sentence, as in
   "section 50(1)﻿(a)" and "1 December 1996". They defeat regex
   matching, lexical tokenisation and exact gold-answer comparison, and you
   cannot see them in the output. They are normalised away.

6. Macrons are not noise. The same text contains te reo Maori with macrons
   (a, o, u with U+0101, U+014D, U+016B). The obvious fix for trap 5 --
   NFKD-normalise and drop non-ASCII -- would corrupt those words. So
   normalisation is surgical: named invisible characters are mapped or dropped
   and everything else is left exactly as published.

Each document is a point-in-time reprint, so every provision records the
`date.as.at` it came from. The five documents do not share one date.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Iterator

from .sources import Source

# Editorial apparatus that must never become statute text.
SKIP_TAGS = frozenset(
    {
        "notes",
        "history",
        "history-note",
        "amendment-date",
        "amending-leg",
        "amending-provision",
        "amended-provision",
        "amending-operation",
        "editorial-note",
        "reprint.amend",
        "cf",
        # Empty position markers left where amended words were removed. The
        # deleted text is already absent from the XML; the tag only records
        # that a deletion happened here.
        "struckoutwords",
    }
)

# Container tags walked through when looking for provisions.
CONTAINER_TAGS = frozenset(
    {"body", "schedule.group", "schedule", "schedule.provisions", "part", "subpart",
     "crosshead", "subprov.crosshead", "prov.group", "front"}
)

MIN_CHARS = 40  # below this a provision is a stub, not usable context

# Trap 8: primary legislation is "repealed", secondary legislation is
# "revoked". They are the same structural situation -- an emptied provision
# whose label and heading survive -- and nothing but this attribute marks it.
# Checking only for "repealed" silently drops 25 of the 46 provisions of the
# Smoke Alarms regulations, including "Ceiling insulation required".
DELETED_STATUSES = frozenset({"repealed", "revoked"})

# Containers whose deletion status is inherited by the provisions inside them:
# a revoked Part does not re-mark each of its regulations.
INHERITING_TAGS = frozenset({"part", "subpart", "schedule", "crosshead"})

# Trap 5/6: surgical normalisation. Keys are the characters to replace; anything
# not named here -- macrons included -- is published text and is left alone.
_INVISIBLES = {
    " ": " ",   # no-break space
    " ": " ",   # figure space
    " ": " ",   # thin space
    " ": " ",   # narrow no-break space
    "﻿": "",    # zero-width no-break space / BOM, found mid-sentence
    "​": "",    # zero-width space
    "‌": "",    # zero-width non-joiner
    "‍": "",    # zero-width joiner
    "­": "",    # soft hyphen
}
_INVISIBLE_RE = re.compile("|".join(map(re.escape, _INVISIBLES)))

_WS = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")

# Whitespace *inside* a text element is source formatting, never meaning. The
# published XML happens to be unwrapped, but collapsing here means a wrapped
# source cannot inject a line break into the middle of a sentence and quietly
# split a chunk.
_INLINE_WS = re.compile(r"\s+")



def normalise(text: str) -> str:
    """Map invisible characters out of published text, preserving everything else."""
    return _INVISIBLE_RE.sub(lambda match: _INVISIBLES[match.group(0)], text)


@dataclass
class Provision:
    """One citable unit of New Zealand legislation."""

    doc_id: str                 # "act/1986/120"
    title: str                  # "Residential Tenancies Act 1986"
    short: str                  # "RTA 1986"
    doc_type: str               # "act" | "regulation" | "amendment"
    provision_id: str           # "s-13A" | "sch-1-cl-2"
    dlm_id: str                 # publisher identifier, e.g. "DLM95011"
    citation: str               # "Residential Tenancies Act 1986, s 13A"
    short_citation: str         # "RTA 1986, s 13A"
    label: str                  # "13A"
    heading: str                # "Landlord's responsibilities"
    status: str = "in_force"    # "in_force" | "repealed" | "revoked"
    operative: bool = True      # False for amendment-Act text
    deleted_on: str | None = None   # date the provision ceased to have effect
    deletion_note: str | None = None
    as_at: str | None = None    # the reprint this text was taken from
    breadcrumb: list[str] = field(default_factory=list)
    text: str = ""
    url: str = ""

    @property
    def key(self) -> str:
        """Globally unique, stable identifier. This is what the eval compares."""
        return self.doc_id + "/" + self.provision_id

    @property
    def n_chars(self) -> int:
        return len(self.text)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "doc_id": self.doc_id,
            "title": self.title,
            "short": self.short,
            "doc_type": self.doc_type,
            "provision_id": self.provision_id,
            "dlm_id": self.dlm_id,
            "citation": self.citation,
            "short_citation": self.short_citation,
            "label": self.label,
            "heading": self.heading,
            "status": self.status,
            "operative": self.operative,
            "deleted_on": self.deleted_on,
            "deletion_note": self.deletion_note,
            "as_at": self.as_at,
            "breadcrumb": self.breadcrumb,
            "text": self.text,
            "url": self.url,
            "n_chars": self.n_chars,
        }


# --------------------------------------------------------------------------
# text extraction
# --------------------------------------------------------------------------

def _inline_text(element: ET.Element) -> str:
    """Flatten an inline element, dropping editorial apparatus."""
    chunks: list[str] = []
    if element.text:
        chunks.append(element.text)
    for child in element:
        if child.tag not in SKIP_TAGS:
            chunks.append(_inline_text(child))
        if child.tail:
            chunks.append(child.tail)
    return "".join(chunks)


def _inline(element: ET.Element) -> str:
    """Flatten an inline element to a single clean line."""
    return _INLINE_WS.sub(" ", normalise(_inline_text(element))).strip()


def _render(element: ET.Element, out: list[str], depth: int = 0) -> None:
    """Walk a provision body, re-emitting numbering as readable markers.

    The XML stores a subsection's number in a sibling `label` element, so a
    plain flatten produces "1A landlord must..." -- the number collides with
    the first word, which both reads badly and prevents the model from citing a
    subsection. Numbers are re-emitted as "(1)" instead.
    """
    for child in element:
        tag = child.tag
        if tag in SKIP_TAGS:
            continue

        if tag == "label":
            number = _inline(child)
            if number:
                out.append("\n" + "  " * max(0, depth - 1) + f"({number}) ")
        elif tag == "text":
            out.append(_inline(child) + " ")
        elif tag == "heading":
            heading = _inline(child)
            if heading:
                out.append("\n" + heading + "\n")
        elif tag == "entry":
            out.append(_inline(child) + " | ")
        elif tag == "row":
            _render(child, out, depth)
            out.append("\n")
        elif tag in ("subprov", "label-para", "def-para"):
            _render(child, out, depth + 1)
        else:
            _render(child, out, depth)


def _clean(text: str) -> str:
    text = normalise(text)
    text = _WS.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = _BLANKS.sub("\n\n", text)
    # A label immediately followed by a newline is an empty numbering artefact.
    text = re.sub(r"\(\s*\)\s*", "", text)
    return text.strip()


# --------------------------------------------------------------------------
# provision discovery
# --------------------------------------------------------------------------

def _iter_provisions(element: ET.Element) -> Iterator[ET.Element]:
    """Yield outermost `prov` elements only (trap 3)."""
    for child in element:
        if child.tag in SKIP_TAGS:
            continue
        if child.tag == "prov":
            yield child          # outermost: do not descend
            continue
        yield from _iter_provisions(child)


def _child_text(element: ET.Element, tag: str) -> str:
    found = element.find(tag)
    if found is None:
        return ""
    return _inline(found)


def _raw_flatten(element: ET.Element) -> str:
    """Concatenate a subtree in document order, keeping tails in place.

    Needed because `notes` is in SKIP_TAGS, so the ordinary flatteners refuse
    to look inside it. Concatenating rather than joining matters: the note's
    punctuation lives in the tails ("Section 53B" + ": " + "repealed" + ", on "),
    so joining with spaces yields "Section 53B : repealed , on".
    """
    chunks: list[str] = []
    if element.text:
        chunks.append(element.text)
    for child in element:
        chunks.append(_raw_flatten(child))
        if child.tail:
            chunks.append(child.tail)
    return "".join(chunks)


def _notes_text(element: ET.Element) -> str:
    """The editorial note block, read for metadata but kept out of the text."""
    notes = element.find("notes")
    if notes is None:
        return ""
    return _INLINE_WS.sub(" ", normalise(_raw_flatten(notes))).strip()


def _own_status(element: ET.Element) -> str | None:
    status = element.get("deletion-status")
    return status if status in DELETED_STATUSES else None


def _deletion_date(element: ET.Element, status: str) -> str | None:
    """The date the provision ceased to have effect.

    Read from the structured history note rather than its prose. The note
    renders as "Regulation 11: revoked, on 2 July 2025 ... by regulation 33",
    but the pieces are real elements -- amending-operation, amendment-date --
    so there is no reason to regex the sentence back apart. A note may list
    several operations over the provision's life, so the one matching this
    provision's final status is the one that matters.
    """
    notes = element.find("notes")
    if notes is None:
        return None

    fallback: str | None = None
    for note in notes.iter("history-note"):
        operation = note.find("amending-operation")
        when = note.find("amendment-date")
        if when is None:
            continue
        date_text = _inline(when)
        if operation is not None:
            operation_text = _inline_text(operation).strip().lower()
            if operation_text == status:
                return date_text
        fallback = fallback or date_text
    return fallback


def _provision_id(label: str, schedule_label: str, index: int) -> str:
    """A readable, stable id. Schedule clauses are namespaced by schedule."""
    slug = re.sub(r"[^0-9A-Za-z]+", "", label) or f"n{index}"
    if schedule_label:
        sched = re.sub(r"[^0-9A-Za-z]+", "", schedule_label) or "x"
        return f"sch-{sched}-cl-{slug}"
    return f"s-{slug}"


def _citation_suffix(label: str, schedule_label: str, doc_type: str) -> str:
    if schedule_label:
        return f"sch {schedule_label} cl {label}"
    # New Zealand drafting style: "s 13A" for Acts, "reg 4" for regulations.
    return (f"reg {label}" if doc_type == "regulation" else f"s {label}")


def _walk_containers(
    element: ET.Element,
    breadcrumb: tuple[str, ...] = (),
    schedule_label: str = "",
    inherited_status: str | None = None,
) -> Iterator[tuple[ET.Element, tuple[str, ...], str, str | None]]:
    """Descend containers, tracking Part/Schedule context and deletion status."""
    for child in element:
        if child.tag in SKIP_TAGS:
            continue
        if child.tag == "prov":
            yield child, breadcrumb, schedule_label, inherited_status
            continue

        trail = breadcrumb
        sched = schedule_label
        status = inherited_status
        if child.tag in INHERITING_TAGS:
            status = _own_status(child) or inherited_status

        if child.tag == "schedule":
            label = _child_text(child, "label")
            heading = _child_text(child, "heading")
            sched = label or heading or schedule_label
            trail = breadcrumb + (" ".join(p for p in (label, heading) if p),)
        elif child.tag in ("part", "subpart"):
            label = _child_text(child, "label")
            heading = _child_text(child, "heading")
            joined = " ".join(p for p in (label, heading) if p)
            if joined:
                trail = breadcrumb + (joined,)
        yield from _walk_containers(child, trail, sched, status)


def parse_document(xml_bytes: bytes, source: Source) -> list[Provision]:
    root = ET.fromstring(xml_bytes)
    as_at = root.get("date.as.at")

    provisions: list[Provision] = []
    seen: set[str] = set()

    # Only the operative containers: `contents` and `cover` restate headings,
    # and `end` holds the reprint notes.
    containers = [
        child
        for child in root
        if child.tag in ("body", "schedule.group", "front")
    ]

    index = 0
    for container in containers:
        for element, breadcrumb, schedule_label, inherited in _walk_containers(
            container
        ):
            index += 1
            label = _child_text(element, "label")
            heading = _child_text(element, "heading")
            notes = _notes_text(element)
            status = _own_status(element) or inherited

            body = element.find("prov.body")
            out: list[str] = []
            if body is not None:
                _render(body, out)
            text = _clean("".join(out))

            if status:
                # Traps 1 and 8: the body is empty, so the note is the only
                # content -- and it is exactly what a user asking about this
                # provision needs to be told.
                text = f"[{status.title()}] {heading}".strip()
                if notes:
                    text = f"{text}\n\n{notes}"
            elif len(text) < MIN_CHARS:
                continue

            provision_id = _provision_id(label, schedule_label, index)
            if provision_id in seen:
                provision_id = f"{provision_id}-{index}"
            seen.add(provision_id)

            suffix = _citation_suffix(
                label or provision_id, schedule_label, source.doc_type
            )

            provisions.append(
                Provision(
                    doc_id=source.doc_id,
                    title=source.title,
                    short=source.short,
                    doc_type=source.doc_type,
                    provision_id=provision_id,
                    dlm_id=element.get("id") or "",
                    citation=f"{source.title}, {suffix}",
                    short_citation=f"{source.short}, {suffix}",
                    label=label,
                    heading=heading,
                    status=status or "in_force",
                    operative=source.operative and not status,
                    deleted_on=_deletion_date(element, status) if status else None,
                    deletion_note=notes if status else None,
                    as_at=as_at,
                    breadcrumb=[part for part in breadcrumb if part],
                    text=text,
                    url=source.provision_url(element.get("id") or ""),
                )
            )
    return provisions
