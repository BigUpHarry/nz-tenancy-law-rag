"""Command line entry point.

Subcommands are added as each phase of the project lands, so the CLI doubles as
a map of what the project can currently do.
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.table import Table

from .config import CORPUS_MANIFEST_PATH, PROVISIONS_PATH

console = Console()


def _cmd_corpus_fetch(args: argparse.Namespace) -> int:
    from .corpus.fetch import fetch_all, write_manifest

    manifest = fetch_all(force=args.force)
    write_manifest(manifest, CORPUS_MANIFEST_PATH)

    table = Table(title="Downloaded reprints", header_style="bold")
    table.add_column("Doc")
    table.add_column("Type")
    table.add_column("Bytes", justify="right")
    table.add_column("As at")
    table.add_column("Incorporates", justify="right")
    for record in manifest["sources"]:
        table.add_row(
            record["short"],
            record["doc_type"],
            f"{record['bytes']:,}",
            record["as_at"] or "-",
            str(len(record["incorporates"])),
        )
    console.print(table)
    console.print(f"total: {manifest['total_bytes']:,} bytes")
    console.print(
        "as-at dates span: " + ", ".join(manifest["as_at_range"])
        + "  [dim](five reprints, five dates -- pinned individually)"
    )
    return 0


def _cmd_corpus_build(args: argparse.Namespace) -> int:
    from .corpus.build import build

    stats = build(force_fetch=args.refetch)

    table = Table(title="Parsed provisions", header_style="bold")
    table.add_column("Doc")
    table.add_column("Provisions", justify="right")
    for doc, count in stats.by_doc.items():
        table.add_row(doc, str(count))
    table.add_row("[bold]total", f"[bold]{stats.provisions}")
    console.print(table)

    console.print(
        f"chars: total {stats.total_chars:,} | median {stats.median_chars:,} "
        f"| p95 {stats.p95_chars:,} | max {stats.max_chars:,}"
    )
    console.print(
        f"operative {stats.operative} | repealed {stats.repealed} "
        f"| amendment decoys {stats.decoy}"
    )
    console.print(f"provisions with no heading: {stats.empty_headings}")
    console.print(f"written: {PROVISIONS_PATH}")
    return 0


def _cmd_corpus_show(args: argparse.Namespace) -> int:
    from .corpus.build import load_provisions

    provisions = load_provisions()
    matches = [
        provision
        for provision in provisions
        if args.query.lower() in provision["key"].lower()
        or args.query.lower() in provision["heading"].lower()
    ]
    if not matches:
        console.print(f"[red]no provision matching {args.query!r}")
        return 1
    for provision in matches[: args.limit]:
        console.rule(provision["citation"])
        console.print(f"[dim]{provision['key']}  ({provision['dlm_id']})")
        console.print(f"[dim]{provision['url']}")
        flags = [provision["status"], f"as at {provision['as_at']}"]
        if not provision["operative"]:
            flags.append("NOT OPERATIVE")
        console.print(f"[dim]{' | '.join(flags)}")
        if provision["breadcrumb"]:
            console.print(f"[dim]{' > '.join(provision['breadcrumb'])}")
        console.print(provision["text"][: args.chars])
    console.print(f"\n[dim]{len(matches)} match(es); showing {min(len(matches), args.limit)}")
    return 0


def _cmd_corpus_check(args: argparse.Namespace) -> int:
    from .corpus.build import load_provisions
    from .corpus.quality import run_checks

    checks = run_checks(load_provisions())

    table = Table(title="Corpus data-quality checks", header_style="bold")
    table.add_column("")
    table.add_column("Check")
    table.add_column("Detail", overflow="fold")
    for check in checks:
        style = "green" if check.passed else "bold red"
        table.add_row(f"[{style}]{check.symbol}", check.name, check.detail)
    console.print(table)

    failed = [check for check in checks if not check.passed]
    if failed:
        console.print(f"[bold red]{len(failed)} check(s) failed")
        return 1
    console.print(f"[green]all {len(checks)} checks passed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tenancy-rag",
        description="Retrieval-augmented QA over New Zealand residential tenancy law.",
    )
    subparsers = parser.add_subparsers(dest="group", required=True)

    corpus = subparsers.add_parser("corpus", help="build and inspect the corpus")
    corpus_sub = corpus.add_subparsers(dest="action", required=True)

    fetch = corpus_sub.add_parser("fetch", help="download reprint XML from legislation.govt.nz")
    fetch.add_argument("--force", action="store_true", help="re-download cached files")
    fetch.set_defaults(func=_cmd_corpus_fetch)

    build_cmd = corpus_sub.add_parser("build", help="parse XML into provisions.jsonl")
    build_cmd.add_argument("--refetch", action="store_true", help="re-download first")
    build_cmd.set_defaults(func=_cmd_corpus_build)

    check = corpus_sub.add_parser(
        "check", help="run the data-quality gate over the built corpus"
    )
    check.set_defaults(func=_cmd_corpus_check)

    show = corpus_sub.add_parser("show", help="print provisions matching a query")
    show.add_argument("query", help="substring of a provision key or heading")
    show.add_argument("--limit", type=int, default=3)
    show.add_argument("--chars", type=int, default=1200)
    show.set_defaults(func=_cmd_corpus_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
