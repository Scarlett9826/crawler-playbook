"""KOL x dimension matrix -> data/metrics/kol.json + report."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from ..config import Config
from ..util import json_write, jsonl_read

WEIGHT = {"independent": 1.0, "semi": 0.7, "sponsored": 0.3, "unknown": 0.5}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    a = ap.parse_args()
    cfg = Config(a.project)
    cfg.ensure_dirs()
    rows = list(jsonl_read(cfg.kol_dir / "evals.jsonl"))

    by_kol = defaultdict(lambda: {"name": "", "independence": "unknown", "sources": Counter(),
                                  "dims": defaultdict(Counter), "items": 0})
    matrix = defaultdict(Counter)
    for r in rows:
        k = r.get("kol") or {}
        kid = k.get("kol_id") or "unknown"
        rec = by_kol[kid]
        rec["name"] = k.get("name") or kid
        rec["independence"] = k.get("independence", "unknown")
        rec["sources"][r.get("source")] += 1
        rec["items"] += 1
        for d in r.get("dimensions") or []:
            dim = d.get("dim")
            verdict = d.get("verdict") or "neu"
            rec["dims"][dim][verdict] += 1
            matrix[dim][verdict] += 1

    out = {
        "kols": {kid: {"name": v["name"], "independence": v["independence"],
                       "sources": dict(v["sources"]), "items": v["items"],
                       "dimensions": {d: dict(c) for d, c in v["dims"].items()}}
                 for kid, v in by_kol.items()},
        "dimension_matrix": {d: dict(c) for d, c in matrix.items()},
        "n_evals": len(rows),
    }
    json_write(cfg.metrics_dir / "kol.json", out)

    lines = ["# KOL 评价提炼", "",
             f"- 评价条数：{len(rows)}",
             f"- KOL 数：{len(by_kol)}", "",
             "| KOL | 独立性 | 来源 | 条数 | 主要维度 |", "|---|---|---|---:|---|"]
    for kid, v in sorted(by_kol.items(), key=lambda x: -x[1]["items"]):
        dims = Counter({d: sum(c.values()) for d, c in v["dims"].items()})
        dims_s = "、".join(f"{d}({n})" for d, n in dims.most_common(4)) or "—"
        lines.append(f"| {v['name']} | {v['independence']} | {'/'.join(v['sources'])} | {v['items']} | {dims_s} |")
    lines += ["", "## 维度共识", "",
              "| 维度 | pos | neg | mix | neu |", "|---|---:|---:|---:|---:|"]
    for d, c in sorted(matrix.items()):
        lines.append(f"| {d} | {c.get('pos',0)} | {c.get('neg',0)} | {c.get('mix',0)} | {c.get('neu',0)} |")
    (cfg.reports_dir / "kol_eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"kols={len(by_kol)} evals={len(rows)} -> {cfg.reports_dir / 'kol_eval.md'}")


if __name__ == "__main__":
    main()
