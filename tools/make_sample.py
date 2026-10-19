#!/usr/bin/env python3
"""Generate a synthetic, anonymized demo dataset.

No real people, brands, links, or numbers. Used by tools/smoke_test.py.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "demo" / "dataset"
OUT.mkdir(parents=True, exist_ok=True)

BASE = 1790000000  # arbitrary epoch; demo only

PLATS = ["xiaohongshu", "douyin", "bilibili", "zhihu", "weibo", "wechat", "x"]
LABEL = {"xiaohongshu": "小红书", "douyin": "抖音", "bilibili": "B站",
         "zhihu": "知乎", "weibo": "微博", "wechat": "微信公众号", "x": "X"}

POSTS = [
    ("价格真香，同样的任务成本只有竞品的一半", "pos", "价格便宜", {"B": "buy"}, ["DeepSeek"]),
    ("便宜是真的，但思考时间太长了，十几分钟才出结果", "mix", "思考过长", {"B": "buy", "E2": "reject"}, []),
    ("榜单分数涨得太快，实际用起来完全不是这个水平", "neg", "刷分质疑", {"A": "reject", "I": "reject"}, []),
    ("开源权重和训练框架都放了，这点很有诚意", "pos", "开源诚意", {"D": "buy"}, []),
    ("空转五个小时没有产出，最后还把目录删了", "neg", "稳定性", {"J": "reject"}, []),
    ("编程任务完成度不错，复杂项目也能跑通", "pos", "编程好用", {"I": "buy"}, []),
    ("营销味太重，到处都是邀请码", "neg", "营销质疑", {"G": "reject"}, []),
    ("和竞品比还是差一档，复杂任务容易跑偏", "neg", "不如竞品", {"K": "reject", "I": "reject"}, ["GLM"]),
    ("换了一个客户端之后效果明显变好", "pos", "客户端", {"H": "reject", "I": "buy"}, []),
    ("长上下文下质量下降明显，越聊越乱", "neg", "长上下文", {"J": "reject"}, []),
    ("多模态识别图片还行，速度也快", "pos", "多模态", {"E1": "buy", "E2": "buy"}, []),
    ("思考链很长，但结论经常是错的", "neg", "思考过长", {"E2": "reject", "I": "reject"}, []),
]

rows, labels = [], []
for i, (text, sent, topic, stance, comp) in enumerate(POSTS):
    plat = PLATS[i % len(PLATS)]
    pid = f"p{i:03d}"
    t = BASE + i * 3600
    n_comments = 3
    rows.append({
        "platform": plat, "platform_label": LABEL[plat], "kind": "post",
        "id": pid, "parent_id": "", "title": "", "text": text,
        "author": f"user{i % 5}", "time": t, "time_known": True,
        "like": 100 + i * 37, "comment_count": n_comments,
        "url": "", "src": f"{plat}-post", "relevant": True, "inherit": False,
    })
    labels.append({
        "key": f"{plat}|post|{pid}|{text[:40]}", "rel": 1, "sent": sent,
        "src": "kol" if i % 4 == 0 else "user", "claims": list(stance),
        "stance": stance, "topics": [topic], "comp": comp,
        "quote": text[:60],
    })
    for j in range(n_comments if plat != "wechat" else 0):
        cid = f"c{i:03d}{j}"
        ctext = ["同意", "不同意，实际体验更差", "价格确实便宜"][j]
        rows.append({
            "platform": plat, "platform_label": LABEL[plat], "kind": "comment",
            "id": cid, "parent_id": pid, "title": "", "text": ctext,
            "author": f"cuser{j}", "time": t + 60 + j * 30, "time_known": True,
            "like": 10 + j * 5, "comment_count": None, "url": "",
            "src": f"{plat}-comment", "relevant": True, "inherit": True,
        })
        labels.append({
            "key": f"{plat}|comment|{cid}|{ctext[:40]}", "rel": 1,
            "sent": ["neu", "neg", "pos"][j], "src": "user", "claims": [],
            "stance": {}, "topics": [], "comp": [], "quote": ctext,
        })

# YouTube synthetic rows (for video smoke test)
yt = [
    {"platform": "youtube", "platform_label": "YouTube", "kind": "video", "id": "v_head",
     "parent_id": "", "title": "同一任务对比三个模型", "text": "",
     "author": "ExampleChannel", "time": BASE, "time_known": True,
     "like": 500, "comment_count": 0, "url": "", "src": "youtube",
     "relevant": True, "inherit": False},
    {"platform": "youtube", "platform_label": "YouTube", "kind": "video", "id": "v_single",
     "parent_id": "", "title": "单模型能力演示", "text": "",
     "author": "ExampleChannel", "time": BASE + 100, "time_known": True,
     "like": 200, "comment_count": 0, "url": "", "src": "youtube",
     "relevant": True, "inherit": False},
    {"platform": "youtube", "platform_label": "YouTube", "kind": "video", "id": "v_relay",
     "parent_id": "", "title": "官方发布会数据解读", "text": "",
     "author": "MediaChannel", "time": BASE + 200, "time_known": True,
     "like": 300, "comment_count": 0, "url": "", "src": "youtube",
     "relevant": True, "inherit": False},
    {"platform": "youtube", "platform_label": "YouTube", "kind": "video", "id": "v_uncertain",
     "parent_id": "", "title": "你们自己看这几个画面", "text": "",
     "author": "ExampleChannel", "time": BASE + 300, "time_known": True,
     "like": 100, "comment_count": 0, "url": "", "src": "youtube",
     "relevant": True, "inherit": False},
]
rows += yt
for v in yt:
    labels.append({
        "key": f'{v["platform"]}|video|{v["id"]}|', "rel": 1, "sent": "neu",
        "src": "kol", "claims": [], "stance": {}, "topics": [], "comp": [],
        "quote": "",
    })

with (OUT / "combined.jsonl").open("w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
with (OUT / "labels.jsonl").open("w", encoding="utf-8") as f:
    for r in labels:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# video manifest + transcripts
video_dir = ROOT / "examples" / "demo" / "video"
video_dir.mkdir(parents=True, exist_ok=True)
manifest = [
    {"platform": "YouTube", "id": "v_head", "url": "", "title": "同一任务对比三个模型",
     "description": "同一提示词，三个模型同台对比", "author": "ExampleChannel", "time": BASE,
     "transcript": [
         {"s": 0, "e": 5, "t": "今天用同一个提示词做编程任务，对比 Model X、DeepSeek、GLM 三个模型"},
         {"s": 5, "e": 12, "t": "第一个模型用了 12 分钟，第二个 8 分钟，第三个 5 分钟"},
         {"s": 12, "e": 20, "t": "通过率分别是 60%、75%、90%，第三个明显更好"},
     ]},
    {"platform": "YouTube", "id": "v_single", "url": "", "title": "单模型能力演示",
     "description": "只演示一个模型的编程能力", "author": "ExampleChannel", "time": BASE + 100,
     "transcript": [{"s": 0, "e": 6, "t": "今天只测 Model X 这一个模型，写一个网页"}]},
    {"platform": "YouTube", "id": "v_relay", "url": "", "title": "官方发布会数据解读",
     "description": "据报道，官方宣布榜单第一", "author": "MediaChannel", "time": BASE + 200,
     "transcript": [{"s": 0, "e": 8, "t": "据报道，官方宣布榜单第一，指数 46"}]},
    {"platform": "YouTube", "id": "v_uncertain", "url": "", "title": "你们自己看这几个画面",
     "description": "左边是 A，右边是 B", "author": "ExampleChannel", "time": BASE + 300,
     "transcript": [{"s": 0, "e": 6, "t": "左边是 A，右边是 B，你们自己看"}]},
]
with (video_dir / "index.jsonl").open("w", encoding="utf-8") as f:
    for r in manifest:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"wrote {len(rows)} records, {len(labels)} labels, {len(manifest)} videos -> {OUT}")
