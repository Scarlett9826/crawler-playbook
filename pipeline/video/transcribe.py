"""Audio -> timestamped transcript with faster-whisper.

Input : data/raw/video/audio/*.m4a
Output: data/raw/video/tx/<name>.json  ([{"s":0.0,"e":1.2,"t":"..."}])
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path

from ..config import Config


def get_model(name: str, device: str = "cpu"):
    from faster_whisper import WhisperModel
    return WhisperModel(name, device=device, compute_type="int8", cpu_threads=4)


def transcribe(model, path: str, language: str = "zh", prompt: str = "") -> list[dict]:
    segs, _ = model.transcribe(path, language=language, initial_prompt=prompt,
                               vad_filter=True, beam_size=5)
    return [{"s": round(s.start, 1), "e": round(s.end, 1), "t": s.text.strip()}
            for s in segs]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--audio-dir", default="data/raw/video/audio")
    ap.add_argument("--out-dir", default="data/raw/video/tx")
    ap.add_argument("--model", default=os.environ.get("WHISPER_MODEL", "small"))
    ap.add_argument("--language", default=None)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()

    cfg = Config(a.project)
    from ..config import resolve
    audio_dir = resolve(a.audio_dir)
    out_dir = resolve(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lang = a.language or ((cfg.project.get("video") or {}).get("languages") or ["zh"])[0]
    prompt = "以下是关于大模型、Agent、编程、跑分、开源、价格、稳定性的技术讨论。"
    files = sorted(glob.glob(str(audio_dir / "*.m4a")) + glob.glob(str(audio_dir / "*.mp3")))
    if a.limit:
        files = files[:a.limit]
    model = get_model(a.model)
    for i, f in enumerate(files, 1):
        out = out_dir / (Path(f).stem + ".json")
        if out.exists():
            continue
        try:
            segs = transcribe(model, f, lang, prompt)
        except Exception as e:
            print(f"[{i}/{len(files)}] fail {f}: {str(e)[:120]}")
            continue
        out.write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")
        print(f"[{i}/{len(files)}] {Path(f).name} -> {len(segs)} segments")


if __name__ == "__main__":
    main()
