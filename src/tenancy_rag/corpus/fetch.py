"""Download each reprint as XML, once, and record exactly what we downloaded.

Pinning matters more here than it looks. legislation.govt.nz serves
point-in-time reprints, and the five documents in this corpus do *not* share an
"as at" date -- they were last reprinted on five different days. A single
"corpus date" would therefore be a fiction. Each document records its own
date.as.at, taken from the XML the publisher served rather than from the date we
happened to run the fetch, plus the list of amendment Acts the reprint claims to
incorporate.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import requests

from ..config import CORPUS_VERSION, RAW_DIR, ensure_dirs
from .sources import SOURCES, Source

USER_AGENT = (
    "tenancy-rag/0.1 (portfolio project; "
    "https://github.com/your-username/nz-tenancy-rag-evals)"
)
TIMEOUT = 90
RETRIES = 3
BACKOFF = 2.0

# The reprint's own metadata, read without a full parse so that a fetch record
# can be produced even if the document later fails to parse.
_AS_AT = re.compile(r'date\.as\.at="([^"]+)"')
_ASSENT = re.compile(r'date\.assent="([^"]+)"')
_REPRINT_DATE = re.compile(r"<reprint-date>([^<]+)</reprint-date>")
_TITLE = re.compile(r"<title>([^<]+)</title>")
_REPRINT_AMEND = re.compile(r"<reprint\.amend[^>]*>(.*?)</reprint\.amend>", re.S)
_TAGS = re.compile(r"<[^>]+>")


@dataclass
class FetchRecord:
    doc_id: str
    title: str
    short: str
    doc_type: str
    operative: bool
    xml_url: str
    html_url: str
    path: str
    bytes: int
    sha256: str
    as_at: str | None            # the publisher's point-in-time pin
    reprint_date: str | None
    assent_date: str | None
    xml_title: str | None        # title as the XML states it, to catch a wrong fetch
    retrieved_on: str
    incorporates: list[str] = field(default_factory=list)


def _strip(markup: str) -> str:
    return " ".join(_TAGS.sub(" ", markup).split())


def _download(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            response = requests.get(
                url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            # The site answers a bad path with a 200-looking HTML error page in
            # some configurations, so verify we actually received XML.
            if "xml" not in content_type and not response.content.lstrip().startswith(
                b"<?xml"
            ):
                raise RuntimeError(
                    f"{url} returned {content_type!r}, not XML -- the path shape "
                    "for this document is probably wrong"
                )
            return response.content
        except (requests.RequestException, RuntimeError) as error:
            last_error = error
            if attempt < RETRIES:
                time.sleep(BACKOFF * attempt)
    raise RuntimeError(f"failed to download {url}: {last_error}")


def _first(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def fetch_source(source: Source, *, force: bool = False) -> FetchRecord:
    ensure_dirs()
    path = RAW_DIR / source.filename
    if path.exists() and not force:
        payload = path.read_bytes()
    else:
        payload = _download(source.xml_url)
        path.write_bytes(payload)

    head = payload[:400_000].decode("utf-8", errors="replace")
    incorporates = [
        _strip(block) for block in _REPRINT_AMEND.findall(head) if _strip(block)
    ]

    return FetchRecord(
        doc_id=source.doc_id,
        title=source.title,
        short=source.short,
        doc_type=source.doc_type,
        operative=source.operative,
        xml_url=source.xml_url,
        html_url=source.html_url,
        path=path.relative_to(RAW_DIR.parents[1]).as_posix(),
        bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        as_at=_first(_AS_AT, head),
        reprint_date=_first(_REPRINT_DATE, head),
        assent_date=_first(_ASSENT, head),
        xml_title=_first(_TITLE, head),
        retrieved_on=date.today().isoformat(),
        incorporates=incorporates,
    )


def fetch_all(*, force: bool = False) -> dict:
    records = [fetch_source(source, force=force) for source in SOURCES]
    return {
        "corpus_version": CORPUS_VERSION,
        "jurisdiction": "New Zealand",
        "publisher": "New Zealand Parliamentary Counsel Office (legislation.govt.nz)",
        "licence": "Crown copyright; CC BY 4.0",
        "source_count": len(records),
        "total_bytes": sum(record.bytes for record in records),
        # Deliberately a range, not a single date: see the module docstring.
        "as_at_range": sorted({r.as_at for r in records if r.as_at}),
        "sources": [asdict(record) for record in records],
    }


def write_manifest(manifest: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False: the manifest is committed and read by humans, and
    # instrument titles contain en-dashes and macrons.
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
