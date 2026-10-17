# NZ Tenancy Law RAG — with a real evaluation harness

Question answering over New Zealand residential tenancy law, built to be
**measured** rather than demoed. The chatbot is the easy part; the point of this
repo is the eval harness, the comparison table, and an honest account of where
retrieval still fails.

Runs entirely locally on [Ollama](https://ollama.com) — no API keys, no cost.

> **Status: Phase 1 of 7 complete.** Corpus ingestion is done, tested and gated.
> Retrieval, generation, the eval harness and the results table are in progress.
> See [docs/PHASES.md](docs/PHASES.md) for the full build plan.

---

## What this is

| | |
|---|---|
| **Corpus** | 647 citable provisions across 5 instruments (612k chars), from legislation.govt.nz |
| **Retrieval** | Dense (`nomic-embed-text`) + BM25 + hybrid RRF, hand-written in numpy |
| **Generation** | `qwen3:8b` via Ollama, required to cite provisions or abstain |
| **Evaluation** | 50+ gold questions; accuracy, citation precision/recall, groundedness, abstention |
| **Data quality** | 15 assertions gating the corpus, plus 33 parser tests |
| **Dependencies** | `numpy`, `requests`, `PyYAML`, `rich`. No LangChain, no PyTorch |

Every answer cites the provision it relied on, with a deep link to the exact
section on legislation.govt.nz.

## Quickstart

```bash
git clone https://github.com/your-username/nz-tenancy-rag-evals
cd nz-tenancy-rag-evals
python -m venv .venv && . .venv/Scripts/activate   # or: source .venv/bin/activate
pip install -e .
```

You need Ollama running with two models:

```bash
ollama pull nomic-embed-text
ollama pull qwen3:8b
```

Then build the corpus:

```bash
tenancy-rag corpus fetch     # ~1.9 MB of reprint XML from legislation.govt.nz
tenancy-rag corpus build     # -> data/processed/provisions.jsonl
tenancy-rag corpus check     # the data-quality gate: 15 assertions
tenancy-rag corpus show s-18
```

## The corpus

| Instrument | Provisions | As at | Contributes |
|---|---:|---|---|
| Residential Tenancies Act 1986 | 373 | 2025-12-01 | The operative statute |
| Residential Tenancies Amendment Act 2020 | 99 | 2020-08-11 | Decoy; staggered commencement |
| Residential Tenancies (Healthy Homes Standards) Regulations 2019 | 69 | 2025-09-25 | Heating, insulation, ventilation |
| Residential Tenancies Amendment Act 2024 | 60 | 2024-12-17 | Decoy; recent amendments |
| Residential Tenancies (Smoke Alarms) Regulations 2016 | 46 | 2025-07-02 | Alarm duties |

Of those 647 provisions: **435 operative**, **53 repealed or revoked**, and
**159 amending** provisions that are text *about* the law rather than the law
itself.

Chosen because the amendment Acts quote the sections they replace almost
verbatim (so citing the wrong one is a measurable error), because the
regulations carry exact numbers (so answers are scoreable, not judged on
vibes), and because 53 provisions are no longer in force (so "this was
repealed" is a correct answer the system has to be able to give).

`data/processed/manifest.json` pins the snapshot: per-instrument SHA-256, byte
count, the publisher's `date.as.at`, and the amendment Acts each reprint claims
to incorporate.

## Notes from building the ingestion

Eight things in legislation.govt.nz's reprint XML break naive parsing. All eight
fail *silently* — the parser keeps running, the provision count looks healthy,
and the output reads like legislation.

1. **Repealed provisions stay in the reprint.** 28 sections of the Act have an
   empty body but a surviving heading, so a naive parser serves
   "6 Long fixed-term tenancies" as live law 29 years after its repeal.
2. **Amendment history sits *inside* the provision**, as a sibling of the body.
   Flattening a provision pulls *"Section 6: repealed, on 1 December 1996, by
   section 4(1)…"* into the statute text.
3. **`prov` nests, but only in amendment Acts** — 58 nested provisions across
   the two, because an amending section quotes the whole replacement section.
4. **The amendment Acts are retrieval decoys.** `RTAA 2024 s 8` is "Replace
   section 18 with: *General bonds* — A landlord may require payment of a bond
   (a general bond) of no more than 4 weeks' rent…", near-identical to the
   operative `RTA 1986 s 18`.
5. **2,521 no-break spaces and 762 zero-width no-break spaces** are embedded
   mid-sentence — `"1 December 1996"`, `"section 50(1)﻿(a)"`. They
   break tokenisation, regexes and exact answer matching, and you cannot see
   them. A repeal-date regex that visibly should have matched scored 0/28.
6. **The obvious fix for (5) corrupts te reo Māori.** The same text contains
   `whānau` and `Rā`; NFKD-normalising and dropping non-ASCII would mangle them.
   Normalisation is surgical, and the gate asserts both zero invisibles *and*
   macrons still present.
7. **The five documents don't share an "as at" date** — five reprints, five
   dates. A single "corpus date" would be a fiction, so each is pinned
   separately.
8. **Secondary legislation is "revoked", not "repealed".** My own error: I
   censused the status attribute on the Act only. **25 of the 46 Smoke Alarms
   provisions were being silently dropped**, including "Ceiling insulation
   required". Status can also sit on a `part`, so it is now inherited.

Full detail, including two things that look like traps and are not, in
[docs/PHASES.md](docs/PHASES.md#eight-ingestion-traps-and-what-was-done-about-them).

## Results

_Phase 6. The comparison table across chunking strategies, retrieval modes and
models goes here._

## Where it still fails

_Phase 7. Named failure cases with diagnoses, not a disclaimer._

## Development

```bash
pytest                      # 33 parser tests against a fixture encoding every trap
pytest --cov=src --cov-report=term-missing
tenancy-rag corpus check    # data-quality gate over the real corpus
```

## Licence and attribution

Code: MIT.

Legislation text is sourced from [legislation.govt.nz](https://www.legislation.govt.nz),
published by the New Zealand Parliamentary Counsel Office. Crown copyright
material is reproduced under the
[Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/),
in accordance with section 27 of the Legislation Act 2019 and the PCO's
copyright statement. The source material has been reformatted and restructured
for machine retrieval; **this repo is not an official version of New Zealand
legislation**, and official versions are available free of charge at
legislation.govt.nz.

**This is not legal advice.** It is an engineering demonstration of retrieval
and evaluation. The corpus is a set of point-in-time snapshots, the model is an
8B local model, and the system is wrong often enough that the README has a
section about it. For advice on a tenancy, see
[Tenancy Services](https://www.tenancy.govt.nz).
