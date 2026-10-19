"""Reserved interface for on-screen text (OCR).

Phase 1 ships a Noop provider. To enable OCR later:
  - set video.frame_text.enabled: true
  - set video.frame_text.provider: rapidocr
  - implement RapidOCRProvider.extract()

The showcase extractor already accepts `frame_text`; no schema change needed.
"""
from __future__ import annotations

from typing import Protocol

from ..config import Config


class FrameTextProvider(Protocol):
    def extract(self, video: dict) -> list[dict]:
        """Return [{"t": seconds, "text": "..."}] or []."""
        ...


class NoopProvider:
    def extract(self, video: dict) -> list[dict]:
        return []


class RapidOCRProvider:  # pragma: no cover - placeholder
    def __init__(self) -> None:
        raise NotImplementedError(
            "OCR is reserved for a later phase. Install RapidOCR and implement extract().")

    def extract(self, video: dict) -> list[dict]:
        return []


def get_provider(cfg: Config) -> FrameTextProvider:
    v = (cfg.project.get("video") or {}).get("frame_text") or {}
    if not v.get("enabled"):
        return NoopProvider()
    if v.get("provider") == "rapidocr":
        return RapidOCRProvider()
    return NoopProvider()


def attach(cfg: Config, video: dict) -> dict:
    video["frame_text"] = get_provider(cfg).extract(video)
    return video
