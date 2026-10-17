"""Data-quality gate for the built corpus.

Every check here corresponds to a trap that was actually found while building
the ingestion, and each one failed silently when it was live: the parser ran,
the provision count looked healthy, and the output read like legislation. The
unit tests prove the parser handles a fixture containing each trap; these
checks prove the real corpus is still clean after a re-fetch, when the
publisher may have changed the documents underneath us.

Run via `tenancy-rag corpus check`. Exits non-zero on any failure, so it can
gate CI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Characters that must never survive normalisation.
INVISIBLES = " ﻿​‌‍­   "

# Macron-bearing vowels used in te reo Maori. Their presence proves that
# normalisation did not ASCII-fold the text.
MACRONS = "āēīōūĀĒĪŌŪ"

# Prose that only appears in editorial amendment notes, never in enacted text.
_NOTE_PROSE = re.compile(
    r"(?:amended|inserted|replaced|repealed|revoked),\s+on\s+\d{1,2}\s+\w+\s+\d{4}"
)

# A provision number run into the first word of its text, e.g. "31For the...".
_GLUED_NUMBER = re.compile(r"^\d+[A-Z][a-z]")


@dataclass
class Check:
    name: str
    passed: bool
    detail: str

    @property
    def symbol(self) -> str:
        return "PASS" if self.passed else "FAIL"


def _examples(keys: list[str], limit: int = 3) -> str:
    shown = ", ".join(keys[:limit])
    extra = f" (+{len(keys) - limit} more)" if len(keys) > limit else ""
    return shown + extra


def run_checks(provisions: list[dict]) -> list[Check]:
    checks: list[Check] = []

    def add(name: str, offenders: list[str], detail_ok: str) -> None:
        checks.append(
            Check(
                name=name,
                passed=not offenders,
                detail=detail_ok if not offenders else _examples(offenders),
            )
        )

    total = len(provisions)
    checks.append(
        Check("corpus is non-empty", total > 0, f"{total} provisions")
    )

    # Identity
    keys = [p["key"] for p in provisions]
    checks.append(
        Check(
            "provision keys are unique",
            len(set(keys)) == total,
            f"{len(set(keys))} distinct keys",
        )
    )
    dlm_ids = [p["dlm_id"] for p in provisions if p["dlm_id"]]
    checks.append(
        Check(
            "publisher ids are unique",
            len(set(dlm_ids)) == len(dlm_ids),
            f"{len(set(dlm_ids))} distinct ids",
        )
    )

    # Trap 5: invisible characters
    add(
        "no invisible characters in text",
        [p["key"] for p in provisions if any(c in p["text"] for c in INVISIBLES)],
        "0 occurrences of U+00A0 / U+FEFF / zero-width",
    )

    # Trap 6: macrons survived
    with_macrons = [p["key"] for p in provisions if any(c in p["text"] for c in MACRONS)]
    checks.append(
        Check(
            "te reo Maori macrons preserved",
            len(with_macrons) > 0,
            f"{len(with_macrons)} provisions retain macrons",
        )
    )

    # Trap 2: editorial annotation kept out of in-force text
    add(
        "no amendment-note prose in in-force text",
        [
            p["key"]
            for p in provisions
            if p["status"] == "in_force" and _NOTE_PROSE.search(p["text"])
        ],
        "0 contaminated provisions",
    )

    # Traps 1 and 8: deleted provisions are flagged and dated
    deleted = [p for p in provisions if p["status"] in ("repealed", "revoked")]
    checks.append(
        Check(
            "repealed and revoked provisions are retained",
            len(deleted) > 0,
            f"{len(deleted)} deleted provisions kept and flagged",
        )
    )
    add(
        "every deleted provision has a date",
        [p["key"] for p in deleted if not p["deleted_on"]],
        f"{len(deleted)}/{len(deleted)} dated",
    )
    add(
        "no deleted provision is marked operative",
        [p["key"] for p in deleted if p["operative"]],
        "0 deleted provisions in the operative set",
    )

    # Trap 4: amendment text is never operative
    add(
        "amendment-Act text is marked not operative",
        [p["key"] for p in provisions if p["doc_type"] == "amendment" and p["operative"]],
        "0 amending provisions in the operative set",
    )

    # Numbering integrity
    add(
        "no provision number glued to its first word",
        [p["key"] for p in provisions if _GLUED_NUMBER.match(p["text"])],
        "0 glued numbers",
    )
    add(
        "no empty numbering artefacts",
        [p["key"] for p in provisions if "()" in p["text"]],
        "0 empty parentheses",
    )

    # Citability: the whole point of the corpus
    add(
        "every provision has a citation and a URL",
        [p["key"] for p in provisions if not p["citation"] or not p["url"]],
        "all provisions citable",
    )
    add(
        "every provision records its reprint date",
        [p["key"] for p in provisions if not p["as_at"]],
        "all provisions carry date.as.at",
    )
    add(
        "no provision is empty",
        [p["key"] for p in provisions if not p["text"].strip()],
        "no empty text",
    )

    return checks
