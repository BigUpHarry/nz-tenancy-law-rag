"""Filesystem layout and defaults.

Every path in the project is derived from PROJECT_ROOT so the repo behaves the
same whether it is run from the root, from an IDE, or from CI.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "index"

EVALS_DIR = PROJECT_ROOT / "evals"
RESULTS_DIR = PROJECT_ROOT / "results"
RUNS_DIR = RESULTS_DIR / "runs"
CONFIG_DIR = PROJECT_ROOT / "config"
CACHE_DIR = PROJECT_ROOT / ".cache"

PROVISIONS_PATH = PROCESSED_DIR / "provisions.jsonl"
CORPUS_MANIFEST_PATH = PROCESSED_DIR / "manifest.json"

# Ollama. Overridable so the same code runs against a remote Ollama host.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_EMBED_MODEL = os.environ.get("TENANCY_RAG_EMBED_MODEL", "nomic-embed-text")
DEFAULT_GEN_MODEL = os.environ.get("TENANCY_RAG_GEN_MODEL", "qwen3:8b")

# A single string the README and every run record can point at, so a results
# table is never ambiguous about which corpus snapshot produced it.
CORPUS_VERSION = "nz-2026-10"


def ensure_dirs() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, INDEX_DIR, RUNS_DIR, CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)
