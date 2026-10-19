#!/usr/bin/env python3
"""Environment self-check. Run this before any crawl."""
from __future__ import annotations

import importlib
import shutil
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OK, WARN, FAIL = "OK", "WARN", "FAIL"
rows: list[tuple[str, str, str]] = []


def add(name: str, status: str, detail: str = "") -> None:
    rows.append((name, status, detail))


def check_python() -> None:
    v = sys.version_info
    add("python", OK if v >= (3, 10) else FAIL, f"{v.major}.{v.minor}.{v.micro}")


def check_module(name: str, label: str, required: bool = True) -> None:
    try:
        importlib.import_module(name)
        add(label, OK, "installed")
    except Exception as e:
        add(label, FAIL if required else WARN, str(e)[:80])


def check_bin(name: str, required: bool = True) -> None:
    path = shutil.which(name)
    add(name, OK if path else (FAIL if required else WARN), path or "missing")


def check_submodule() -> None:
    mc = ROOT / "vendors" / "MediaCrawler" / "main.py"
    add("MediaCrawler submodule", OK if mc.exists() else FAIL,
        str(mc.relative_to(ROOT)) if mc.exists() else "run: git submodule update --init")


def check_files() -> None:
    for rel in ("config/platforms.yaml", "config/project.example.yaml",
                "config/taxonomy.example.yaml", "requirements.txt"):
        p = ROOT / rel
        add(rel, OK if p.exists() else FAIL, "" if p.exists() else "missing")
    project = ROOT / "config" / "project.yaml"
    add("config/project.yaml", OK if project.exists() else WARN,
        "" if project.exists() else "using project.example.yaml")


def check_env() -> None:
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    else:
        add(".env", WARN, "missing; copy .env.example")
    for k, needed in (("LLM_BASE_URL", "LLM"), ("LLM_MODEL", "LLM")):
        add(k, OK if env.get(k) else WARN, "set in .env" if not env.get(k) else "")
    add("X cookies", OK if env.get("X_AUTH_TOKEN") and env.get("X_CT0_TOKEN") else WARN,
        "needed only for the X collector")


def check_network() -> None:
    for host, port in (("x.com", 443), ("www.youtube.com", 443)):
        try:
            with socket.create_connection((host, port), timeout=3):
                add(f"net:{host}", OK, "")
        except Exception as e:
            add(f"net:{host}", WARN, str(e)[:60])


def main() -> None:
    check_python()
    for mod, label in (("yaml", "PyYAML"), ("requests", "requests"),
                       ("playwright", "playwright"), ("markdown", "markdown")):
        check_module(mod, label)
    for mod, label in (("faster_whisper", "faster-whisper"),
                       ("youtube_transcript_api", "youtube-transcript-api")):
        check_module(mod, label, required=False)
    check_bin("ffmpeg")
    check_bin("yt-dlp")
    check_bin("node", required=False)
    check_submodule()
    check_files()
    check_env()
    check_network()

    width = max(len(r[0]) for r in rows) + 2
    for name, status, detail in rows:
        icon = {"OK": "✅", "WARN": "🟡", "FAIL": "❌"}[status]
        print(f"{icon} {name:<{width}} {detail}")
    fails = [r for r in rows if r[1] == FAIL]
    print(f"\n{len(rows) - len(fails)}/{len(rows)} checks ok")
    if fails:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
