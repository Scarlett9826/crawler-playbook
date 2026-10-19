"""Normalize all platform outputs into one schema.

Guarantees:
  - every record has stable fields (platform/kind/id/text/time)
  - comments inherit relevance from their parent post
  - duplicates are collapsed, with counts reported
  - out-of-window and irrelevant records are counted, not silently dropped

Output:
  data/normalized/combined.jsonl
  data/normalized/stats.json
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .util import clean_text, jsonl_read, jsonl_write, json_write, parse_time, to_epoch

MC_CODE = {
    "xiaohongshu": "xhs",
    "douyin": "douyin",
    "bilibili": "bili",
    "zhihu": "zhihu",
    "weibo": "weibo",
}


def _first(d: dict, *keys, default=""):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return default


def _user_name(d: dict) -> str:
    user = d.get("user")
    if isinstance(user, dict):
        return clean_text(user.get("nickname") or user.get("screen_name") or "")
    return clean_text(_first(d, "nickname", "user_nickname", "user_name", "author"))


def mc_records(cfg: Config, platform: str) -> tuple[list[dict], list[dict]]:
    code = MC_CODE.get(platform, platform)
    dirs = [cfg.raw_dir / platform, cfg.media_crawler_data / code]
    posts, comments = [], []

    for root in dirs:
        for f in glob.glob(str(root / "**" / "*.jsonl"), recursive=True):
            low = f.lower()
            is_comment = "comment" in low
            for d in jsonl_read(f):
                if is_comment:
                    pid = str(_first(d, "note_id", "aweme_id", "video_id", "content_id"))
                    comments.append({
                        "platform": platform, "kind": "comment",
                        "id": str(_first(d, "comment_id", "cid", "id")),
                        "parent_id": pid,
                        "reply_to": str(_first(d, "parent_comment_id", "reply_id")),
                        "title": "", "text": clean_text(_first(d, "content", "text")),
                        "author": _user_name(d),
                        "time": to_epoch(_first(d, "create_time", "publish_time", "time")),
                        "like": _first(d, "like_count", "like_counts", "digg_count", default=0),
                        "url": "", "src": f"{platform}-comment",
                        "crawled_at": int(datetime.now(timezone.utc).timestamp()),
                    })
                else:
                    pid = str(_first(d, "note_id", "aweme_id", "video_id", "content_id"))
                    posts.append({
                        "platform": platform, "kind": "post", "id": pid,
                        "parent_id": "",
                        "title": clean_text(_first(d, "title", "desc")),
                        "text": clean_text(_first(d, "desc", "content", "title")),
                        "author": _user_name(d),
                        "time": to_epoch(_first(d, "time", "create_time", "created_time")),
                        "like": _first(d, "liked_count", "like_count", "voteup_count",
                                       "digg_count", default=0),
                        "comment_count": _first(d, "comment_count", "video_comment",
                                                "comments_count", default=None),
                        "url": _first(d, "note_url", "aweme_url", "video_url", "content_url"),
                        "src": f"{platform}-post",
                        "crawled_at": int(datetime.now(timezone.utc).timestamp()),
                    })
    return posts, comments


def weibo_records(cfg: Config) -> tuple[list[dict], list[dict]]:
    posts, comments = [], []
    for f in glob.glob(str(cfg.raw_dir / "weibo" / "*.jsonl")):
        for d in jsonl_read(f):
            if d.get("kind") == "comment":
                comments.append({**d, "platform": "weibo", "kind": "comment",
                                 "text": clean_text(d.get("text")),
                                 "time": d.get("time") or parse_time(d.get("created_at"), 8)})
            else:
                posts.append({**d, "platform": "weibo", "kind": "post", "parent_id": "",
                              "title": d.get("title") or "",
                              "text": clean_text(d.get("text")),
                              "time": d.get("time") or parse_time(d.get("created_at"), 8),
                              "comment_count": d.get("comment_count") or d.get("comments")})
    return posts, comments


def wechat_records(cfg: Config) -> list[dict]:
    out = []
    for f in glob.glob(str(cfg.raw_dir / "wechat" / "*.jsonl")):
        for d in jsonl_read(f):
            if not d.get("content") and not d.get("text"):
                continue
            out.append({
                "platform": "wechat", "kind": "article", "id": str(d.get("id") or ""),
                "parent_id": "", "title": clean_text(d.get("title")),
                "text": clean_text(d.get("content") or d.get("text")),
                "author": clean_text(d.get("account") or d.get("author")),
                "time": d.get("time") or parse_time(d.get("publish_time") or d.get("date"), 8),
                "like": None, "comment_count": None,
                "url": d.get("url") or "", "src": "wechat",
                "keyword": d.get("keyword", ""),
                "crawled_at": d.get("crawled_at") or int(datetime.now(timezone.utc).timestamp()),
            })
    return out


def x_records(cfg: Config) -> tuple[list[dict], list[dict]]:
    tweets, replies = [], []
    for f in glob.glob(str(cfg.raw_dir / "x" / "*.jsonl")):
        name = f.rsplit("/", 1)[-1]
        if name.startswith("video_"):
            continue
        for d in jsonl_read(f):
            kind = d.get("kind") or ("comment" if name.startswith("replies_") else "tweet")
            rec = {
                "platform": "x", "kind": kind,
                "id": str(d.get("id") or ""),
                "parent_id": str(d.get("parent_id") or d.get("anchor_id") or ""),
                "title": "", "text": clean_text(d.get("text")),
                "author": d.get("author") or d.get("screen_name"),
                "time": d.get("time") or parse_time(d.get("created_at"), 0),
                "like": d.get("like") or d.get("like_count"),
                "comment_count": d.get("reply_count"),
                "url": d.get("url") or "",
                "src": "x-reply" if kind == "comment" else "x",
                "media": d.get("media") or [],
                "has_video": d.get("has_video", False),
                "crawled_at": d.get("crawled_at") or int(datetime.now(timezone.utc).timestamp()),
            }
            (replies if kind == "comment" else tweets).append(rec)
    return tweets, replies


def youtube_records(cfg: Config) -> tuple[list[dict], list[dict]]:
    videos, comments = [], []
    for f in glob.glob(str(cfg.raw_dir / "youtube" / "*.jsonl")):
        for d in jsonl_read(f):
            if d.get("kind") == "comment":
                comments.append({
                    "platform": "youtube", "kind": "comment",
                    "id": str(d.get("id") or ""), "parent_id": str(d.get("parent_id") or ""),
                    "title": "", "text": clean_text(d.get("text")),
                    "author": d.get("author"), "time": d.get("time"),
                    "like": d.get("like"), "url": "", "src": "youtube-comment",
                })
            else:
                videos.append({
                    "platform": "youtube", "kind": "video",
                    "id": str(d.get("id") or ""), "parent_id": "",
                    "title": clean_text(d.get("title")),
                    "text": clean_text(d.get("description") or d.get("text")),
                    "author": d.get("author") or d.get("channel"),
                    "time": d.get("time") or d.get("published_at"),
                    "like": d.get("like"), "comment_count": d.get("comment_count"),
                    "url": d.get("url") or "", "src": "youtube",
                    "duration_s": d.get("duration_s"),
                    "transcript": d.get("transcript"),
                    "transcript_source": d.get("transcript_source"),
                })
    return videos, comments


def collect(cfg: Config) -> list[dict]:
    records: list[dict] = []
    for platform in cfg.enabled_platforms():
        adapter = (cfg.platform(platform) or {}).get("adapter")
        if adapter == "media_crawler":
            p, c = mc_records(cfg, platform)
            records += p + c
        elif adapter == "weibo":
            p, c = weibo_records(cfg)
            records += p + c
        elif adapter == "wechat":
            records += wechat_records(cfg)
        elif adapter == "x":
            p, c = x_records(cfg)
            records += p + c
        elif adapter == "youtube":
            p, c = youtube_records(cfg)
            records += p + c

    for r in records:
        pc = cfg.platform(r.get("platform", "")) or {}
        r["platform_label"] = pc.get("label") or r.get("platform", "")
    return records


def apply_relevance(cfg: Config, records: list[dict]) -> tuple[list[dict], int]:
    include, exclude = cfg.relevance_patterns()
    for r in records:
        blob = f"{r.get('title','')} {r.get('text','')}"
        hit = bool(include.search(blob)) if include else True
        if exclude and exclude.search(blob):
            hit = False
        r["relevant"] = hit
        r["inherit"] = False

    # comments inherit relevance from a relevant parent post
    rel_parent = {(r["platform"], r["id"]) for r in records
                  if r.get("kind") in ("post", "article", "tweet", "video") and r.get("relevant")}
    for r in records:
        if r.get("kind") == "comment" and not r.get("relevant"):
            pid = r.get("parent_id")
            if pid and (r["platform"], pid) in rel_parent:
                r["relevant"] = True
                r["inherit"] = True

    kept = [r for r in records if r.get("relevant")]
    return kept, len(records) - len(kept)


def dedupe(records: list[dict]) -> tuple[list[dict], int, int]:
    seen: dict[tuple, int] = {}
    out: list[dict] = []
    dup_id = 0
    for r in records:
        key = ((r["platform"], r["kind"], r["id"]) if r.get("id")
               else (r["platform"], r["kind"], (r.get("text") or "")[:120]))
        if key in seen:
            dup_id += 1
            old = out[seen[key]]
            # prefer the record with more fields filled
            if len([1 for v in r.values() if v not in (None, "", [], 0)]) > \
               len([1 for v in old.values() if v not in (None, "", [], 0)]):
                out[seen[key]] = r
            continue
        seen[key] = len(out)
        out.append(r)

    seen2: set[tuple] = set()
    final: list[dict] = []
    dup_text = 0
    for r in out:
        k2 = (r["platform"], r["kind"], (r.get("text") or "")[:120])
        if r.get("text") and k2 in seen2:
            dup_text += 1
            continue
        seen2.add(k2)
        final.append(r)
    return final, dup_id, dup_text


def filter_window(cfg: Config, records: list[dict]) -> tuple[list[dict], int, int]:
    kept, out_of_window, unknown = [], 0, 0
    for r in records:
        t = r.get("time")
        if not t:
            r["time_known"] = False
            unknown += 1
            kept.append(r)
            continue
        r["time_known"] = True
        if t < cfg.window_start or t > cfg.window_end:
            out_of_window += 1
            continue
        kept.append(r)
    return kept, out_of_window, unknown


def stats(cfg: Config, records: list[dict], raw_n: int, irrelevant: int,
          out_of_window: int, unknown: int, dup_id: int, dup_text: int) -> dict:
    by_platform = Counter(r["platform"] for r in records)
    by_kind = Counter(f'{r["platform"]}/{r["kind"]}' for r in records)
    times = [r["time"] for r in records if r.get("time")]
    return {
        "generated_at": int(datetime.now(timezone.utc).timestamp()),
        "window": {"since": cfg.window_start, "until": cfg.window_end},
        "raw_records": raw_n,
        "kept_records": len(records),
        "dropped": {
            "irrelevant": irrelevant,
            "out_of_window": out_of_window,
            "duplicate_id": dup_id,
            "duplicate_text": dup_text,
        },
        "unknown_time": unknown,
        "duplicate_ratio": round((dup_id + dup_text) / raw_n, 4) if raw_n else 0,
        "unknown_time_ratio": round(unknown / len(records), 4) if records else 0,
        "by_platform": dict(by_platform),
        "by_kind": dict(by_kind),
        "time_range": {
            "min": min(times) if times else None,
            "max": max(times) if times else None,
            "min_iso": cfg.date_label(min(times)) if times else "",
            "max_iso": cfg.date_label(max(times)) if times else "",
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    records = collect(cfg)
    raw_n = len(records)
    records, irrelevant = apply_relevance(cfg, records)
    records, out_of_window, unknown = filter_window(cfg, records)
    records, dup_id, dup_text = dedupe(records)
    records.sort(key=lambda r: (r.get("time") or 0))
    n = jsonl_write(cfg.normalized_dir / "combined.jsonl", records)
    st = stats(cfg, records, raw_n, irrelevant, out_of_window, unknown, dup_id, dup_text)
    json_write(cfg.normalized_dir / "stats.json", st)

    print(f"raw={raw_n} kept={n} irrelevant={irrelevant} out_of_window={out_of_window} "
          f"dup_id={dup_id} dup_text={dup_text} unknown_time={unknown}")
    print("by_platform:", st["by_platform"])
    print("time_range:", st["time_range"])
    print("wrote:", cfg.normalized_dir / "combined.jsonl")


if __name__ == "__main__":
    main()
