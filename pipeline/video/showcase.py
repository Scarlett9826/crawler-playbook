"""Structured comparison showcases.

A showcase only exists when the video contains a self-tested, same-task
comparison of two or more models. Everything else is routed elsewhere.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict

from ..config import Config
from ..util import clean_text, jsonl_read, json_write, jsonl_write

SYSTEM = """你是视频证据抽取器。从转写里抽取“同题多模型对比”的 showcase。
只输出 JSON 数组；没有对比就输出 []。每个元素：
{
 "task": "测试任务（前端复刻/3D建模/代码修复/长文总结/跑分横评等）",
 "models": [{"raw":"转写里的名字","canonical":"规范名"}],
 "setup": {"prompt":"","dataset":"","budget":"","runs":null,"notes":""},
 "results": [{"model":"","metric":"耗时/成本/通过率/主观评分","value":"","unit":"","evidence":"explicit|vague"}],
 "verdict": {"winner":"","margin":"","summary":""},
 "timestamps": {"start":0,"end":0},
 "quotes": [{"t":0,"text":""}],
 "caveats": [],
 "confidence": "high|medium|low"
}
要求：
- 只抽取视频里真实说出来的对比，不要脑补
- 口头数字标 explicit；印象式结论标 vague
- 时间戳来自转写行首的 [秒]
- 没有明确结果就降低 confidence"""


def _tx(video: dict) -> str:
    return "\n".join(f"[{s.get('s', 0):.0f}] {s.get('t','')}"
                     for s in (video.get("transcript") or []))[:20000]


TASK = re.compile(r"前端|网页|3D|建模|代码|编程|长文|总结|横评|跑分|图片|视频|Agent|工具调用|数学|推理", re.I)


def infer_task(video: dict) -> str:
    blob = f'{video.get("title","")} {video.get("description","")} ' + " ".join(
        s.get("t", "") for s in (video.get("transcript") or []))
    m = TASK.search(blob)
    return m.group(0) if m else "未标注任务"


def _span(video: dict) -> tuple[int, int]:
    ts = [float(s.get("s") or 0) for s in (video.get("transcript") or [])]
    return (int(min(ts)), int(max(ts))) if ts else (0, 0)


def heuristic(cfg: Config, video: dict, tri: dict) -> list[dict]:
    models = (tri.get("showcase") or {}).get("models_tested") or []
    if len(models) < 2:
        return []
    start, end = _span(video)
    return [{
        "task": video.get("task") or infer_task(video),
        "models": [{"raw": m, "canonical": m} for m in models],
        "setup": {"prompt": "", "dataset": "", "budget": "", "runs": None, "notes": ""},
        "results": [],
        "verdict": {"winner": "", "margin": "", "summary": ""},
        "timestamps": {"start": start, "end": end},
        "quotes": [],
        "caveats": ["heuristic extraction; no explicit result parsed"],
        "confidence": "low",
    }]


def extract(cfg: Config, video: dict, tri: dict, call_llm=None) -> list[dict]:
    if (tri.get("showcase") or {}).get("present") != "yes":
        return []
    if call_llm is None:
        return heuristic(cfg, video, tri)
    user = json.dumps({
        "title": video.get("title"), "description": video.get("description"),
        "transcript": _tx(video), "heuristic_models": (tri.get("showcase") or {}).get("models_tested"),
    }, ensure_ascii=False)
    txt = call_llm(SYSTEM, user)
    m = re.search(r"\[.*\]", txt or "", re.S)
    if not m:
        return heuristic(cfg, video, tri)
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return heuristic(cfg, video, tri)
    return data if isinstance(data, list) else heuristic(cfg, video, tri)


def validate(s: dict, video: dict, cfg: Config) -> dict:
    s.setdefault("models", [])
    s.setdefault("results", [])
    s.setdefault("quotes", [])
    s.setdefault("caveats", [])
    s.setdefault("timestamps", _span(video))
    s.setdefault("confidence", "low")
    start = int((s.get("timestamps") or {}).get("start") or 0)
    end = int((s.get("timestamps") or {}).get("end") or 0)
    if end and start > end:
        start, end = end, start
    s["timestamps"] = {"start": start, "end": end}

    if len(s["models"]) < int((cfg.routing.get("triage") or {}).get("min_models_for_showcase", 2)):
        s["confidence"] = "low"
        s["caveats"].append("fewer than 2 models")
    if not s["results"]:
        s["confidence"] = "low" if s["confidence"] == "high" else s["confidence"]
        s["caveats"].append("no explicit results")
    # resolve model names
    aliases = {}
    for m in (cfg.models.get("models") or []):
        for a in m.get("aliases") or [m.get("canonical")]:
            aliases[str(a).lower()] = m.get("canonical")
    for m in s["models"]:
        raw = str(m.get("raw") or m.get("canonical") or "")
        m["canonical"] = m.get("canonical") or aliases.get(raw.lower(), raw)
    s["video"] = {
        "platform": video.get("platform"), "id": video.get("id"),
        "url": video.get("url"), "title": video.get("title"),
        "author": video.get("author"), "published_at": video.get("time"),
    }
    s["showcase_id"] = f'{video.get("platform")}_{video.get("id")}_{start}'
    return s


def aggregate(showcases: list[dict]) -> dict:
    by_task = defaultdict(list)
    for s in showcases:
        by_task[s.get("task") or "未标注任务"].append({
            "showcase_id": s.get("showcase_id"),
            "models": [m.get("canonical") for m in s.get("models", [])],
            "results": s.get("results"),
            "verdict": s.get("verdict"),
            "confidence": s.get("confidence"),
            "video": s.get("video"),
            "timestamps": s.get("timestamps"),
        })
    return {"tasks": dict(by_task), "total": len(showcases)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--input", default=None, help="video JSONL with triage field")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()

    from ..llm import for_config
    cfg = Config(a.project)
    cfg.ensure_dirs()
    src = a.input or (cfg.video_dir / "triage.jsonl")
    rows = list(jsonl_read(src))
    out = []
    for v in rows:
        tri = v.get("triage") or {}
        items = extract(cfg, v, tri, None if a.offline else for_config(cfg))
        for s in items:
            out.append(validate(s, v, cfg))
    jsonl_write(cfg.video_dir / "showcases.jsonl", out)
    json_write(cfg.metrics_dir / "showcases.json", aggregate(out))
    print(f"showcases={len(out)} -> {cfg.video_dir / 'showcases.jsonl'}")


if __name__ == "__main__":
    main()
