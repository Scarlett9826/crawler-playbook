"""Resolve authors to canonical KOL identities."""
from __future__ import annotations

from ..config import Config


class Registry:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.by_handle: dict[str, dict] = {}
        for k in (cfg.kol.get("kols") or []):
            for platform, handle in (k.get("handles") or {}).items():
                self.by_handle[f"{platform}:{str(handle).lower()}"] = k
            self.by_handle[f"*:{str(k.get('name','')).lower()}"] = k

    def resolve(self, platform: str, author: str | None) -> dict | None:
        if not author:
            return None
        a = str(author).lower().lstrip("@")
        return self.by_handle.get(f"{platform}:{a}") or self.by_handle.get(f"*:{a}")

    def identity(self, platform: str, author: str | None) -> dict:
        hit = self.resolve(platform, author)
        if hit:
            return {
                "kol_id": hit.get("id"),
                "name": hit.get("name") or author,
                "independence": hit.get("independence", "unknown"),
                "notes": hit.get("notes", ""),
                "known": True,
            }
        return {
            "kol_id": f"unknown:{platform}:{str(author).lower()}",
            "name": author or "",
            "independence": "unknown",
            "notes": "",
            "known": False,
        }

    @property
    def threshold(self) -> int:
        return int(self.cfg.kol.get("candidate_threshold", 3))
