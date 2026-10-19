"""X targeted collection: anchor tweets + reply threads (TweetDetail).

Output:
  data/raw/x/anchors_<YYYYmmdd-HHMMSS>.jsonl
  data/raw/x/replies_<YYYYmmdd-HHMMSS>.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import json
from datetime import datetime
from urllib.parse import quote

from playwright.async_api import async_playwright

from ...config import Config
from ...state import CrawlState
from ...util import jsonl_read, jsonl_write
from .common import (capture, dedupe_by_id, log, new_context, normalize_tweet,
                     since_str, walk_tweets)

CLICK = ("Show more replies", "Show probable spam", "显示更多回复", "Show replies")


async def collect_anchors(cfg: Config, page, queries: list[str],
                          since: int, scrolls: int) -> dict[str, dict]:
    anchors: dict[str, dict] = {}
    since_s = since_str(since, cfg.tz_offset)
    for q in queries:
        for tab in ("top", "live"):
            url = (f"https://x.com/search?q={quote(q + ' since:' + since_s)}"
                   f"&src=typed_query" + ("&f=live" if tab == "live" else ""))
            log(f"[{tab}] {q}")
            resps = await capture(page, url, "SearchTimeline", scrolls, wait=2.0)
            n0 = len(anchors)
            for r in resps:
                acc: list[dict] = []
                walk_tweets(r, acc)
                for res in acc:
                    d = normalize_tweet(res, query=q, tab=tab)
                    if not d["id"] or d["id"] in anchors:
                        continue
                    if d["time"] and d["time"] < since:
                        continue
                    anchors[d["id"]] = d
            log(f"  +{len(anchors) - n0} (total {len(anchors)})")
            await asyncio.sleep(1.2)
    return anchors


def merge_previous(anchors: dict[str, dict], cfg: Config, since: int) -> None:
    for f in sorted(glob.glob(str(cfg.raw_dir / "x" / "*.jsonl"))):
        name = f.rsplit("/", 1)[-1]
        if not (name.startswith("anchors_") or name.startswith("search_")):
            continue
        for d in jsonl_read(f):
            if not d.get("id"):
                continue
            t = d.get("time")
            if t and t < since:
                continue
            anchors.setdefault(d["id"], d)


async def collect_replies(cfg: Config, page, targets: list[dict],
                          out_path, scrolls: int) -> int:
    done: set[str] = set()
    for f in glob.glob(str(cfg.raw_dir / "x" / "replies_*.jsonl")):
        for d in jsonl_read(f):
            if d.get("anchor_id"):
                done.add(str(d["anchor_id"]))

    total = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as fo:
        for i, a in enumerate(targets, 1):
            if str(a["id"]) in done:
                continue
            resps = await capture(page, a["url"], "TweetDetail", scrolls, wait=2.2,
                                  click_labels=CLICK)
            seen: set[str] = set()
            n = 0
            for r in resps:
                acc: list[dict] = []
                walk_tweets(r, acc)
                for res in acc:
                    d = normalize_tweet(res, kind="comment", parent_id=a["id"],
                                        anchor_id=a["id"],
                                        anchor_author=a.get("author"))
                    if d["id"] == a["id"] or d["id"] in seen:
                        continue
                    if d.get("conversation_id") != a["id"] and d.get("in_reply_to") is None:
                        continue
                    seen.add(d["id"])
                    fo.write(json.dumps(d, ensure_ascii=False) + "\n")
                    n += 1
            fo.flush()
            total += n
            log(f"[{i}/{len(targets)}] @{a.get('author')} replies={a.get('reply_count')} -> {n}")
            await asyncio.sleep(1.8)
    return total


async def run(cfg: Config, *, since: int, max_threads: int, scrolls: int,
              min_replies: int, dry_run: bool = False) -> tuple[list[dict], list[dict]]:
    xcfg = cfg.platform_config("x")
    queries = list(cfg.queries("x") or [])
    authority = [h.lstrip("@").lower() for h in (xcfg.get("authority") or [])]
    for h in authority:
        queries.append(f"from:{h}")

    if dry_run:
        for q in queries:
            log(f"query: {q} since:{since_str(since, cfg.tz_offset)}")
        return [], []

    async with async_playwright() as pw:
        browser, ctx = await new_context(pw, cfg)
        page = await ctx.new_page()

        anchors = await collect_anchors(cfg, page, queries, since, max(4, scrolls // 2))
        merge_previous(anchors, cfg, since)

        pool = list(anchors.values())

        def is_relevant(d: dict) -> bool:
            kw = cfg.keywords()
            terms = [str(x).lower() for x in (kw.get("core") or []) + (kw.get("include") or [])]
            s = (d.get("text") or "").lower()
            return not terms or any(t in s for t in terms)

        auth = [d for d in pool
                if (d.get("author") or "").lower() in authority and is_relevant(d)]
        rest = [d for d in pool
                if d not in auth and is_relevant(d) and (d.get("reply_count") or 0) >= min_replies]
        auth.sort(key=lambda d: -(d.get("reply_count") or 0))
        rest.sort(key=lambda d: -(d.get("reply_count") or 0))
        targets = (auth + rest)[:max_threads]
        log(f"reply targets: {len(targets)} (authority {len(auth)})")

        stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
        anchors_path = cfg.raw_dir / "x" / f"anchors_{stamp}.jsonl"
        replies_path = cfg.raw_dir / "x" / f"replies_{stamp}.jsonl"
        jsonl_write(anchors_path, dedupe_by_id(pool))
        n = await collect_replies(cfg, page, targets, replies_path, scrolls)
        log(f"replies written: {n} -> {replies_path}")
        await browser.close()
    return pool, targets


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--max-threads", type=int, default=None)
    ap.add_argument("--scrolls", type=int, default=None)
    ap.add_argument("--min-replies", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    xcfg = cfg.platform_config("x")
    st = CrawlState(cfg.state_file,
                    overlap_hours=int((cfg.project.get("crawl") or {}).get("overlap_hours", 6)),
                    project_since=cfg.window_start)
    since = st.effective_since("x")
    if not a.dry_run:
        st.mark_started("x")
    try:
        pool, targets = asyncio.run(run(
            cfg, since=since,
            max_threads=a.max_threads or int(xcfg.get("max_anchors", 45)),
            scrolls=a.scrolls or int(xcfg.get("max_scrolls", 14)),
            min_replies=a.min_replies, dry_run=a.dry_run))
        if not a.dry_run:
            st.mark_finished("x", stats={"anchors": len(pool), "threads": len(targets)},
                             success=True)
    except Exception:
        if not a.dry_run:
            st.mark_finished("x", success=False)
        raise


if __name__ == "__main__":
    main()
