"""YouTube search + metadata via yt-dlp (no API key).

Output: data/raw/youtube/search_<YYYYmmdd-HHMMSS>.jsonl
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone

from ...config import Config
from ...util import clean_text, jsonl_write, parse_time


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} [youtube] {msg}", flush=True)


def _cmd(query: str, limit: int, since: str | None) -> list[str]:
    cmd = ["yt-dlp", "--dump-json", "--no-warnings", "--skip-download"]
    if since:
        cmd += ["--dateafter", since.replace("-", "")]
    cmd.append(f"ytsearch{limit}:{query}")
    return cmd


def to_record(v: dict) -> dict:
    vid = v.get("id")
    upload = v.get("upload_date") or ""
    ts = v.get("timestamp")
    if not ts and upload:
        ts = parse_time(f"{upload[:4]}-{upload[4:6]}-{upload[6:8]}", 0)
    return {
        "platform": "youtube", "platform_label": "YouTube", "kind": "video",
        "id": vid, "parent_id": "",
        "title": clean_text(v.get("title")),
        "description": clean_text(v.get("description")),
        "text": clean_text(v.get("description")),
        "author": v.get("uploader") or v.get("channel"),
        "time": ts,
        "like": v.get("like_count"),
        "comment_count": v.get("comment_count"),
        "view_count": v.get("view_count"),
        "duration_s": v.get("duration"),
        "url": v.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}",
        "src": "youtube",
        "crawled_at": int(datetime.now(timezone.utc).timestamp()),
    }


def run(cfg: Config, *, limit: int, queries: list[str] | None = None,
        dry_run: bool = False) -> list[dict]:
    queries = queries or cfg.queries("youtube") or list(cfg.keywords().get("core") or [])
    since = cfg.date_label(cfg.window_start)[:10] if cfg.window_start else None
    rows: dict[str, dict] = {}
    for q in queries:
        cmd = _cmd(q, limit, since)
        log(" ".join(cmd))
        if dry_run:
            continue
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except Exception as e:
            log(f"failed: {str(e)[:120]}")
            continue
        for line in (p.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                v = json.loads(line)
            except json.JSONDecodeError:
                continue
            r = to_record(v)
            if r["id"] and r["id"] not in rows:
                rows[r["id"]] = r
        log(f"  +{len(rows)} (total)")
    return list(rows.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--query", action="append", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    pc = cfg.platform_config("youtube")
    rows = run(cfg, limit=a.limit or int(pc.get("max_videos", 20)),
               queries=a.query, dry_run=a.dry_run)
    if rows and not a.dry_run:
        out = cfg.raw_dir / "youtube" / f"search_{datetime.now():%Y%m%d-%H%M%S}.jsonl"
        jsonl_write(out, rows)
        log(f"wrote {len(rows)} -> {out}")


if __name__ == "__main__":
    main()
