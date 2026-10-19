"""Unified KOL evaluation extraction (text + video).

Text KOL posts come from data/labels/labels.jsonl where src=kol.
Video KOLs come from data/video/triage.jsonl. If an upstream summary exists it
is used; otherwise an LLM extracts dimensions directly from the transcript.

Output: data/kol/evals.jsonl
"""
from __future__ import annotations

import argparse
import json
import re

from ..config import Config
from ..util import jsonl_read, jsonl_write
from .registry import Registry

DIM_RULES = {
    "coding": ("编程", "代码", "coding", "程序"),
    "agent": ("agent", "工具调用", "智能体"),
    "reasoning": ("推理", "数学", "逻辑"),
    "speed": ("速度", "思考", "慢", "延迟", "耗时"),
    "price": ("价格", "便宜", "性价比", "成本", "贵"),
    "stability": ("空转", "死循环", "删库", "崩", "退化", "不稳定"),
    "long_context": ("长上下文", "长文本", "上下文"),
    "multimodal": ("多模态", "图片", "音频", "视频", "识图"),
    "instruction": ("指令遵循", "遵循", "不听"),
    "harness": ("客户端", "harness", "desktop", "专武", "agent 环境"),
    "design": ("前端", "设计", "审美", "3d", "建模"),
    "safety": ("审核", "敏感", "拦截"),
    "openness": ("开源", "权重", "许可", "mit"),
}

VIDEO_SYSTEM = """你是 KOL 评价抽取器。对象：{brand} 的 {product}。
根据视频转写，提炼这位 KOL 对产品的分维度评价。只输出 JSON：
{{
 "overall": {{"stance":"pos|neg|mix|neu","summary":"≤60字","recommendation":"use|conditional|avoid|unknown"}},
 "dimensions": [
   {{"dim":"{dims}","verdict":"pos|neg|mix|neu","strength":"strong|moderate|weak",
     "evidence":["带时间戳的原话，如 [123] ..."],"compared_to":["竞品规范名"]}}
 ],
 "claims": {{"代码":"buy|reject|neutral"}},
 "methodology": {{"tasks":[],"runs":null,"reproducible":"yes|no|unclear"}}
}}
要求：
- 只写视频里明确表达的评价，不要脑补
- 没有提到的维度不要输出
- 证据尽量带转写行首的时间戳
- 区分“模型本身”和“客户端/harness”的问题"""


def dims_from_topics(topics: list[str]) -> list[str]:
    blob = " ".join(str(t) for t in topics).lower()
    out = []
    for dim, kws in DIM_RULES.items():
        if any(k.lower() in blob for k in kws):
            out.append(dim)
    return out


def text_evals(cfg: Config, registry: Registry) -> list[dict]:
    rows = {}
    for r in jsonl_read(cfg.normalized_dir / "combined.jsonl"):
        key = f'{r.get("platform")}|{r.get("kind")}|{r.get("id")}|{(r.get("text") or "")[:40]}'
        rows[key] = r
    out = []
    for d in jsonl_read(cfg.labels_dir / "labels.jsonl"):
        if d.get("src") != "kol" or d.get("rel") != 1:
            continue
        r = rows.get(d.get("key"))
        if not r:
            continue
        ident = registry.identity(r.get("platform"), r.get("author"))
        dims = dims_from_topics(d.get("topics") or [])
        out.append({
            "source": "text",
            "kol": ident,
            "content": {
                "platform": r.get("platform"), "id": r.get("id"), "url": r.get("url"),
                "title": r.get("title"), "published_at": r.get("time"),
                "text": (r.get("text") or "")[:600],
            },
            "overall": {"stance": d.get("sent"), "summary": d.get("quote") or "",
                        "recommendation": "unknown"},
            "dimensions": [{"dim": x, "verdict": d.get("sent"), "strength": "moderate",
                            "evidence": [d.get("quote") or ""], "compared_to": d.get("comp") or []}
                           for x in dims],
            "claims": d.get("stance") or {},
            "methodology": {"tasks": [], "runs": None, "reproducible": "unclear"},
            "evidence_quality": "medium",
        })
    return out


def extract_video_llm(cfg: Config, row: dict, call_llm) -> dict:
    tx = "\n".join(f"[{s.get('s', 0):.0f}] {s.get('t','')}"
                   for s in (row.get("transcript") or []))[:20000]
    if not tx or call_llm is None:
        return {}
    project = cfg.project.get("project") or {}
    dims = "|".join((cfg.dimensions.get("dimensions") or {}).keys())
    system = VIDEO_SYSTEM.format(brand=project.get("brand", "品牌"),
                                 product=project.get("product", "产品"),
                                 dims=dims)
    user = json.dumps({
        "title": row.get("title"), "author": row.get("author"),
        "transcript": tx, "triage": row.get("triage"),
    }, ensure_ascii=False)
    txt = call_llm(system, user)
    m = re.search(r"\{.*\}", txt or "", re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def video_evals(cfg: Config, registry: Registry, call_llm=None) -> list[dict]:
    out = []
    for v in jsonl_read(cfg.video_dir / "triage.jsonl"):
        tri = v.get("triage") or {}
        ident = registry.identity(v.get("platform"), v.get("author"))
        is_kol = tri.get("content_type") == "kol_review" or ident.get("known")
        if not is_kol:
            continue
        summary = v.get("kol_eval_summary") or {}
        if not summary:
            summary = extract_video_llm(cfg, v, call_llm)
        out.append({
            "source": "video",
            "kol": ident,
            "content": {
                "platform": v.get("platform"), "id": v.get("id"), "url": v.get("url"),
                "title": v.get("title"), "published_at": v.get("time"),
                "timestamps": (tri.get("showcase") or {}).get("timestamps"),
            },
            "overall": summary.get("overall") or {
                "stance": "unknown", "summary": "", "recommendation": "unknown"},
            "dimensions": summary.get("dimensions") or [],
            "claims": summary.get("claims") or {},
            "methodology": summary.get("methodology") or {
                "tasks": [], "runs": None, "reproducible": "unclear"},
            "evidence_quality": ("high" if tri.get("confidence") == "high"
                                 else "low" if not summary.get("dimensions") else "medium"),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    cfg = Config(a.project)
    cfg.ensure_dirs()
    reg = Registry(cfg)
    llm = None
    if not a.offline:
        from ..llm import for_config
        llm = for_config(cfg)
    rows = text_evals(cfg, reg) + video_evals(cfg, reg, llm)
    jsonl_write(cfg.kol_dir / "evals.jsonl", rows)
    n_video = sum(1 for r in rows if r["source"] == "video")
    n_text = sum(1 for r in rows if r["source"] == "text")
    print(f"kol evals={len(rows)} (text={n_text}, video={n_video})")


if __name__ == "__main__":
    main()
