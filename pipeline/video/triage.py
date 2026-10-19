"""Video triage: decide whether a video contains a comparison showcase.

Not every video has one. This module classifies the content first, then routes.
Heuristics always run; an LLM can refine the result when configured.
"""
from __future__ import annotations

import json
import re

from ..config import Config
from ..util import clean_text

COMPARE = re.compile(
    r"对比|横评|大乱斗|对战|对打|同台|PK|vs\.?|VS|双模|竞品|"
    r"同一(个)?提示词|同一(个)?任务|左边|右边|第一个|第二个|"
    r"跑分|实测|测试了|公平的?测", re.I)
NUMERIC = re.compile(r"\d+(\.\d+)?\s*(分|秒|分钟|小时|元|美元|%|token|倍|刀)|通过率|成功率|排名|第[一二三四五六七八九十\d]+")
VISUAL = re.compile(r"你们自己看|自己看|看图|画面|左边是|右边是|上面是|下面是|这个分数|如图所示")
RELAY = re.compile(r"官方(发布|宣布|数据)|发布会|据报道|媒体|转述|消息称|官宣")
RELAY_MARK = re.compile(r"榜单|指数|排名|跑分|第一")
PROMO = re.compile(r"邀请码|赞助|官方提供|商务合作|合作|折扣|affiliate|promo", re.I)
BEFORE_AFTER = re.compile(r"换(了)?(harness|客户端|agent|环境)|重测|重新测|版本|前后|升级后", re.I)
TUTORIAL = re.compile(r"教程|安装|接入|配置|怎么用|使用教程|step\s*by\s*step", re.I)
ENTERTAIN = re.compile(r"拳皇|对战游戏|娱乐|整活|搞笑|meme", re.I)


def _known_models(cfg: Config, text: str) -> list[str]:
    found = []
    low = text.lower()
    for m in (cfg.models.get("models") or []):
        for alias in m.get("aliases") or [m.get("canonical")]:
            if alias and alias.lower() in low:
                found.append(m["canonical"])
                break
    return sorted(set(found))


def heuristic(cfg: Config, video: dict) -> dict:
    title = clean_text(video.get("title"))
    desc = clean_text(video.get("description"))
    tx = " ".join(clean_text(s.get("t") or s.get("text")) for s in (video.get("transcript") or []))
    blob = f"{title} {desc} {tx}"
    models = _known_models(cfg, blob)
    has_compare = bool(COMPARE.search(blob))
    has_numbers = bool(NUMERIC.search(blob))
    own_test = not bool(RELAY.search(blob))
    visual_only = bool(VISUAL.search(blob)) and not has_numbers
    promo = bool(PROMO.search(blob))
    tutorial = bool(TUTORIAL.search(blob))
    entertainment = bool(ENTERTAIN.search(blob))
    before_after = bool(BEFORE_AFTER.search(blob))

    if entertainment:
        ctype, stype = "entertainment", "entertainment_vs"
    elif tutorial:
        ctype, stype = "tutorial", "none"
    elif not own_test and (has_compare or RELAY_MARK.search(blob)):
        ctype, stype = "media_relay", "benchmark_relay"
    elif before_after:
        ctype, stype = "kol_review", "before_after"
    elif has_compare and len(models) >= 2:
        ctype, stype = "kol_review", ("head_to_head" if has_numbers else "multi_model_leaderboard")
    elif has_compare and len(models) == 1:
        ctype, stype = "kol_review", "single_model_demo"
    elif models:
        ctype, stype = "kol_review", "single_model_demo"
    else:
        ctype, stype = "other", "none"

    present = "yes" if stype in ("head_to_head", "multi_model_leaderboard") else (
        "uncertain" if visual_only and has_compare else "no")

    conf = "high" if (present == "yes" and has_numbers) else (
        "medium" if present == "yes" else "low")
    if visual_only:
        conf = "low"

    return {
        "content_type": ctype,
        "is_own_test": own_test,
        "showcase": {
            "present": present,
            "type": stype,
            "models_tested": models,
            "same_task": has_compare,
            "has_numbers": has_numbers,
            "visual_only_suspected": visual_only,
        },
        "promo_signals": [m.group(0) for m in PROMO.finditer(blob)][:5],
        "needs_ocr": bool(visual_only),
        "confidence": conf,
        "reason": _reason(ctype, stype, models, has_numbers, own_test),
        "source": "heuristic",
    }


def _reason(ctype: str, stype: str, models: list[str], numbers: bool, own_test: bool) -> str:
    bits = [ctype, stype]
    if models:
        bits.append(f"{len(models)} models")
    bits.append("numbers" if numbers else "no numbers")
    bits.append("own test" if own_test else "relay")
    return " / ".join(bits)


def route(cfg: Config, tri: dict) -> dict:
    r = cfg.routing.get("routes") or {}
    stype = (tri.get("showcase") or {}).get("type", "none")
    present = (tri.get("showcase") or {}).get("present", "no")

    if present == "uncertain" and ((cfg.routing.get("triage") or {}).get("manual_review_on_uncertain")):
        return {"route": "manual_review", "tag": "needs_ocr" if tri.get("needs_ocr") else "uncertain"}
    rule = r.get(stype) or r.get("none") or {"route": "kol_eval_only"}
    out = dict(rule)
    if tri.get("promo_signals") and out.get("route") == "showcase_extract":
        out["sponsored"] = True
    return out


def llm_refine(cfg: Config, video: dict, tri: dict, call_llm) -> dict:
    """Optional refinement. `call_llm(system, user)` returns text."""
    if call_llm is None:
        return tri
    tx = "\n".join(f"[{s.get('s', 0):.0f}] {s.get('t','')}"
                   for s in (video.get("transcript") or []))[:12000]
    system = """你是视频内容分诊员。判断视频里是否包含“同题多模型对比”的 showcase。
只输出 JSON：{"content_type":"kol_review|media_relay|tutorial|entertainment|user_complaint|tech_analysis|other",
"is_own_test":true/false,
"showcase":{"present":"yes|no|uncertain","type":"head_to_head|multi_model_leaderboard|before_after|single_model_demo|benchmark_relay|entertainment_vs|none",
"models_tested":[],"same_task":true/false,"has_numbers":true/false,"visual_only_suspected":true/false},
"needs_ocr":true/false,"confidence":"high|medium|low","reason":"≤60字"}"""
    user = json.dumps({
        "title": video.get("title"), "description": video.get("description"),
        "transcript": tx, "heuristic": tri,
    }, ensure_ascii=False)
    try:
        txt = call_llm(system, user)
        m = re.search(r"\{.*\}", txt or "", re.S)
        refined = json.loads(m.group(0)) if m else None
        if refined:
            refined["source"] = "llm"
            return refined
    except Exception:
        pass
    return tri


def run(cfg: Config, video: dict, call_llm=None) -> dict:
    tri = heuristic(cfg, video)
    tri = llm_refine(cfg, video, tri, call_llm)
    tri["route"] = route(cfg, tri)
    return tri
