"""WeChat public-account articles via Sogou WeChat search.

Requires a persistent browser profile (login/cookies are kept there).
Captcha is solved manually in the opened browser window.

Output: data/raw/wechat/articles_<YYYYmmdd-HHMMSS>.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from playwright.async_api import async_playwright

from ...config import Config
from ...state import CrawlState
from ...util import jsonl_write, parse_time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} [wechat] {msg}", flush=True)


async def wait_results(page, keyword: str, max_wait: int = 600) -> bool:
    waited = 0
    prompted = False
    while waited < max_wait:
        html = await page.content()
        if "antispider" in page.url or "请依次点击" in html or "antispider" in html:
            if not prompted:
                log(f"captcha for「{keyword}」— solve it in the browser window ({max_wait}s)")
                prompted = True
            await asyncio.sleep(3)
            waited += 3
            continue
        if await page.locator("ul.news-list li").count() > 0:
            return True
        await asyncio.sleep(3)
        waited += 3
    return False


async def parse_search(page) -> list[dict]:
    return await page.eval_on_selector_all(
        "ul.news-list li",
        """els => els.map(li => {
            const a = li.querySelector('h3 a');
            const acc = li.querySelector('a.account') || li.querySelector('.s-p a');
            const s2 = li.querySelector('.s2');
            const info = li.querySelector('.txt-info');
            return {
                title: a ? a.innerText.trim() : '',
                link: a ? a.getAttribute('href') : '',
                account: acc ? acc.innerText.trim() : '',
                date: s2 ? s2.innerText.trim() : '',
                summary: info ? info.innerText.trim() : ''
            };
        }).filter(x => x.title)""")


async def fetch_article(page, link: str) -> dict:
    if link.startswith("/"):
        link = "https://weixin.sogou.com" + link
    try:
        await page.goto(link, wait_until="domcontentloaded", timeout=25000)
        try:
            await page.wait_for_url("**mp.weixin.qq.com/**", timeout=12000)
        except Exception:
            pass
        data = await page.evaluate(
            """() => {
                const t = document.querySelector('#activity-name')?.innerText?.trim() || '';
                const acc = document.querySelector('#js_name')?.innerText?.trim() || '';
                const tm = document.querySelector('#publish_time')?.innerText?.trim() || '';
                const au = document.querySelector('#js_author_name')?.innerText?.trim() || '';
                const body = document.querySelector('#js_content')?.innerText?.trim() || '';
                return {title: t, account: acc, publish_time: tm, author: au, content: body};
            }"""
        )
        data["url"] = page.url
        return data
    except Exception as e:
        return {"url": link, "error": str(e)[:200]}


async def run(cfg: Config, *, max_per_query: int, dry_run: bool = False) -> list[dict]:
    queries = cfg.queries("wechat") or list(cfg.keywords().get("core") or [])
    if dry_run:
        for q in queries:
            log(f"query: {q}")
        return []

    profile = cfg.p(".profiles", "wechat")
    profile.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    async with async_playwright() as pw:
        try:
            ctx = await pw.chromium.launch_persistent_context(
                str(profile), channel="chrome", headless=False,
                user_agent=UA, locale="zh-CN",
                viewport={"width": 1280, "height": 900})
        except Exception:
            ctx = await pw.chromium.launch_persistent_context(
                str(profile), headless=False, user_agent=UA, locale="zh-CN")
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        for q in queries:
            log(f"search: {q}")
            url = f"https://weixin.sogou.com/weixin?type=2&query={q}&ie=utf8"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                log(f"open failed: {e}")
                continue
            if not await wait_results(page, q):
                log(f"no results for「{q}」")
                continue
            items = (await parse_search(page))[:max_per_query]
            for it in items:
                art = await fetch_article(page, it["link"])
                it.update(art)
                it.update({
                    "platform": "微信公众号", "kind": "article",
                    "id": "", "parent_id": "", "keyword": q,
                    "time": parse_time(art.get("publish_time") or it.get("date"), 8),
                    "crawled_at": int(datetime.now().timestamp()),
                })
                if not it.get("content"):
                    log(f"  skip (no body): {it.get('title','')[:40]}")
                    continue
                rows.append(it)
                log(f"  · {it['title'][:40]} | {it.get('account','')} | {len(it.get('content',''))}字")
                await asyncio.sleep(1.2)
            await asyncio.sleep(1.5)
        await asyncio.sleep(2)
        await ctx.close()
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--max-per-query", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    pc = cfg.platform_config("wechat")
    st = CrawlState(cfg.state_file,
                    overlap_hours=int((cfg.project.get("crawl") or {}).get("overlap_hours", 6)),
                    project_since=cfg.window_start)
    if not a.dry_run:
        st.mark_started("wechat")
    try:
        rows = asyncio.run(run(
            cfg, max_per_query=a.max_per_query or int(pc.get("max_articles_per_query", 10)),
            dry_run=a.dry_run))
        if rows:
            out = cfg.raw_dir / "wechat" / f"articles_{datetime.now():%Y%m%d-%H%M%S}.jsonl"
            jsonl_write(out, rows)
            log(f"wrote {len(rows)} -> {out}")
        if not a.dry_run:
            st.mark_finished("wechat", stats={"articles": len(rows)}, success=True)
    except Exception:
        if not a.dry_run:
            st.mark_finished("wechat", success=False)
        raise


if __name__ == "__main__":
    main()
