"""Weibo collector via m.weibo.cn JSON interception.

Output:
  data/raw/weibo/posts_<YYYYmmdd-HHMMSS>.jsonl
  data/raw/weibo/comments_<YYYYmmdd-HHMMSS>.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import re
from datetime import datetime
from urllib.parse import quote

from playwright.async_api import async_playwright

from ...config import Config
from ...state import CrawlState
from ...util import jsonl_write, parse_time

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
      "Mobile/15E148 Safari/604.1")


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} [weibo] {msg}", flush=True)


def clean(t) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", t or "")).strip()


def parse_cards(data: dict, posts: dict) -> None:
    cards = (data.get("data") or {}).get("cards") or []
    for c in cards:
        for g in (c.get("card_group") or [c]):
            m = g.get("mblog")
            if not m or not m.get("id") or str(m["id"]) in posts:
                continue
            text = clean(m.get("text"))
            if not text:
                continue
            mid = str(m["id"])
            posts[mid] = {
                "platform": "微博", "kind": "post", "id": mid, "parent_id": "",
                "title": "", "text": text,
                "author": (m.get("user") or {}).get("screen_name"),
                "created_at": m.get("created_at"),
                "time": parse_time(m.get("created_at"), 8),
                "like": m.get("attitudes_count"),
                "comment_count": m.get("comments_count"),
                "reposts": m.get("reposts_count"),
                "url": f"https://m.weibo.cn/detail/{mid}",
                "crawled_at": int(datetime.now().timestamp()),
            }


def parse_comments(data: dict, mid: str, comments: dict) -> None:
    items = (((data or {}).get("data") or {}).get("data")) or []
    for c in items:
        cid = str(c.get("id") or "")
        if not cid or cid in comments:
            continue
        comments[cid] = {
            "platform": "微博", "kind": "comment", "id": cid, "parent_id": mid,
            "title": "", "text": clean(c.get("text")),
            "author": (c.get("user") or {}).get("screen_name"),
            "created_at": c.get("created_at"),
            "time": parse_time(c.get("created_at"), 8),
            "like": c.get("like_count"),
            "url": "",
            "crawled_at": int(datetime.now().timestamp()),
        }


async def run(cfg: Config, *, since: int, max_posts: int, max_comments: int,
              dry_run: bool = False) -> tuple[dict, dict]:
    queries = cfg.queries("weibo") or list(cfg.keywords().get("core") or [])
    if dry_run:
        for q in queries:
            log(f"query: {q}")
        return {}, {}

    posts: dict[str, dict] = {}
    comments: dict[str, dict] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel="chrome", headless=True)
        ctx = await browser.new_context(user_agent=UA, locale="zh-CN")

        for q in queries:
            page = await ctx.new_page()
            bucket: list[dict] = []

            async def on_resp(resp, bucket=bucket):
                if "/api/container/getIndex" in resp.url and resp.status == 200:
                    try:
                        bucket.append(await resp.json())
                    except Exception:
                        pass

            page.on("response", on_resp)
            log(f"search: {q}")
            await page.goto(
                f"https://m.weibo.cn/search?containerid=100103type%3D1%26q%3D{quote(q)}",
                wait_until="domcontentloaded", timeout=40000)
            for _ in range(4):
                await page.mouse.wheel(0, 3000)
                await asyncio.sleep(2.2)
            before = len(posts)
            for d in bucket:
                parse_cards(d, posts)
            log(f"  +{len(posts) - before} (total {len(posts)})")
            await page.close()
            await asyncio.sleep(1.2)

        ids = [k for k, v in posts.items()
               if not v.get("time") or v["time"] >= since][:max_posts]
        log(f"comments: {len(ids)} posts")
        for i, mid in enumerate(ids, 1):
            page = await ctx.new_page()
            cbucket: list[dict] = []

            async def on_resp(resp, cbucket=cbucket):
                if "/comments/hotflow" in resp.url and resp.status == 200:
                    try:
                        cbucket.append(await resp.json())
                    except Exception:
                        pass

            page.on("response", on_resp)
            try:
                await page.goto(f"https://m.weibo.cn/detail/{mid}",
                                wait_until="domcontentloaded", timeout=30000)
                for _ in range(3):
                    await page.mouse.wheel(0, 4000)
                    await asyncio.sleep(1.6)
            except Exception:
                pass
            for d in cbucket:
                parse_comments(d, mid, comments)
                if len(comments) >= max_comments * max_posts:
                    break
            await page.close()
            if i % 10 == 0:
                log(f"  {i}/{len(ids)} comments={len(comments)}")
            await asyncio.sleep(1.0)
        await browser.close()

    return posts, comments


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--max-posts", type=int, default=None)
    ap.add_argument("--max-comments", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    pc = cfg.platform_config("weibo")
    st = CrawlState(cfg.state_file,
                    overlap_hours=int((cfg.project.get("crawl") or {}).get("overlap_hours", 6)),
                    project_since=cfg.window_start)
    since = st.effective_since("weibo")
    if not a.dry_run:
        st.mark_started("weibo")
    try:
        posts, comments = asyncio.run(run(
            cfg, since=since,
            max_posts=a.max_posts or int(pc.get("max_posts", 100)),
            max_comments=a.max_comments or int(pc.get("max_comments", 300)),
            dry_run=a.dry_run))
        stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
        if posts:
            jsonl_write(cfg.raw_dir / "weibo" / f"posts_{stamp}.jsonl", posts.values())
        if comments:
            jsonl_write(cfg.raw_dir / "weibo" / f"comments_{stamp}.jsonl", comments.values())
        log(f"posts={len(posts)} comments={len(comments)}")
        if not a.dry_run:
            st.mark_finished("weibo", stats={"posts": len(posts), "comments": len(comments)},
                             success=True)
    except Exception:
        if not a.dry_run:
            st.mark_finished("weibo", success=False)
        raise


if __name__ == "__main__":
    main()
