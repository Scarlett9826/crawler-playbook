"""Core metrics -> data/metrics/metrics.json"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from ..config import Config
from ..util import json_write
from .common import claim_table, load, num, region


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    a = ap.parse_args()
    cfg = Config(a.project)
    cfg.ensure_dirs()
    rows, labels, rel = load(cfg)

    M = {}
    M["labels_total"] = len(labels)
    M["records_total"] = len(rows)
    M["relevant"] = len(rel)
    M["sent"] = dict(Counter(d.get("sent") for d in rel.values()))
    M["src"] = dict(Counter(d.get("src") for d in rel.values()))
    M["kind"] = dict(Counter(rows[k].get("kind") for k in rel))

    by_platform = defaultdict(Counter)
    by_region = defaultdict(Counter)
    weighted = defaultdict(int)
    for k, d in rel.items():
        r = rows[k]
        s = d.get("sent")
        by_platform[r.get("platform")][s] += 1
        by_region[region(r)][s] += 1
        weighted[s] += num(r.get("like"))
    M["sent_by_platform"] = {p: dict(c) for p, c in by_platform.items()}
    M["sent_by_region"] = {p: dict(c) for p, c in by_region.items()}
    M["sent_like_weighted"] = dict(weighted)

    ct = claim_table(rows, rel)
    M["claims"] = {c: v.get("all", {}) for c, v in ct["counts"].items()}
    M["claims_by_region"] = ct["counts"]
    M["claims_like_weighted"] = ct["likes"]

    comp = Counter()
    for d in rel.values():
        for c in (d.get("comp") or []):
            comp[str(c)] += 1
    M["competitors"] = dict(comp.most_common(20))

    times = [rows[k].get("time") for k in rel if rows[k].get("time")]
    M["time_range"] = {"min": min(times) if times else None,
                       "max": max(times) if times else None,
                       "min_iso": cfg.date_label(min(times)) if times else "",
                       "max_iso": cfg.date_label(max(times)) if times else ""}

    json_write(cfg.metrics_dir / "metrics.json", M)
    print(f"relevant={len(rel)} sent={M['sent']}")
    print("wrote", cfg.metrics_dir / "metrics.json")


if __name__ == "__main__":
    main()
