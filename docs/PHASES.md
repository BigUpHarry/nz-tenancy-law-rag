# Build phases

What each phase does, why it exists, and what "done" means. Phases are ordered
so that every later phase can be measured by the harness built in Phase 5.

| Phase | Deliverable | Status |
|---|---|---|
| 0 | Repo scaffold, dependency floor, CLI skeleton | done |
| 1 | Corpus: five NZ instruments parsed into citable provisions | done |
| 2 | Chunking, embeddings, vector + lexical index | next |
| 3 | Retrieval and grounded answer generation with citations | pending |
| 4 | Gold eval set: 50+ questions with known answers | pending |
| 5 | Eval harness: accuracy, citation, hallucination, abstention | pending |
| 6 | Experiment matrix and results table | pending |
| 7 | README, failure analysis, CI | pending |

---

## Phase 0 — Scaffold

**What happens.** A `src/` layout package, a deliberately small dependency set,
and a CLI that grows a subcommand per phase.

**Why these choices.**

- *No LangChain or LlamaIndex.* Every retrieval and prompting decision is
  visible in this repo. A reviewer can read `retrieve.py` and know exactly what
  happened; they cannot do that through a framework abstraction. It also means
  the eval numbers are attributable to decisions I made, not to a framework
  default I never saw.
- *No PyTorch.* Embeddings come from Ollama over HTTP, so the dependency set is
  `numpy`, `requests`, `PyYAML`, `rich`. The repo installs in seconds on Python
  3.11–3.14 and needs no GPU wheel resolution.
- *Vector search in numpy.* At ~650 provisions a brute-force cosine scan over a
  dense matrix is sub-millisecond. Adding FAISS would buy nothing and cost
  reproducibility. This is a deliberate right-sizing, documented rather than
  hidden.

**Done when** `pip install -e .` works and `tenancy-rag --help` runs.

---

## Phase 1 — Corpus

**What happens.** Five instruments are downloaded from legislation.govt.nz as
reprint XML and parsed into one JSONL file of citable provisions.

```bash
tenancy-rag corpus fetch     # download XML -> data/raw/
tenancy-rag corpus build     # parse -> data/processed/provisions.jsonl
tenancy-rag corpus check     # the data-quality gate: 15 assertions
tenancy-rag corpus show s-18 # inspect what the parser produced
```

**The corpus.**

| Instrument | Provisions | As at | Contributes |
|---|---:|---|---|
| Residential Tenancies Act 1986 | 373 | 2025-12-01 | The operative statute |
| Residential Tenancies Amendment Act 2020 | 99 | 2020-08-11 | Decoy; staggered commencement |
| Healthy Homes Standards Regulations 2019 | 69 | 2025-09-25 | Numeric standards |
| Residential Tenancies Amendment Act 2024 | 60 | 2024-12-17 | Decoy; recent amendments |
| Smoke Alarms Regulations 2016 | 46 | 2025-07-02 | Alarm duties; revoked insulation Part |
| **total** | **647** | | 612,515 characters |

Of those 647: **435 operative**, **53 repealed or revoked**, **159 amending**
provisions that are text *about* the law rather than the law itself.

**Why this corpus and not a pile of PDFs.** Four properties that make
evaluation meaningful:

1. **The amendment Acts are retrieval decoys.** The Residential Tenancies
   Amendment Act 2024 s 8 reads "Replace section 18 with: General bonds — A
   landlord may require payment of a bond (a general bond) of no more than 4
   weeks' rent…". That is near-identical to the operative s 18 of the principal
   Act. A system that cites the amending instruction instead of the operative
   provision is wrong in a way that reads perfectly, and it cannot be measured
   unless the decoys are in the corpus. Both are present and tagged.
2. **The regulations carry numbers.** Heating capacity, insulation R-values,
   ventilation, smoke alarm placement. Numeric answers are scoreable exactly,
   rather than judged on prose similarity.
3. **Repealed and revoked provisions are retained.** 53 of them. A user asking
   about s 53B deserves to be told it was repealed on 30 January 2025, not to
   get a confident answer or silence.
4. **The documents disagree about "now".** Five reprints, five "as at" dates.
   That is a genuine reproducibility problem and the manifest treats it as one.

**Unit of retrieval: the provision.** The citation is the product. A tenancy
answer is only useful if it points at the exact provision, and the eval can
only score citations if every provision has one stable id. So the parser emits
one record per section / regulation / schedule clause, carrying:

```
key           act/1986/120/s-18
dlm_id        DLM95041
citation      Residential Tenancies Act 1986, s 18
url           https://www.legislation.govt.nz/act/public/1986/0120/latest/DLM95041.html
heading       General bonds
status        in_force          (or: repealed | revoked)
operative     true              (false for amending text and deleted provisions)
deleted_on    null              ("30 January 2025" where applicable)
as_at         2025-12-01        which reprint this text came from
text          (1) A landlord may require payment of a bond ...
```

`key` is what the eval compares. `citation` and `url` are what the user checks.
`operative` is what the retriever filters on.

### Eight ingestion traps, and what was done about them

This is the part worth reading. Every one of these fails *silently*: the parser
keeps running, the provision count looks healthy, and the output reads like
legislation.

**1. Repealed provisions stay in the reprint.** 28 sections of the Residential
Tenancies Act 1986 carry `deletion-status="repealed"`. Their `prov.body` is
empty but the label and heading survive, so a naive parser emits
"6 Long fixed-term tenancies" as retrievable law twenty-nine years after it was
repealed. They are kept — a user asking about s 6 deserves to be told it is
gone — but marked `status="repealed"`, excluded from the operative set, and
given the repeal date.

**2. Amendment history sits inside the provision.** Every provision carries a
`notes`/`history` block: *"Section 6: repealed, on 1 December 1996, by section
4(1) of the Residential Tenancies Amendment Act 1996"*. Unlike the equivalent
in UK legislation XML, these are a **sibling of `prov.body` inside the `prov`
element**, so flattening a provision pulls editorial annotation into the
statute text. Excluded from the text, and mined for metadata instead — the
repeal date is recorded nowhere else in the document.

**3. `prov` nests, but only in amendment Acts.** The principal Act has zero
nested provisions. The Amendment Act 2024 has 11 and the Amendment Act 2020 has
47, because an amending section that replaces a section quotes the whole
replacement. Taking every `prov` would have inflated the corpus by 58
provisions and minted citations to sections of the *wrong instrument*. Only
outermost `prov` elements are provisions.

**4. The amendment Acts are decoys.** See above. Tagged `doc_type="amendment"`
and `operative=false` so Phase 5 can measure a system that cites them.

**5. Invisible characters, in quantity.** The text carries **2,521 no-break
spaces (U+00A0)** and **762 zero-width no-break spaces (U+FEFF)** embedded
mid-sentence — `"1 December 1996"`, `"section 50(1)﻿(a)"`. They
defeat regex matching, lexical tokenisation and exact gold-answer comparison,
and **you cannot see them in the output**. This one bit during development: a
repeal-date regex that visibly should have matched scored 0 out of 28.

**6. The obvious fix for trap 5 corrupts te reo Māori.** The same text contains
macrons — `whānau`, `Rā` — across 11 provisions. The tempting one-liner,
NFKD-normalise and drop non-ASCII, would silently mangle them. Normalisation is
therefore surgical: nine named invisible characters are mapped or dropped and
every other character is left exactly as published. The quality gate asserts
both halves — zero invisibles *and* macrons still present.

**7. The five documents do not share an "as at" date.** They were last
reprinted on 2020-08-11, 2024-12-17, 2025-07-02, 2025-09-25 and 2025-12-01. A
single "corpus date" would be a fiction, so each document is pinned separately
and every provision records the reprint it came from. The manifest publishes
`as_at_range` rather than one date.

**8. Secondary legislation is "revoked", not "repealed".** This one was my own
error, caught only by the quality sweep. I censused `deletion-status` on the
principal Act, found `"repealed"`, and coded for it. Regulations use
`"revoked"` — the correct term for secondary legislation — so **25 of the 46
provisions of the Smoke Alarms Regulations were being silently dropped**,
including "Ceiling insulation required" and "Underfloor insulation required".
The provision count still looked plausible. The lesson generalised: the status
can also sit on a `part` or `subpart`, so deletion status is now inherited by
the provisions inside a deleted container, and the gate asserts that nothing
deleted is ever marked operative.

Two things that look like traps and are not, checked rather than assumed:

- **`<struckoutwords/>` is always self-closing.** It records the position where
  amended words were removed; the deleted text is already absent from the XML.
  It contributes nothing to the text, which the parser asserts rather than
  trusts.
- **"Prospective" appears 23 times but never marks a version.** All 23 are the
  defined terms *prospective landlord* and *prospective tenant*. NZ reprints
  contain only law in force at the reprint date, so there is no not-yet-in-force
  text to disentangle inside a reprint. The residual risk lives elsewhere: an
  amendment Act in the corpus may contain provisions not yet commenced, which
  is why amending text is never operative.

**Reproducibility.** `data/processed/manifest.json` records, per instrument:
source URL, byte count, SHA-256, the publisher's `date.as.at` and reprint date,
the title as the XML states it (to catch a silently wrong fetch), the amendment
Acts the reprint claims to incorporate, and the retrieval date.

**Done when** 647 provisions parse, `corpus check` passes all 15 assertions,
and `pytest` passes 33 parser tests against a fixture that encodes every trap
above.

---

## Phase 2 — Chunking, embeddings, index

**What happens.** Provisions become retrievable units, embedded once and cached.

**The decisions being made.**

- *Chunk boundary.* A provision is the natural unit, but 33 exceed 3,000
  characters and the longest is 18,901. Those are split on subsection
  boundaries rather than at a character offset, so no chunk straddles two
  subsections and every chunk keeps a precise citation.
- *Context prefix.* Each chunk is embedded with its citation and heading
  prepended. A bare subsection reads as "it does not apply in that case", which
  is unretrievable alone.
- *Operative filter.* The index is built over the 435 operative provisions by
  default, with the 212 others retrievable but flagged. Which default is right
  is an experiment in Phase 6, not an assumption: excluding them raises
  precision and makes "was s 53B repealed?" unanswerable.
- *Two indexes.* Dense vectors from `nomic-embed-text`, plus BM25 in pure
  Python. Legal queries carry rare exact tokens ("section 53B", "R-value",
  "pet bond") that dense retrieval blurs, so lexical retrieval is not a baseline
  to beat but a component to combine.
- *Embedding cache.* Keyed by model plus chunk hash, so re-running an experiment
  changes only what actually changed.

**Done when** the index builds from `provisions.jsonl` and a query returns
ranked chunks with citations.

## Phase 3 — Retrieval and generation

Retrieval modes: dense, BM25, and hybrid via reciprocal rank fusion, behind one
interface so Phase 6 can swap them by config. Generation prompts the model with
numbered, cited context and requires it to cite the provisions it relied on, or
to say it cannot answer from the supplied context. Abstention is a first-class
outcome: in this domain a confident wrong answer about a termination notice is
worse than no answer.

## Phase 4 — Gold eval set

50+ questions in YAML, each with the question, the provision keys that must be
retrieved, the expected answer, acceptable equivalents, and a category.
Categories target distinct failure modes, several of which exist only because
of what Phase 1 found:

- single-provision lookup
- cross-instrument questions (Act plus regulations)
- numeric answers (bond caps, R-values, heating capacity, notice periods)
- **repealed-provision questions** — "can I use s 53B?" The correct answer
  names the repeal, and there are 53 provisions to draw on
- **decoy questions** — answerable from the operative Act, where an amendment
  Act contains near-identical text. Scored on whether the citation is the
  operative provision
- **unanswerable questions**, where the correct response is abstention. Without
  this category a system that never abstains scores perfectly

## Phase 5 — Eval harness

Metrics, each computed per category:

- **Answer accuracy** — LLM judge against the gold answer, with a rubric and a
  hand-checked sample reporting judge agreement. A judge whose agreement with
  me is unmeasured is not evidence.
- **Citation precision / recall** — set comparison against gold provision keys.
- **Operative-citation rate** — of the citations given, how many point at
  operative law rather than an amending instruction or a repealed provision.
  This metric exists because trap 4 and trap 8 exist.
- **Groundedness** — does every claim trace to retrieved context? The
  hallucination rate, measured rather than asserted.
- **Abstention correctness** — abstained when it should, answered when it could.
- **Retrieval recall@k** — the ceiling on everything above. If the right
  provision is never retrieved, no prompt fixes it.
- Cost proxies: latency and token counts.

## Phase 6 — Experiment matrix

Each configuration runs the full question set; results go to a committed table.
Axes: chunking strategy, retrieval mode (dense / BM25 / hybrid), *k*, whether
non-operative provisions are indexed, and generation model. One axis moves at a
time, with the ablation that matters most reported first.

## Phase 7 — README and failure analysis

The README's most important section is where the system still fails, with named
examples and a diagnosis for each. Phases 1–6 exist to make that section honest
and specific.
