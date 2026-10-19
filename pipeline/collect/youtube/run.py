"""YouTube end-to-end: search -> transcripts -> comments."""
from __future__ import annotations

import argparse
from datetime import datetime

from ...config import Config
from ...util import jsonl_write
from . import comments, search, transcript


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--per-video-comments", type=int, default=None)
    ap.add_argument("--no-whisper", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    pc = cfg.platform_config("youtube")
    limit = a.limit or int(pc.get("max_videos", 20))
    per_video = a.per_video_comments or int(pc.get("max_comments", 200))
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"

    print("== search ==")
    rows = search.run(cfg, limit=limit, dry_run=a.dry_run)
    if rows and not a.dry_run:
        out = cfg.raw_dir / "youtube" / f"search_{stamp}.jsonl"
        jsonl_write(out, rows)
        print(f"wrote {len(rows)} -> {out}")

    print("== transcript ==")
    videos = transcript.run(cfg, limit=limit, whisper=not a.no_whisper,
                            dry_run=a.dry_run, refresh=a.refresh)
    if videos and not a.dry_run:
        out = cfg.raw_dir / "youtube" / f"videos_{stamp}.jsonl"
        jsonl_write(out, videos)
        print(f"wrote {len(videos)} -> {out}")

    print("== comments ==")
    coms = comments.run(cfg, per_video=per_video, max_videos=limit,
                        dry_run=a.dry_run, refresh=a.refresh)
    if coms and not a.dry_run:
        out = cfg.raw_dir / "youtube" / f"comments_{stamp}.jsonl"
        jsonl_write(out, coms)
        print(f"wrote {len(coms)} -> {out}")


if __name__ == "__main__":
    main()
