"""Incremental crawl state.

Purpose: make every run pick up where the last successful run stopped, with a
small overlap so late comments and edits are not missed.
"""
from __future__ import annotations

import time
from pathlib import Path

from .util import json_read, json_write

VERSION = 1


class CrawlState:
    def __init__(self, path: str | Path, overlap_hours: int = 6, project_since: int = 0):
        self.path = Path(path)
        self.overlap = int(overlap_hours) * 3600
        self.project_since = project_since
        self.data = json_read(self.path, default=None) or {"version": VERSION, "platforms": {}}
        self.data.setdefault("version", VERSION)
        self.data.setdefault("platforms", {})

    def save(self) -> None:
        json_write(self.path, self.data)

    def _p(self, platform: str) -> dict:
        return self.data["platforms"].setdefault(platform, {
            "runs": 0,
            "last_started": 0,
            "last_finished": 0,
            "last_success": 0,
            "cursor": {},
            "stats": {},
        })

    def effective_since(self, platform: str) -> int:
        """Start time for the next crawl (epoch seconds)."""
        p = self._p(platform)
        last = int(p.get("last_success") or 0)
        if last:
            return max(self.project_since, last - self.overlap)
        return self.project_since

    def mark_started(self, platform: str) -> int:
        now = int(time.time())
        p = self._p(platform)
        p["runs"] = int(p.get("runs") or 0) + 1
        p["last_started"] = now
        self.save()
        return now

    def mark_finished(self, platform: str, stats: dict | None = None,
                      success: bool = True, cursor: dict | None = None) -> None:
        now = int(time.time())
        p = self._p(platform)
        p["last_finished"] = now
        if success:
            p["last_success"] = now
        if stats is not None:
            p["stats"] = stats
        if cursor is not None:
            p["cursor"] = cursor
        self.save()

    def cursor(self, platform: str) -> dict:
        return self._p(platform).get("cursor") or {}

    def set_cursor(self, platform: str, cursor: dict) -> None:
        self._p(platform)["cursor"] = cursor
        self.save()

    def summary(self) -> dict:
        return self.data
