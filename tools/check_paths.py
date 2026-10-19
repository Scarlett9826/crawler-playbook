#!/usr/bin/env python3
"""Fail if machine-specific absolute paths leak into the repository."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "vendors", "data", ".pytest_cache"}
SKIP_SUFFIX = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".m4a", ".mp4", ".wav"}

PATTERNS = [
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
    re.compile(r"/var/folders/"),
    re.compile(r"/private/tmp/"),
    re.compile(r"tools/MediaCrawler"),
    re.compile(r"analysis/out"),
]


def iter_files():
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in SKIP_SUFFIX:
            continue
        if p.name in {"check_anonymity.py", "check_paths.py"}:
            continue
        yield p


def main() -> None:
    hits = []
    for p in iter_files():
        try:
            lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            if any(pat.search(line) for pat in PATTERNS):
                hits.append((p.relative_to(ROOT), i, line.strip()[:160]))
    if hits:
        print(f"path check FAILED: {len(hits)} hit(s)")
        for f, i, line in hits[:80]:
            print(f"  {f}:{i}: {line}")
        raise SystemExit(1)
    print("path check OK")


if __name__ == "__main__":
    main()
