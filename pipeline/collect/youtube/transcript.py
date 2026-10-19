"""YouTube transcript: subtitles first, Whisper fallback.

Input : data/raw/youtube/search_*.jsonl
Output: data/raw/youtube/videos_<stamp>.jsonl  (records + transcript)
        data/raw/video/audio/youtube_<id>.m4a    (only when Whisper is needed)
"""
from __future__ import annotations

import argparse
import glob
import subprocess
from datetime import datetime
from pathlib import Path

from ...config import Config
from ...util import jsonl_read, jsonl_write
from ...video.transcribe import get_model, transcribe

LANGS = ["zh", "zh-Hans", "en"]


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} [yt-sub] {msg}", flush=True)


def subtitle(video_id: str, languages: list[str]) -> list[dict] | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:
        return None
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=languages)
        return [{"s": round(s.start, 1), "e": round(s.start + s.duration, 1),
                 "t": s.text.strip()} for s in fetched]
    except Exception as e:
        log(f"  subtitle miss {video_id}: {type(e).__name__}")
        return None


def download_audio(url: str, out_stem: Path) -> str | None:
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["yt-dlp", "-q", "--no-warnings", "-f", "ba/b",
           "-x", "--audio-format", "m4a", "--audio-quality", "5",
           "-o", str(out_stem) + ".%(ext)s", url]
    try:
        subprocess.run(cmd, check=True, timeout=900,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        log(f"  audio fail {url}: {str(e)[:100]}")
        return None
    for p in out_stem.parent.glob(out_stem.name + ".*"):
        return str(p)
    return None


def collect(cfg: Config) -> list[dict]:
    rows: dict[str, dict] = {}
    for f in sorted(glob.glob(str(cfg.raw_dir / "youtube" / "*.jsonl"))):
        name = Path(f).name
        if name.startswith("comments_"):
            continue
        for d in jsonl_read(f):
            if d.get("kind") == "comment":
                continue
            if d.get("id"):
                rows[d["id"]] = d
    return list(rows.values())


def _done(cfg: Config) -> set[str]:
    done: set[str] = set()
    for f in glob.glob(str(cfg.raw_dir / "youtube" / "videos_*.jsonl")):
        for d in jsonl_read(f):
            if d.get("transcript"):
                done.add(str(d.get("id")))
    return done


def run(cfg: Config, *, limit: int | None = None, whisper: bool = True,
        dry_run: bool = False, refresh: bool = False) -> list[dict]:
    rows = collect(cfg)
    done = set() if refresh else _done(cfg)
    rows = [r for r in rows if str(r.get("id")) not in done]
    if limit:
        rows = rows[:limit]
    languages = (cfg.project.get("video") or {}).get("languages") or LANGS
    audio_dir = cfg.raw_dir / "video" / "audio"
    model = None
    out = []

    for i, r in enumerate(rows, 1):
        vid = r.get("id")
        if dry_run:
            log(f"would fetch {vid} (subtitle first)")
            continue
        tx = subtitle(vid, languages)
        source = "subtitle"
        if tx is None and whisper:
            audio = download_audio(r.get("url"), audio_dir / f"youtube_{vid}")
            if audio:
                if model is None:
                    model = get_model("small")
                tx = transcribe(model, audio, language=languages[0],
                                prompt="以下是关于大模型、Agent、编程、跑分、开源、价格、稳定性的技术讨论。")
                source = "whisper"
        rr = dict(r)
        rr["transcript"] = tx or []
        rr["transcript_source"] = source if tx else ""
        out.append(rr)
        log(f"[{i}/{len(rows)}] {vid} {source if tx else 'no transcript'} ({len(tx or [])})")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-whisper", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    rows = run(cfg, limit=a.limit, whisper=not a.no_whisper, dry_run=a.dry_run, refresh=a.refresh)
    if rows and not a.dry_run:
        out = cfg.raw_dir / "youtube" / f"videos_{datetime.now():%Y%m%d-%H%M%S}.jsonl"
        jsonl_write(out, rows)
        log(f"wrote {len(rows)} -> {out}")


if __name__ == "__main__":
    main()
