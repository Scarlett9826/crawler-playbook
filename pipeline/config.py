"""Configuration loading and path resolution.

Everything is relative to the repository root, so scripts work on any machine.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from .util import compile_any, parse_time

ROOT = Path(__file__).resolve().parents[1]


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_env(path: Path | None = None) -> dict[str, str]:
    """Load KEY=VALUE from .env without touching os.environ."""
    env: dict[str, str] = {}
    p = path or (ROOT / ".env")
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k, v in os.environ.items():
        env.setdefault(k, v)
    return env


def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def resolve(path: str | Path, base: Path = ROOT) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (base / p)


class Config:
    def __init__(self, project_path: str | Path | None = None):
        self.root = ROOT
        self.env = load_env()

        if project_path is None:
            project_path = self.env.get("CP_PROJECT")
        if project_path is None:
            default = ROOT / "config" / "project.yaml"
            project_path = default if default.exists() else ROOT / "config" / "project.example.yaml"

        self.project_path = resolve(project_path)
        self.project = _read_yaml(self.project_path)
        self.files = self.project.get("files", {})

        self.platforms = _read_yaml(resolve(
            self.files.get("platforms", "config/platforms.yaml"))).get("platforms", {})
        self.taxonomy = _read_yaml(resolve(self.files.get("taxonomy", "config/taxonomy.example.yaml")))
        self.models = _read_yaml(resolve(self.files.get("models", "config/models.yaml")))
        self.kol = _read_yaml(resolve(self.files.get("kol", "config/kol.yaml")))
        self.dimensions = _read_yaml(resolve(
            self.files.get("dimensions", "config/video_dimensions.yaml")))
        self.routing = _read_yaml(resolve(
            self.files.get("routing", "config/video_routing.yaml")))

        self.tz_offset = self._tz_offset()
        self.window_start, self.window_end = self._window()

    # ---------- basics ----------
    def _tz_offset(self) -> int:
        name = (self.project.get("project") or {}).get("timezone", "Asia/Shanghai")
        if name in ("Asia/Shanghai", "Asia/Chongqing", "PRC"):
            return 8
        try:
            from zoneinfo import ZoneInfo
            now = datetime.now(ZoneInfo(name))
            return int(now.utcoffset().total_seconds() // 3600)
        except Exception:
            return 8

    def _window(self) -> tuple[int, int]:
        w = (self.project.get("project") or {}).get("date_window") or {}
        since = parse_time(w.get("since"), self.tz_offset) if w.get("since") else None
        until = parse_time(w.get("until"), self.tz_offset) if w.get("until") else None
        if until:
            until += 86400 - 1  # inclusive day
        now = int(datetime.now(timezone.utc).timestamp())
        return (since or 0, until or now)

    def date_label(self, ts: int | None) -> str:
        if not ts:
            return ""
        tz = timezone(timedelta(hours=self.tz_offset))
        return datetime.fromtimestamp(ts, tz).strftime("%Y-%m-%d %H:%M")

    # ---------- lookups ----------
    def platform(self, name: str) -> dict:
        return self.platforms.get(name, {})

    def platform_config(self, name: str) -> dict:
        return (self.project.get("platforms") or {}).get(name, {})

    def enabled_platforms(self) -> list[str]:
        out = []
        for name in (self.project.get("platforms") or {}):
            if self.platform_config(name).get("enabled", False):
                out.append(name)
        return out

    def keywords(self) -> dict:
        return self.project.get("keywords") or {}

    def queries(self, platform: str) -> list[str]:
        q = self.keywords().get("queries") or {}
        value = q.get(platform, [])
        if isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]
        return list(value)

    def relevance_patterns(self) -> tuple[re.Pattern | None, re.Pattern | None]:
        kw = self.keywords()
        include = list(kw.get("core") or []) + list(kw.get("include") or [])
        exclude = list(kw.get("exclude") or [])
        return compile_any(include), compile_any(exclude)

    def llm(self) -> dict:
        llm = dict(self.project.get("llm") or {})
        key_env = llm.pop("api_key_env", "LLM_API_KEY")
        llm["api_key"] = self.env.get(key_env, "")
        return llm

    # ---------- paths ----------
    def p(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    @property
    def media_crawler_dir(self) -> Path:
        return self.p("vendors", "MediaCrawler")

    @property
    def media_crawler_data(self) -> Path:
        return self.media_crawler_dir / "data"

    @property
    def raw_dir(self) -> Path:
        return self.p("data", "raw")

    @property
    def normalized_dir(self) -> Path:
        return self.p("data", "normalized")

    @property
    def labels_dir(self) -> Path:
        return self.p("data", "labels")

    @property
    def metrics_dir(self) -> Path:
        return self.p("data", "metrics")

    @property
    def reports_dir(self) -> Path:
        return self.p("data", "reports")

    @property
    def video_dir(self) -> Path:
        return self.p("data", "video")

    @property
    def kol_dir(self) -> Path:
        return self.p("data", "kol")

    @property
    def state_file(self) -> Path:
        crawl = self.project.get("crawl") or {}
        return resolve(crawl.get("state_file", "data/state/crawl_state.json"))

    def ensure_dirs(self) -> None:
        for d in (self.raw_dir, self.normalized_dir, self.labels_dir,
                  self.metrics_dir, self.reports_dir, self.video_dir,
                  self.kol_dir, self.state_file.parent):
            d.mkdir(parents=True, exist_ok=True)

    def in_window(self, ts: int | None) -> bool | None:
        if not ts:
            return None
        return self.window_start <= ts <= self.window_end


def load(project_path: str | Path | None = None) -> Config:
    return Config(project_path)
