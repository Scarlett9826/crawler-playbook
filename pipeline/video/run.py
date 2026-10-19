"""Video pipeline orchestrator.

Input : data/raw/video/index.jsonl (metadata, optional transcript/audio)
Output:
  data/video/triage.jsonl
  data/video/showcases.jsonl
  data/video/claims_media.jsonl
  data/video/manual_review.jsonl

Routing is conditional: no showcase is created for videos that do not contain
a self-tested, same-task, multi-model comparison.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config import Config, resolve
from ..util import jsonl_read, jsonl_write
from . import claims_media, showcase, triage
from .frame_text import attach


def load_transcript(cfg: Config, r: dict) -> list[dict]:
    if r.get("transcript"):
        return r["transcript"]
    tx_dir = cfg.raw_dir / "video" / "tx"
    for stem in (f'{r.get("platform")}_{r.get("id")}', str(r.get("id"))):
        p = tx_dir / f"{stem}.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--input", default="data/raw/video/index.jsonl")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    from ..llm import for_config
    llm = None if a.offline else for_config(cfg)

    src = resolve(a.input)
    rows = list(jsonl_read(src))
    if a.limit:
        rows = rows[:a.limit]
    if not rows:
        print(f"no input rows: {src}")
        return

    tri_rows, showcases, claims, review = [], [], [], []
    for i, r in enumerate(rows, 1):
        r["transcript"] = load_transcript(cfg, r)
        attach(cfg, r)
        tri = triage.run(cfg, r, llm)
        route = (tri.get("route") or {}).get("route")
        tri_rows.append({
            "platform": r.get("platform"), "id": r.get("id"), "url": r.get("url"),
            "title": r.get("title"), "author": r.get("author"), "time": r.get("time"),
            "transcript": r.get("transcript"), "triage": tri,
        })
        if route == "showcase_extract":
            for s in showcase.extract(cfg, r, tri, llm):
                showcases.append(showcase.validate(s, r, cfg))
        elif route == "claims_media":
            for c in claims_media.extract(cfg, r, llm):
                c["video"] = {"platform": r.get("platform"), "id": r.get("id"),
                              "url": r.get("url"), "title": r.get("title")}
                claims.append(c)
        elif route == "manual_review":
            review.append({
                "platform": r.get("platform"), "id": r.get("id"), "url": r.get("url"),
                "title": r.get("title"),
                "reason": tri.get("reason"),
                "needs_ocr": tri.get("needs_ocr"),
                "showcase": tri.get("showcase"),
            })
        print(f"[{i}/{len(rows)}] {tri.get('content_type')} -> {route}")

    jsonl_write(cfg.video_dir / "triage.jsonl", tri_rows)
    jsonl_write(cfg.video_dir / "showcases.jsonl", showcases)
    jsonl_write(cfg.video_dir / "claims_media.jsonl", claims)
    jsonl_write(cfg.video_dir / "manual_review.jsonl", review)
    print(f"triage={len(tri_rows)} showcases={len(showcases)} "
          f"claims={len(claims)} review={len(review)}")


if __name__ == "__main__":
    main()
