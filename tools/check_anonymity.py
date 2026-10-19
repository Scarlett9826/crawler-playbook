#!/usr/bin/env python3
"""Fail if project-identifying terms leak into the repository.

Scope (per project decision): only the anonymized brand and the LLM proxy.
Competitor and third-party names are allowed.

Usage: python tools/check_anonymity.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "vendors", "data", ".pytest_cache"}
SKIP_SUFFIX = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".m4a", ".mp4", ".wav"}

# Case-insensitive; word-ish boundaries where useful.
BANNED = [
    r"(?<![a-z0-9_-])xiaomi(?![a-z0-9_-])", r"小米",
    r"(?<![a-z0-9_-])mimo(?![a-z0-9_-])", r"罗福莉", r"luo\s*fuli",
    r"雷军", r"卢伟冰", r"天才少女", r"九亿少女的梦", r"22\s*级",
    r"斩杀线", r"mify", r"mify-proxy", r"18080",
    r"@xiaomimimo", r"@xiaomitech_", r"@xiaomi(?![a-z0-9_-])",
    r"未命名文件夹",
]

PATTERN = re.compile("|".join(f"(?:{p})" for p in BANNED), re.I)


def iter_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
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
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line):
                hits.append((p.relative_to(ROOT), i, line.strip()[:160]))
    if hits:
        print(f"anonymity check FAILED: {len(hits)} hit(s)")
        for f, i, line in hits[:80]:
            print(f"  {f}:{i}: {line}")
        if len(hits) > 80:
            print(f"  ... {len(hits) - 80} more")
        raise SystemExit(1)
    print("anonymity check OK")


if __name__ == "__main__":
    main()
