"""Tests for the legislation.govt.nz reprint parser.

The fixture is a miniature Act and a miniature set of regulations that between
them contain every trap documented in nzl.py, so a regression in any of them
fails here rather than silently degrading the corpus.

The invisible characters in the fixture are deliberate and load-bearing: they
are written as escapes so they survive editing, and they are the reason the
normalisation tests can assert anything at all.
"""

from __future__ import annotations

import pytest

from tenancy_rag.corpus.nzl import normalise, parse_document
from tenancy_rag.corpus.sources import Source

ACT = Source(
    doc_id="act/1999/1",
    title="Test Tenancies Act 1999",
    short="TTA 1999",
    doc_type="act",
    year=1999,
    number=1,
    path_kind="act",
    operative=True,
    why="fixture",
)

AMENDMENT = Source(
    doc_id="act/2024/9",
    title="Test Tenancies Amendment Act 2024",
    short="TTAA 2024",
    doc_type="amendment",
    year=2024,
    number=9,
    path_kind="act",
    operative=False,
    why="fixture decoy",
)

REGS = Source(
    doc_id="reg/2016/5",
    title="Test Tenancies (Smoke Alarms) Regulations 2016",
    short="TSAR 2016",
    doc_type="regulation",
    year=2016,
    number=5,
    path_kind="secondary",
    operative=True,
    why="fixture",
)

ACT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<act id="DLM1" date.as.at="2025-12-01" year="1999" act.no="1" act.type="public">
  <cover id="DLM2"><title>Test Tenancies Act 1999</title></cover>
  <contents><heading>Contents</heading><text>4 Bond limits</text></contents>
  <body>
    <part id="DLM3">
      <label>1</label><heading>Tenancy obligations</heading>
      <prov id="DLM10">
        <label denominator="yes">4</label>
        <heading>Bond limits</heading>
        <prov.body>
          <subprov>
            <label denominator="yes">1</label>
            <para><text>A landlord may require a bond of no more than 4 weeks’ rent
              payable under section 50(1)﻿(a).</text></para>
          </subprov>
          <subprov>
            <label denominator="yes">2</label>
            <para><text>Subsection (1) does not apply to a tenancy of a whare or
              other dwelling occupied by whānau.</text></para>
          </subprov>
        </prov.body>
        <notes><history><history-note id="H1">
          <amended-provision>Section 4(1)</amended-provision>:
          <amending-operation>amended</amending-operation>, on
          <amendment-date>1 July 2020</amendment-date>, by
          <amending-provision>section 9</amending-provision>.
        </history-note></history></notes>
      </prov>
      <prov id="DLM11" deletion-status="repealed">
        <label denominator="yes">6</label>
        <heading>Long fixed-term tenancies</heading>
        <prov.body/>
        <notes><history><history-note id="H2">
          <amended-provision>Section 6</amended-provision>:
          <amending-operation>repealed</amending-operation>, on
          <amendment-date>1 December 1996</amendment-date>, by
          <amending-provision>section 4(1)</amending-provision>.
        </history-note></history></notes>
      </prov>
    </part>
  </body>
  <schedule.group>
    <schedule id="DLM20">
      <label>1</label>
      <heading>Transitional provisions</heading>
      <schedule.provisions>
        <prov id="DLM21">
          <label denominator="yes">2</label>
          <heading>Existing tenancies</heading>
          <prov.body><para><text>An amendment applies to a tenancy whether it
            commenced before or after the amendment came into force.</text></para></prov.body>
        </prov>
      </schedule.provisions>
    </schedule>
  </schedule.group>
  <end><prov id="DLM30"><label>99</label><heading>Reprint notes</heading>
    <prov.body><para><text>This is editorial apparatus about the reprint itself and
      must not be ingested as a provision of the Act.</text></para></prov.body></prov></end>
</act>
"""

AMENDMENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<act id="LM1" date.as.at="2024-12-17" year="2024" act.no="9" act.type="public">
  <body>
    <prov id="LM10">
      <label denominator="yes">8</label>
      <heading>Section 18 replaced</heading>
      <prov.body>
        <para><text>Replace section 18 with:</text></para>
        <prov id="LM11">
          <label denominator="yes">18</label>
          <heading>General bonds</heading>
          <prov.body><para><text>A landlord may require payment of a bond of no
            more than 4 weeks rent lawfully payable under the tenancy.</text></para></prov.body>
        </prov>
      </prov.body>
    </prov>
  </body>
</act>
"""

REGS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<regulation id="LMS1" date.as.at="2025-07-02" year="2016" sr.no="5">
  <body>
    <prov id="LMS10">
      <label denominator="yes">7</label>
      <heading>Smoke alarms required</heading>
      <prov.body><para><text>A landlord must ensure that a smoke alarm is
        installed in the premises.</text></para></prov.body>
    </prov>
    <subpart id="LMS20" deletion-status="revoked">
      <label>2</label><heading>Insulation</heading>
      <prov id="LMS21">
        <label denominator="yes">11</label>
        <heading>Ceiling insulation required</heading>
        <prov.body/>
        <notes><history><history-note id="H9">
          <amended-provision>Regulation 11</amended-provision>:
          <amending-operation>revoked</amending-operation>, on
          <amendment-date>2 July 2025</amendment-date>, by
          <amending-provision>regulation 33</amending-provision>.
        </history-note></history></notes>
      </prov>
      <prov id="LMS22">
        <label denominator="yes">12</label>
        <heading>Qualifying ceiling insulation</heading>
        <prov.body/>
      </prov>
    </subpart>
  </body>
</regulation>
"""


@pytest.fixture(scope="module")
def act():
    return {p.provision_id: p for p in parse_document(ACT_XML.encode("utf-8"), ACT)}


@pytest.fixture(scope="module")
def amendment():
    return {
        p.provision_id: p
        for p in parse_document(AMENDMENT_XML.encode("utf-8"), AMENDMENT)
    }


@pytest.fixture(scope="module")
def regs():
    return {p.provision_id: p for p in parse_document(REGS_XML.encode("utf-8"), REGS)}


# -- trap 1: repealed provisions stay in the reprint ------------------------

def test_repealed_provision_is_kept_and_flagged(act):
    section_6 = act["s-6"]
    assert section_6.status == "repealed"
    assert section_6.operative is False
    assert "Long fixed-term tenancies" in section_6.text


def test_repealed_provision_records_its_date(act):
    assert act["s-6"].deleted_on == "1 December 1996"


def test_repealed_provision_is_not_mistaken_for_live_law(act):
    assert act["s-6"].text.startswith("[Repealed]")


# -- trap 2: amendment history is not law ----------------------------------

def test_history_note_is_excluded_from_in_force_text(act):
    text = act["s-4"].text
    assert "amended" not in text
    assert "1 July 2020" not in text
    assert "A landlord may require a bond" in text


def test_history_note_is_still_available_as_metadata(act):
    # The note is the only record of the date, so it must survive somewhere.
    assert act["s-6"].deletion_note is not None
    assert "repealed" in act["s-6"].deletion_note


# -- trap 3: prov nests only in amendment Acts ------------------------------

def test_quoted_replacement_section_is_not_a_separate_provision(amendment):
    assert "s-18" not in amendment
    assert set(amendment) == {"s-8"}


def test_amending_section_keeps_the_text_it_quotes(amendment):
    assert "Replace section 18 with" in amendment["s-8"].text
    assert "no more than 4 weeks rent" in amendment["s-8"].text


# -- trap 4: amendment Acts are decoys, tagged as such ---------------------

def test_amendment_text_is_marked_not_operative(amendment):
    assert amendment["s-8"].operative is False
    assert amendment["s-8"].doc_type == "amendment"


def test_operative_act_text_is_marked_operative(act):
    assert act["s-4"].operative is True


# -- trap 5: invisible characters -------------------------------------------

@pytest.mark.parametrize(
    "char", [" ", "﻿", "​", "­", " "]
)
def test_invisible_characters_are_normalised_away(act, char):
    assert all(char not in provision.text for provision in act.values())


def test_no_break_space_becomes_a_real_space(act):
    # "4 weeks" must become "4 weeks" or no tokeniser will ever match it.
    assert "4 weeks" in act["s-4"].text


def test_zero_width_space_is_removed_not_replaced(act):
    # "section 50(1)﻿(a)" must close up, not gain a space.
    assert "section 50(1)(a)" in act["s-4"].text


def test_normalise_is_idempotent():
    messy = "a b﻿c"
    assert normalise(normalise(messy)) == normalise(messy)


# -- trap 6: macrons are published text, not noise -------------------------

def test_macrons_are_preserved(act):
    assert "whānau" in act["s-4"].text


# -- trap 8: secondary legislation is "revoked", not "repealed" ------------

def test_revoked_regulation_is_kept(regs):
    assert "s-11" in regs
    assert regs["s-11"].status == "revoked"
    assert regs["s-11"].deleted_on == "2 July 2025"


def test_revoked_status_is_inherited_from_a_container(regs):
    # Regulation 12 carries no marker of its own; its subpart does.
    assert regs["s-12"].status == "revoked"
    assert regs["s-12"].operative is False


def test_live_regulation_is_unaffected(regs):
    assert regs["s-7"].status == "in_force"
    assert regs["s-7"].operative is True


# -- structure, citations, provenance --------------------------------------

def test_reprint_notes_are_not_ingested(act):
    assert "s-99" not in act
    assert all("editorial apparatus" not in p.text for p in act.values())


def test_contents_listing_is_not_ingested(act):
    assert all(p.heading != "Contents" for p in act.values())


def test_schedule_clause_is_namespaced_by_schedule(act):
    assert "sch-1-cl-2" in act
    clause = act["sch-1-cl-2"]
    assert clause.citation == "Test Tenancies Act 1999, sch 1 cl 2"
    assert clause.breadcrumb[0] == "1 Transitional provisions"


def test_schedule_clause_does_not_collide_with_a_section(act):
    # Section 4 and schedule 1 clause 2 must not share a key.
    assert act["sch-1-cl-2"].key != act["s-4"].key


def test_subsection_numbers_are_preserved(act):
    assert act["s-4"].text.startswith("(1) A landlord")
    assert "(2) Subsection (1) does not apply" in act["s-4"].text


def test_act_citation_style(act):
    assert act["s-4"].citation == "Test Tenancies Act 1999, s 4"


def test_regulation_citation_style(regs):
    assert regs["s-7"].citation.endswith(", reg 7")


def test_as_at_is_recorded_per_document(act, regs, amendment):
    assert act["s-4"].as_at == "2025-12-01"
    assert regs["s-7"].as_at == "2025-07-02"
    assert amendment["s-8"].as_at == "2024-12-17"


def test_act_provision_url_is_a_deep_link(act):
    assert act["s-4"].url.endswith("/act/public/1999/0001/latest/DLM10.html")


def test_regulation_provision_url_uses_a_fragment(regs):
    assert regs["s-7"].url.endswith("/2016/5/en/latest/#LMS10")


def test_keys_and_dlm_ids_are_unique(act):
    provisions = list(act.values())
    assert len({p.key for p in provisions}) == len(provisions)
    assert len({p.dlm_id for p in provisions}) == len(provisions)


def test_short_live_provisions_are_dropped():
    tiny = ACT_XML.replace(
        "A landlord may require a bond of no more than 4 weeks’ rent\n"
        "              payable under section 50(1)﻿(a).",
        "Repealed.",
    ).replace(
        "Subsection (1) does not apply to a tenancy of a whare or\n"
        "              other dwelling occupied by whānau.",
        "x",
    )
    ids = {p.provision_id for p in parse_document(tiny.encode("utf-8"), ACT)}
    assert "s-4" not in ids
