"""Minimal OpenAI-compatible chat client."""
from __future__ import annotations

import json
import time
import urllib.request

from .config import Config


def call(cfg: Config, system: str, user: str, *, timeout: int = 300) -> str | None:
    llm = cfg.llm()
    base = (llm.get("base_url") or "").rstrip("/")
    if not base or not llm.get("api_key"):
        return None
    body = json.dumps({
        "model": llm.get("model"),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": float(llm.get("temperature", 0)),
        "max_tokens": int(llm.get("max_tokens", 8000)),
    }).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions", body,
        {"Content-Type": "application/json",
         "Authorization": f"Bearer {llm['api_key']}"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  llm retry {i} {type(e).__name__} {str(e)[:100]}", flush=True)
            time.sleep(3 * (i + 1))
    return None


def for_config(cfg: Config):
    """Return a `call(system, user)` bound to this config."""
    def _call(system: str, user: str, **kw):
        return call(cfg, system, user, **kw)
    return _call
