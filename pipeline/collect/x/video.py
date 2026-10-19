"""Download audio from X posts that contain video.

We use the tweet URL (not the CDN variant URL) because yt-dlp resolves the
current signed URL at download time; direct CDN links expire.

Output:
  data/raw/x/video/<id>.m4a
  data/raw/x/video/manifest.jsonl
"""
from __future__ import annotations

import argparse
import glob
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from ...config import Config
from ...util import jsonl_read, jsonl_write, json_write


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} [x-video] {msg}", flush=True)


def collect(cfg: Config) -> list[dict]:
    rows: dict[str, dict] = {}
    for f in sorted(glob.glob(str(cfg.raw_dir / "x" / "*.jsonl"))):
        name = f.rsplit("/", 1)[-1]
        if name.startswith("video_"):
            continue
        for d in jsonl_read(f):
            media = d.get("media") or []
            if any(m.get("type") in ("video", "animated_gif") for m in media):
                rows.setdefault(str(d["id"]), d)
    return list(rows.values())


def download(url: str, out: Path, dry_run: bool = False) -> bool:
    if out.exists() and out.stat().st_size > 1024:
        return True
    if dry_run:
        log(f"would download {url}")
        return True
    if not shutil.which("yt-dlp"):
        log("yt-dlp missing")
        return False
    tmp = out.with_suffix(".part.%(ext)s")
    cmd = [
        "yt-dlp", "-q", "--no-warnings",
        "-f", "ba/b",
        "-x", "--audio-format", "m4a", "--audio-quality", "5",
        "-o", str(out.with_suffix("")) + ".%(ext)s",
        url,
    ]
    try:
        subprocess.run(cmd, check=True, timeout=600,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        log(f"failed {url}: {str(e)[:120]}")
        return False
    return out.exists() or any(out.parent.glob(out.stem + ".*"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    out_dir = cfg.raw_dir / "x" / "video"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = collect(cfg)
    if a.limit:
        rows = rows[:a.limit]
    log(f"tweets with video: {len(rows)}")

    manifest = []
    for i, d in enumerate(rows, 1):
        out = out_dir / f"{d['id']}.m4a"
        ok = download(d["url"], out, a.dry_run)
        manifest.append({
            "platform": "X", "kind": "video_media",
            "id": d["id"], "parent_id": d["id"],
            "title": (d.get("text") or "")[:120],
            "author": d.get("author"), "url": d.get("url"),
            "time": d.get("time"), "like": d.get("like"),
            "media_path": str(out.relative_to(cfg.root)) if ok else "",
            "ok": ok,
        })
        log(f"[{i}/{len(rows)}] {d['id']} ok={ok}")
    jsonl_write(out_dir / "manifest.jsonl", manifest)
    json_write(out_dir / "summary.json", {
        "tweets": len(rows), "downloaded": sum(1 for m in manifest if m["ok"]),
    })


if __name__ == "__main__":
    main()
