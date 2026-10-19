"""Official / media claims extracted from relay-style videos.

These are NOT KOL self-tests. They are kept separately so the report can compare
"what was claimed" with "what self-testers found" and "what users said".
"""
from __future__ import annotations

import argparse
import json
import re

from ..config import Config
from ..util import jsonl_read, jsonl_write
from .showcase import _tx

SYSTEM = """你是声明抽取器。视频是媒体转述或官方口径，不是自测。
只输出 JSON 数组，每项：
{"claim_code":"A|B|C|D|E1|E2|F|G|H|I|J|K|other",
 "claim":"一句话声明",
 "metric":"分数/排名/成本/速度/通过率/其他",
 "value":"声明中的数值或结论",
 "quote":"转写原话 ≤60字",
 "timestamp":0,
 "evidence":"explicit|vague"}
不要加入你自己的判断。"""


def heuristic(cfg: Config, video: dict) -> list[dict]:
    tx = _tx(video)
    out = []
    claims = cfg.taxonomy.get("claims") or {}
    for code, meta in claims.items():
        name = str(meta.get("name") or "")
        if name and name.split("/")[0].strip() in tx:
            out.append({
                "claim_code": code, "claim": name, "metric": "其他",
                "value": "", "quote": "", "timestamp": 0, "evidence": "vague",
            })
    return out


def extract(cfg: Config, video: dict, call_llm=None) -> list[dict]:
    if call_llm is None:
        return heuristic(cfg, video)
    user = json.dumps({"title": video.get("title"),
                       "description": video.get("description"),
                       "transcript": _tx(video)}, ensure_ascii=False)
    txt = call_llm(SYSTEM, user)
    m = re.search(r"\[.*\]", txt or "", re.S)
    if not m:
        return heuristic(cfg, video)
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, list) else heuristic(cfg, video)
    except json.JSONDecodeError:
        return heuristic(cfg, video)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    from ..llm import for_config
    cfg = Config(a.project)
    rows = list(jsonl_read(cfg.video_dir / "triage.jsonl"))
    out = []
    for v in rows:
        route = ((v.get("triage") or {}).get("route") or {}).get("route")
        if route != "claims_media":
            continue
        for c in extract(cfg, v, None if a.offline else for_config(cfg)):
            c["video"] = {"platform": v.get("platform"), "id": v.get("id"),
                          "url": v.get("url"), "title": v.get("title")}
            out.append(c)
    jsonl_write(cfg.video_dir / "claims_media.jsonl", out)
    print(f"claims={len(out)}")


if __name__ == "__main__":
    main()
