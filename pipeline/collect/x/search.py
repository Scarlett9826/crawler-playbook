"""X keyword search via Playwright response interception (SearchTimeline).

Output: data/raw/x/search_<YYYYmmdd-HHMMSS>.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from urllib.parse import quote

from playwright.async_api import async_playwright

from ...config import Config
from ...state import CrawlState
from ...util import jsonl_write
from .common import capture, dedupe_by_id, log, new_context, normalize_tweet, since_str, walk_tweets


async def run(cfg: Config, *, scrolls: int, max_queries: int | None,
              since: int, dry_run: bool = False) -> list[dict]:
    queries = cfg.queries("x") or list(cfg.keywords().get("core") or [])
    if max_queries:
        queries = queries[:max_queries]
    if dry_run:
        for q in queries:
            log(f"query: {q} since:{since_str(since, cfg.tz_offset)}")
        return []

    collected: dict[str, dict] = {}
    async with async_playwright() as pw:
        browser, ctx = await new_context(pw, cfg)
        page = await ctx.new_page()
        for q in queries:
            url = f"https://x.com/search?q={quote(q)}&src=typed_query&f=live"
            log(f"search: {q}")
            resps = await capture(page, url, "SearchTimeline", scrolls, wait=2.2)
            n0 = len(collected)
            for r in resps:
                acc: list[dict] = []
                walk_tweets(r, acc)
                for res in acc:
                    d = normalize_tweet(res, query=q, tab="live")
                    if not d["id"] or d["id"] in collected:
                        continue
                    if d["time"] and d["time"] < since:
                        continue
                    collected[d["id"]] = d
            log(f"  +{len(collected) - n0} (total {len(collected)})")
            await asyncio.sleep(1.5)
        await browser.close()
    return list(collected.values())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--scrolls", type=int, default=8)
    ap.add_argument("--max-queries", type=int, default=None)
    ap.add_argument("--since", default=None, help="YYYY-MM-DD; default from state/project")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    st = CrawlState(cfg.state_file,
                    overlap_hours=int((cfg.project.get("crawl") or {}).get("overlap_hours", 6)),
                    project_since=cfg.window_start)
    since = cfg.window_start
    if a.since:
        from ...util import parse_time
        since = parse_time(a.since, cfg.tz_offset) or since
    else:
        since = st.effective_since("x")

    if not a.dry_run:
        st.mark_started("x")
    rows = asyncio.run(run(cfg, scrolls=a.scrolls, max_queries=a.max_queries,
                           since=since, dry_run=a.dry_run))
    if rows:
        out = cfg.raw_dir / "x" / f"search_{datetime.now():%Y%m%d-%H%M%S}.jsonl"
        n = jsonl_write(out, rows)
        log(f"wrote {n} -> {out}")
        if not a.dry_run:
            st.mark_finished("x", stats={"search_rows": n}, success=True)
    elif not a.dry_run:
        st.mark_finished("x", stats={"search_rows": 0}, success=True)


if __name__ == "__main__":
    main()
