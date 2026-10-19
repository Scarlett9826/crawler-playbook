"""Shared loaders for the analysis layer."""
from __future__ import annotations

from collections import Counter, defaultdict

from ..config import Config
from ..util import jsonl_read, to_epoch


def load(cfg: Config):
    rows = {}
    for r in jsonl_read(cfg.normalized_dir / "combined.jsonl"):
        key = f'{r.get("platform")}|{r.get("kind")}|{r.get("id")}|{(r.get("text") or "")[:40]}'
        rows[key] = r
    labels = {}
    for d in jsonl_read(cfg.labels_dir / "labels.jsonl"):
        k = d.get("key")
        if k and k not in labels:
            labels[k] = d
    rel = {k: d for k, d in labels.items() if d.get("rel") == 1 and k in rows}
    return rows, labels, rel


def num(x) -> int:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def region(row: dict) -> str:
    return "X" if row.get("platform") == "x" else "domestic"


def claim_table(rows: dict, rel: dict) -> dict:
    """buy/reject/neutral per claim, overall and by region."""
    out = defaultdict(lambda: defaultdict(Counter))
    likes = defaultdict(lambda: defaultdict(Counter))
    for k, d in rel.items():
        r = rows[k]
        for c, st in (d.get("stance") or {}).items():
            out[c][region(r)][st] += 1
            out[c]["all"][st] += 1
            likes[c][region(r)][st] += num(r.get("like"))
            likes[c]["all"][st] += num(r.get("like"))
    return {
        "counts": {c: {reg: dict(cnt) for reg, cnt in v.items()} for c, v in out.items()},
        "likes": {c: {reg: dict(cnt) for reg, cnt in v.items()} for c, v in likes.items()},
    }


def topic_table(rows: dict, rel: dict, sentiments: set[str]) -> list[dict]:
    cnt = Counter()
    likes = Counter()
    plats = defaultdict(Counter)
    for k, d in rel.items():
        if d.get("sent") not in sentiments:
            continue
        r = rows[k]
        for t in (d.get("topics") or []):
            t = str(t).strip()
            if not t:
                continue
            cnt[t] += 1
            likes[t] += num(r.get("like"))
            plats[t][r.get("platform")] += 1
    return [{"topic": t, "n": n, "likes": likes[t],
             "platforms": dict(plats[t].most_common(4))}
            for t, n in cnt.most_common()]
