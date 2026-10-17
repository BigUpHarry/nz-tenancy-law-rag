"""Turn the downloaded reprints into one JSONL file of citable provisions."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..config import CORPUS_MANIFEST_PATH, PROVISIONS_PATH, RAW_DIR, ensure_dirs
from .fetch import fetch_all, write_manifest
from .nzl import Provision, parse_document
from .sources import SOURCES


@dataclass(frozen=True)
class CorpusStats:
    provisions: int
    total_chars: int
    by_doc: dict[str, int]
    by_status: dict[str, int]
    operative: int
    decoy: int
    repealed: int
    median_chars: int
    p95_chars: int
    max_chars: int
    empty_headings: int
    as_at_range: list[str]

    def as_dict(self) -> dict:
        return {
            "provisions": self.provisions,
            "total_chars": self.total_chars,
            "by_doc": self.by_doc,
            "by_status": self.by_status,
            "operative": self.operative,
            "amendment_decoys": self.decoy,
            "repealed": self.repealed,
            "median_chars": self.median_chars,
            "p95_chars": self.p95_chars,
            "max_chars": self.max_chars,
            "empty_headings": self.empty_headings,
            "as_at_range": self.as_at_range,
        }


def _percentile(sorted_values: list[int], fraction: float) -> int:
    if not sorted_values:
        return 0
    index = min(len(sorted_values) - 1, int(fraction * len(sorted_values)))
    return sorted_values[index]


def summarise(provisions: list[Provision]) -> CorpusStats:
    lengths = sorted(provision.n_chars for provision in provisions)
    return CorpusStats(
        provisions=len(provisions),
        total_chars=sum(lengths),
        by_doc=dict(sorted(Counter(p.short for p in provisions).items())),
        by_status=dict(sorted(Counter(p.status for p in provisions).items())),
        operative=sum(1 for p in provisions if p.operative),
        decoy=sum(1 for p in provisions if p.doc_type == "amendment"),
        repealed=sum(1 for p in provisions if p.status in ("repealed", "revoked")),
        median_chars=_percentile(lengths, 0.5),
        p95_chars=_percentile(lengths, 0.95),
        max_chars=lengths[-1] if lengths else 0,
        empty_headings=sum(1 for p in provisions if not p.heading),
        as_at_range=sorted({p.as_at for p in provisions if p.as_at}),
    )


def parse_all() -> list[Provision]:
    provisions: list[Provision] = []
    for source in SOURCES:
        path = RAW_DIR / source.filename
        if not path.exists():
            raise FileNotFoundError(
                f"{path} is missing -- run `tenancy-rag corpus fetch` first"
            )
        provisions.extend(parse_document(path.read_bytes(), source))
    return provisions


def write_provisions(provisions: list[Provision], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for provision in provisions:
            handle.write(json.dumps(provision.to_dict(), ensure_ascii=False) + "\n")


def load_provisions(path: Path = PROVISIONS_PATH) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing -- run `tenancy-rag corpus build` first"
        )
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build(*, force_fetch: bool = False) -> CorpusStats:
    """Fetch (if needed), parse, write provisions.jsonl and the manifest."""
    ensure_dirs()
    manifest = fetch_all(force=force_fetch)
    provisions = parse_all()
    write_provisions(provisions, PROVISIONS_PATH)

    stats = summarise(provisions)
    manifest["corpus_stats"] = stats.as_dict()
    write_manifest(manifest, CORPUS_MANIFEST_PATH)
    return stats
