"""Download audio for a video manifest.

Works for YouTube, X, Bilibili, Douyin and anything else yt-dlp supports.
For Douyin, if yt-dlp fails, pass a direct media URL in the manifest `dl` field.

Manifest (JSONL) fields: platform, id, url, [dl]
Output: data/raw/video/audio/<platform>_<id>.m4a
"""
from __future__ import annotations

import argparse
import shutil
import subprocess

from ..config import Config
from ..util import jsonl_read, jsonl_write


def download(url: str, out_stem) -> str | None:
    if not shutil.which("yt-dlp"):
        raise SystemExit("yt-dlp missing")
    cmd = ["yt-dlp", "-q", "--no-warnings", "-f", "ba/b",
           "-x", "--audio-format", "m4a", "--audio-quality", "5",
           "-o", str(out_stem) + ".%(ext)s", url]
    try:
        subprocess.run(cmd, check=True, timeout=900,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"  failed {url}: {str(e)[:120]}")
        return None
    for p in out_stem.parent.glob(out_stem.name + ".*"):
        if p.suffix in (".m4a", ".mp3", ".opus", ".webm", ".wav"):
            return str(p)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--input", default="data/raw/video/index.jsonl")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    from ..config import resolve
    src = resolve(a.input)
    rows = list(jsonl_read(src))
    if a.limit:
        rows = rows[:a.limit]
    out_dir = cfg.raw_dir / "video" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, r in enumerate(rows, 1):
        stem = out_dir / f'{r.get("platform","video")}_{r.get("id","x")}'
        url = r.get("dl") or r.get("url")
        if a.dry_run:
            print(f"would download {url}")
            continue
        path = download(url, stem)
        rr = dict(r)
        rr["audio"] = path or ""
        manifest.append(rr)
        print(f"[{i}/{len(rows)}] {r.get('id')} -> {path}")
    if manifest:
        jsonl_write(cfg.raw_dir / "video" / "index.audio.jsonl", manifest)


if __name__ == "__main__":
    main()
