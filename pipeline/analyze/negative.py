"""Export negative / mixed records to CSV, sorted by likes."""
from __future__ import annotations

import argparse
import csv

from ..config import Config
from .common import load, num


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    a = ap.parse_args()
    cfg = Config(a.project)
    rows, labels, rel = load(cfg)
    items = []
    for k, d in rel.items():
        if d.get("sent") not in ("neg", "mix"):
            continue
        r = rows[k]
        items.append({
            "platform": r.get("platform"), "kind": r.get("kind"),
            "like": num(r.get("like")), "sent": d.get("sent"),
            "topics": "|".join(d.get("topics") or []),
            "claims": "|".join(d.get("claims") or []),
            "quote": d.get("quote") or "",
            "text": (r.get("text") or "")[:500],
            "url": r.get("url") or "",
            "time": cfg.date_label(r.get("time")),
        })
    items.sort(key=lambda x: -x["like"])
    out = cfg.metrics_dir / "negative.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(items[0].keys()) if items else [])
        if items:
            w.writeheader()
            w.writerows(items)
    print(f"wrote {len(items)} -> {out}")


if __name__ == "__main__":
    main()
