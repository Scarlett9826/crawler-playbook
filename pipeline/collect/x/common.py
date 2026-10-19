"""Shared X / Twitter helpers: auth, response capture, tweet normalization."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from ...config import Config
from ...util import parse_time

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} [x] {msg}", flush=True)


def tokens(cfg: Config) -> tuple[str, str]:
    auth = cfg.env.get("X_AUTH_TOKEN", "").strip()
    ct0 = cfg.env.get("X_CT0_TOKEN", "").strip()
    if not auth or not ct0:
        raise SystemExit(
            "Missing X_AUTH_TOKEN / X_CT0_TOKEN. Put them in .env "
            "(DevTools -> Application -> Cookies -> x.com).")
    return auth, ct0


async def new_context(pw, cfg: Config, headless: bool = False):
    auth, ct0 = tokens(cfg)
    browser = await pw.chromium.launch(headless=headless)
    ctx = await browser.new_context(user_agent=UA, locale="en-US",
                                    viewport={"width": 1280, "height": 1000})
    await ctx.add_cookies([
        {"name": "auth_token", "value": auth, "domain": ".x.com",
         "path": "/", "httpOnly": True, "secure": True},
        {"name": "ct0", "value": ct0, "domain": ".x.com",
         "path": "/", "secure": True},
    ])
    return browser, ctx


def since_str(epoch: int, tz_offset: int = 8) -> str:
    tz = timezone(timedelta(hours=tz_offset))
    return datetime.fromtimestamp(epoch, tz).strftime("%Y-%m-%d")


def walk_tweets(obj: Any, acc: list[dict]) -> None:
    """Recursively collect Tweet result objects from GraphQL JSON."""
    if isinstance(obj, dict):
        tn = obj.get("__typename")
        if tn == "TweetWithVisibilityResults" and isinstance(obj.get("tweet"), dict):
            walk_tweets(obj["tweet"], acc)
            return
        if tn == "Tweet" and isinstance(obj.get("legacy"), dict):
            acc.append(obj)
        for v in obj.values():
            walk_tweets(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            walk_tweets(v, acc)


def media_from(res: dict) -> list[dict]:
    """Extract images / videos / gifs, including video variants."""
    leg = res.get("legacy") or {}
    ents = leg.get("extended_entities") or leg.get("entities") or {}
    out = []
    for m in ents.get("media") or []:
        info = m.get("video_info") or {}
        variants = []
        for v in info.get("variants") or []:
            variants.append({
                "url": v.get("url"),
                "bitrate": v.get("bitrate"),
                "content_type": v.get("content_type"),
            })
        out.append({
            "type": m.get("type"),
            "url": m.get("media_url_https"),
            "expanded_url": m.get("expanded_url"),
            "alt_text": m.get("ext_alt_text"),
            "duration_ms": info.get("duration_millis"),
            "variants": variants,
        })
    return out


def normalize_tweet(res: dict, **extra) -> dict:
    leg = res.get("legacy") or {}
    user = (res.get("core") or {}).get("user_results", {}).get("result", {})
    ucore = user.get("core") or {}
    screen_name = ucore.get("screen_name") or (user.get("legacy") or {}).get("screen_name")
    name = ucore.get("name") or (user.get("legacy") or {}).get("name")

    text = leg.get("full_text") or ""
    note = ((res.get("note_tweet") or {}).get("note_tweet_results") or {}).get("result") or {}
    if note.get("text"):
        text = note["text"]

    tid = leg.get("id_str") or res.get("rest_id")
    media = media_from(res)
    d = {
        "platform": "X",
        "kind": "tweet",
        "id": tid,
        "parent_id": "",
        "title": "",
        "text": text,
        "author": screen_name,
        "name": name,
        "followers": (user.get("legacy") or {}).get("followers_count"),
        "verified": user.get("is_blue_verified"),
        "created_at": leg.get("created_at"),
        "time": parse_time(leg.get("created_at")),
        "like": leg.get("favorite_count"),
        "reply_count": leg.get("reply_count"),
        "retweet_count": leg.get("retweet_count"),
        "quote_count": leg.get("quote_count"),
        "views": (res.get("views") or {}).get("count"),
        "lang": leg.get("lang"),
        "conversation_id": leg.get("conversation_id_str"),
        "in_reply_to": leg.get("in_reply_to_status_id_str"),
        "quoted_id": leg.get("quoted_status_id_str"),
        "url": f"https://x.com/{screen_name}/status/{tid}",
        "media": media,
        "has_video": any(m.get("type") in ("video", "animated_gif") for m in media),
        "crawled_at": int(datetime.now(timezone.utc).timestamp()),
    }
    d.update(extra)
    return d


async def capture(page, url: str, marker: str, scrolls: int,
                  wait: float = 2.0, click_labels: tuple[str, ...] = ()) -> list[dict]:
    """Open a page and capture JSON responses whose URL contains `marker`."""
    got: list[dict] = []

    async def on_resp(resp):
        if marker in resp.url and resp.status == 200:
            try:
                got.append(await resp.json())
            except Exception:
                pass

    page.on("response", on_resp)
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"open failed: {str(e)[:100]}")
    await asyncio.sleep(3)
    for _ in range(max(1, scrolls)):
        await page.mouse.wheel(0, 3500)
        await asyncio.sleep(wait)
        for label in click_labels:
            try:
                btn = page.get_by_text(label, exact=False)
                if await btn.count():
                    await btn.first.click(timeout=1200)
                    await asyncio.sleep(1.2)
            except Exception:
                pass
    try:
        page.remove_listener("response", on_resp)
    except Exception:
        pass
    return got


def dedupe_by_id(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for r in rows:
        if not r.get("id") or r["id"] in seen:
            continue
        seen.add(r["id"])
        out.append(r)
    return out
