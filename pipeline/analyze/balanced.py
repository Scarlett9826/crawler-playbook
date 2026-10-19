"""Symmetric theme counts + claim scorecard -> data/metrics/balanced.json

Rules:
  - negative themes come only from negative records
  - positive themes come only from positive records
  - mixed records are reported separately (and in a sensitivity view)
  - each record contributes one primary topic to keep counts from double-counting
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from ..config import Config
from ..util import json_write
from .common import claim_table, load, num


def primary(record: dict) -> str:
    topics = [str(t).strip() for t in (record.get("topics") or []) if str(t).strip()]
    return topics[0] if topics else "其他/笼统"


def theme_rows(rows, rel, sent: str) -> list[dict]:
    cnt = Counter()
    likes = Counter()
    plats = defaultdict(Counter)
    for k, d in rel.items():
        if d.get("sent") != sent:
            continue
        t = primary(d)
        r = rows[k]
        cnt[t] += 1
        likes[t] += num(r.get("like"))
        plats[t][r.get("platform")] += 1
    return [{"theme": t, "n": n, "likes": likes[t],
             "platforms": dict(plats[t].most_common(5))}
            for t, n in cnt.most_common()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    a = ap.parse_args()
    cfg = Config(a.project)
    rows, labels, rel = load(cfg)

    neg = theme_rows(rows, rel, "neg")
    pos = theme_rows(rows, rel, "pos")
    mix = theme_rows(rows, rel, "mix")
    ct = claim_table(rows, rel)

    # defense voices: positive or mixed records that push back on criticism
    defend = []
    for k, d in rel.items():
        if d.get("sent") not in ("pos", "mix"):
            continue
        blob = " ".join([str(d.get("quote") or "")] + [str(t) for t in (d.get("topics") or [])])
        if any(x in blob for x in ("辩护", "反驳", "支持", "辟谣", "理性", "反驳质疑")):
            r = rows[k]
            defend.append({"platform": r.get("platform"), "like": num(r.get("like")),
                           "text": (r.get("text") or "")[:120], "quote": d.get("quote")})
    defend.sort(key=lambda x: -x["like"])

    out = {
        "negative_themes": neg,
        "positive_themes": pos,
        "mixed_themes": mix,
        "claims": {
            "counts": ct["counts"],
            "likes": ct["likes"],
        },
        "defense": {"n": len(defend), "likes": sum(x["like"] for x in defend),
                    "examples": defend[:20]},
    }
    json_write(cfg.metrics_dir / "balanced.json", out)
    print("neg:", [(x["theme"], x["n"]) for x in neg[:8]])
    print("pos:", [(x["theme"], x["n"]) for x in pos[:8]])
    print("defense:", out["defense"]["n"])


if __name__ == "__main__":
    main()
