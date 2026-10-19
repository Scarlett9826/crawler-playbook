"""Supplementary dimensions -> data/metrics/deep.json"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from ..config import Config
from ..util import json_write
from .common import load, num


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    a = ap.parse_args()
    cfg = Config(a.project)
    rows, labels, rel = load(cfg)

    kind_sent = defaultdict(Counter)
    for k, d in rel.items():
        kind_sent[rows[k].get("kind")][d.get("sent")] += 1

    # like concentration
    likes = sorted((num(rows[k].get("like")) for k in rel), reverse=True)
    total = sum(likes) or 1
    top1 = likes[0] if likes else 0
    top10 = sum(likes[:10])
    top1pct = sum(likes[:max(1, len(likes) // 100)])
    zero = sum(1 for x in likes if x == 0)

    # comments vs posts
    parent_sent = {}
    for k, d in rel.items():
        r = rows[k]
        if r.get("kind") != "comment":
            parent_sent[(r.get("platform"), r.get("id"))] = d.get("sent")
    comment_on_pos = Counter()
    for k, d in rel.items():
        r = rows[k]
        if r.get("kind") != "comment":
            continue
        ps = parent_sent.get((r.get("platform"), r.get("parent_id")))
        if ps:
            comment_on_pos[ps] += 1

    out = {
        "sent_by_kind": {k: dict(v) for k, v in kind_sent.items()},
        "like_concentration": {
            "n": len(likes), "total": total,
            "top1": top1, "top1_share": round(top1 / total, 4),
            "top10_share": round(top10 / total, 4),
            "top1pct_share": round(top1pct / total, 4),
            "zero_like_share": round(zero / len(likes), 4) if likes else 0,
        },
        "comments_on_parent_sentiment": dict(comment_on_pos),
        "unknown_time": sum(1 for k in rel if not rows[k].get("time")),
    }
    json_write(cfg.metrics_dir / "deep.json", out)
    print("kinds:", out["sent_by_kind"])
    print("top1 share:", out["like_concentration"]["top1_share"])


if __name__ == "__main__":
    main()
