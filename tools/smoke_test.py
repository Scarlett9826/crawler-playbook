#!/usr/bin/env python3
"""Offline smoke test: no network, no credentials.

Copies the synthetic demo dataset into data/, then runs audit, analysis,
video triage/routing, and KOL aggregation. Exits non-zero on failure.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
PROJECT = "examples/demo/project.yaml"


def run(mod: str, *args: str) -> None:
    cmd = [PY, "-m", mod, *args]
    print("\n$", " ".join(cmd))
    p = subprocess.run(cmd, cwd=ROOT, text=True)
    if p.returncode != 0:
        raise SystemExit(f"FAILED: {' '.join(cmd)}")


def copy(src: str, dst: str) -> None:
    s = ROOT / src
    d = ROOT / dst
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(s, d)


def main() -> None:
    demo = ROOT / "examples" / "demo" / "dataset"
    if not (demo / "combined.jsonl").exists():
        subprocess.run([PY, str(ROOT / "tools" / "make_sample.py")], check=True, cwd=ROOT)

    copy("examples/demo/dataset/combined.jsonl", "data/normalized/combined.jsonl")
    copy("examples/demo/dataset/labels.jsonl", "data/labels/labels.jsonl")
    copy("examples/demo/video/index.jsonl", "data/raw/video/index.jsonl")

    # stats.json is normally produced by pipeline.normalize; synthesize for the demo
    rows = [json.loads(l) for l in (ROOT / "data/normalized/combined.jsonl").open(encoding="utf-8")]
    times = [r["time"] for r in rows if r.get("time")]
    stats = {
        "generated_at": 0,
        "window": {"since": min(times), "until": max(times) + 86400},
        "raw_records": len(rows), "kept_records": len(rows),
        "dropped": {"irrelevant": 0, "out_of_window": 0, "duplicate_id": 0, "duplicate_text": 0},
        "unknown_time": 0, "duplicate_ratio": 0.0, "unknown_time_ratio": 0.0,
        "by_platform": {}, "by_kind": {},
        "time_range": {"min": min(times), "max": max(times), "min_iso": "", "max_iso": ""},
    }
    (ROOT / "data/normalized/stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    run("pipeline.audit", "--project", PROJECT)
    run("pipeline.analyze.metrics", "--project", PROJECT)
    run("pipeline.analyze.themes", "--project", PROJECT)
    run("pipeline.analyze.balanced", "--project", PROJECT)
    run("pipeline.analyze.deep", "--project", PROJECT)
    run("pipeline.analyze.negative", "--project", PROJECT)
    run("pipeline.video.run", "--project", PROJECT, "--offline")
    run("pipeline.kol.extract", "--project", PROJECT)
    run("pipeline.kol.aggregate", "--project", PROJECT)

    expected = [
        "data/metrics/audit.json",
        "data/metrics/metrics.json",
        "data/metrics/themes.json",
        "data/metrics/balanced.json",
        "data/metrics/deep.json",
        "data/video/triage.jsonl",
        "data/video/showcases.jsonl",
        "data/video/claims_media.jsonl",
        "data/video/manual_review.jsonl",
        "data/kol/evals.jsonl",
        "data/metrics/kol.json",
    ]
    missing = [p for p in expected if not (ROOT / p).exists()]
    if missing:
        raise SystemExit(f"missing outputs: {missing}")

    print("\nSmoke test OK")
    print("outputs:")
    for p in expected:
        print("  ", p)


if __name__ == "__main__":
    main()
