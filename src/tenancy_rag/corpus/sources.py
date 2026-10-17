"""The corpus: the statutes and regulations that govern a New Zealand tenancy.

Chosen deliberately, not for convenience:

* The Residential Tenancies Act 1986 is the operative statute, and the
  consolidated reprint already folds in every commenced amendment. The two
  amendment Acts are included anyway, because they are *retrieval decoys*: the
  Residential Tenancies Amendment Act 2024 contains the full text of the new
  section 18 under the heading "Replace section 18 with", which embeds almost
  verbatim alongside the operative section 18 in the principal Act. A system
  that cites the amending instruction instead of the operative provision is
  wrong in a way that looks right, and it cannot be measured unless the decoys
  are in the corpus.
* The Healthy Homes Standards regulations carry the numeric obligations people
  actually ask about (heating capacity, insulation R-values, ventilation), so
  the eval can score exact figures rather than prose.
* Every document is a point-in-time reprint with its own "as at" date. They do
  not share one date, which is why the manifest pins each document separately.

Source: legislation.govt.nz. Crown copyright, reproduced under the
Creative Commons Attribution 4.0 International licence (see README).
"""

from __future__ import annotations

from dataclasses import dataclass

SITE = "https://www.legislation.govt.nz"


@dataclass(frozen=True)
class Source:
    doc_id: str          # our stable key prefix, e.g. "act/1986/120"
    title: str           # full official title
    short: str           # compact label used in citations and results tables
    doc_type: str        # "act" | "regulation" | "amendment"
    year: int
    number: int
    path_kind: str       # "act" | "secondary" -- decides the URL shape
    operative: bool      # False for amendment Acts: text amends, it does not apply
    why: str

    # -- URLs ---------------------------------------------------------------
    # legislation.govt.nz serves primary and secondary legislation from two
    # different path shapes, and neither is guessable from the other.

    @property
    def _xml_base(self) -> str:
        if self.path_kind == "act":
            return f"{SITE}/act/public/{self.year}/{self.number}"
        return f"{SITE}/secondary-legislation/pco-drafted/{self.year}/{self.number}"

    @property
    def xml_url(self) -> str:
        """The current reprint as XML. Its date.as.at attribute is the pin."""
        return f"{self._xml_base}/en/latest.xml"

    @property
    def html_url(self) -> str:
        """Human-browsable whole document."""
        if self.path_kind == "act":
            return f"{SITE}/act/public/{self.year}/{self.number:04d}/latest/whole.html"
        return (
            f"{SITE}/regulation/public/{self.year}/{self.number:04d}/latest/whole.html"
        )

    def provision_url(self, dlm_id: str) -> str:
        """Deep link to one provision.

        Acts address a provision as its own page; secondary legislation only
        offers a fragment on the whole-document page.
        """
        if not dlm_id:
            return self.html_url
        if self.path_kind == "act":
            return (
                f"{SITE}/act/public/{self.year}/{self.number:04d}"
                f"/latest/{dlm_id}.html"
            )
        return f"{self._xml_base}/en/latest/#{dlm_id}"

    @property
    def filename(self) -> str:
        return self.doc_id.replace("/", "_") + ".xml"


SOURCES: tuple[Source, ...] = (
    Source(
        doc_id="act/1986/120",
        title="Residential Tenancies Act 1986",
        short="RTA 1986",
        doc_type="act",
        year=1986,
        number=120,
        path_kind="act",
        operative=True,
        why="The operative statute: tenancy obligations, bonds, termination, Tribunal.",
    ),
    Source(
        doc_id="reg/2019/88",
        title="Residential Tenancies (Healthy Homes Standards) Regulations 2019",
        short="HHS 2019",
        doc_type="regulation",
        year=2019,
        number=88,
        path_kind="secondary",
        operative=True,
        why="Numeric standards: heating, insulation, ventilation, moisture, draughts.",
    ),
    Source(
        doc_id="reg/2016/128",
        title="Residential Tenancies (Smoke Alarms) Regulations 2016",
        short="SAR 2016",
        doc_type="regulation",
        year=2016,
        number=128,
        path_kind="secondary",
        operative=True,
        why="Smoke alarm type, placement and maintenance duties.",
    ),
    Source(
        doc_id="act/2024/52",
        title="Residential Tenancies Amendment Act 2024",
        short="RTAA 2024",
        doc_type="amendment",
        year=2024,
        number=52,
        path_kind="act",
        operative=False,
        why="Recent amendments, and a retrieval decoy: it quotes whole new sections.",
    ),
    Source(
        doc_id="act/2020/59",
        title="Residential Tenancies Amendment Act 2020",
        short="RTAA 2020",
        doc_type="amendment",
        year=2020,
        number=59,
        path_kind="act",
        operative=False,
        why="Earlier amendment wave; a second decoy with staggered commencement.",
    ),
)

BY_DOC_ID = {source.doc_id: source for source in SOURCES}
BY_SHORT = {source.short: source for source in SOURCES}

OPERATIVE_DOC_IDS = frozenset(s.doc_id for s in SOURCES if s.operative)
