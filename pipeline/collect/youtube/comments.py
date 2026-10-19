"""YouTube comments via youtube-comment-downloader (no API key).

Input : data/raw/youtube/videos_*.jsonl or search_*.jsonl
Output: data/raw/youtube/comments_<stamp>.jsonl
"""
from __future__ import annotations

import argparse
import glob
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

from ...config import Config
from ...util import jsonl_read, jsonl_write, parse_time


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} [yt-comments] {msg}", flush=True)


def collect_videos(cfg: Config) -> list[dict]:
    rows: dict[str, dict] = {}
    for f in sorted(glob.glob(str(cfg.raw_dir / "youtube" / "*.jsonl"))):
        name = Path(f).name
        if name.startswith("comments_"):
            continue
        for d in jsonl_read(f):
            if d.get("kind") != "comment" and d.get("id"):
                rows[d["id"]] = d
    return list(rows.values())


def to_comment(c: dict, video_id: str) -> dict:
    t = c.get("time_parsed") or parse_time(c.get("time"), 0)
    return {
        "platform": "youtube", "platform_label": "YouTube", "kind": "comment",
        "id": str(c.get("cid") or c.get("id") or ""),
        "parent_id": video_id, "title": "",
        "text": (c.get("text") or "").strip(),
        "author": c.get("author"), "time": t,
        "like": c.get("votes"), "url": "",
        "src": "youtube-comment",
        "crawled_at": int(datetime.now(timezone.utc).timestamp()),
    }


def _done(cfg: Config) -> set[str]:
    done: set[str] = set()
    for f in glob.glob(str(cfg.raw_dir / "youtube" / "comments_*.jsonl")):
        for d in jsonl_read(f):
            if d.get("parent_id"):
                done.add(str(d["parent_id"]))
    return done


def run(cfg: Config, *, per_video: int, max_videos: int | None,
        dry_run: bool = False, refresh: bool = False) -> list[dict]:
    videos = collect_videos(cfg)
    done = set() if refresh else _done(cfg)
    videos = [v for v in videos if str(v.get("id")) not in done]
    if max_videos:
        videos = videos[:max_videos]
    if dry_run:
        for v in videos:
            log(f"would fetch comments for {v.get('id')}")
        return []
    try:
        from youtube_comment_downloader import SORT_BY_POPULAR, YoutubeCommentDownloader
    except Exception as e:
        raise SystemExit(f"youtube-comment-downloader missing: {e}")
    dl = YoutubeCommentDownloader()
    out = []
    for i, v in enumerate(videos, 1):
        try:
            it = dl.get_comments_from_url(v.get("url"), sort_by=SORT_BY_POPULAR)
            n = 0
            for c in islice(it, per_video):
                out.append(to_comment(c, str(v.get("id"))))
                n += 1
            log(f"[{i}/{len(videos)}] {v.get('id')} -> {n}")
        except Exception as e:
            log(f"[{i}/{len(videos)}] fail {v.get('id')}: {str(e)[:100]}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--per-video", type=int, default=None)
    ap.add_argument("--max-videos", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    pc = cfg.platform_config("youtube")
    rows = run(cfg, per_video=a.per_video or int(pc.get("max_comments", 200)),
               max_videos=a.max_videos, dry_run=a.dry_run, refresh=a.refresh)
    if rows and not a.dry_run:
        out = cfg.raw_dir / "youtube" / f"comments_{datetime.now():%Y%m%d-%H%M%S}.jsonl"
        jsonl_write(out, rows)
        log(f"wrote {len(rows)} -> {out}")


if __name__ == "__main__":
    main()
