"""Coverage / freshness / accuracy audit.

This is the guardrail for "完整、准确、新鲜":
  - completeness: are there posts, and how much of the reported comment volume did we get?
  - freshness: how stale is the newest record?
  - accuracy: duplicate ratio + unknown-time ratio + missing parent links.

Output:
  data/metrics/audit.json
  data/reports/audit.md
Exit code is non-zero with --strict if any enabled platform fails.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone

from .config import Config
from .util import json_read, json_write, jsonl_read

POST_KINDS = {"post", "article", "tweet", "video"}


def load(cfg: Config) -> tuple[list[dict], dict]:
    rows = list(jsonl_read(cfg.normalized_dir / "combined.jsonl"))
    st = json_read(cfg.normalized_dir / "stats.json", default={}) or {}
    return rows, st


def audit(cfg: Config, rows: list[dict], st: dict) -> dict:
    targets = (cfg.project.get("crawl") or {}).get("targets") or {}
    min_posts = int(targets.get("min_posts_per_platform", 1))
    min_comment_ratio = float(targets.get("min_comment_ratio", 0.5))
    max_stale = float(targets.get("max_staleness_hours", 24))
    max_dup = float(targets.get("max_duplicate_ratio", 0.15))
    max_unknown = float(targets.get("max_unknown_time_ratio", 0.05))

    now = int(datetime.now(timezone.utc).timestamp())
    by_platform: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_platform[r.get("platform", "")].append(r)

    out = {
        "generated_at": now,
        "window": st.get("window"),
        "targets": {
            "min_posts_per_platform": min_posts,
            "min_comment_ratio": min_comment_ratio,
            "max_staleness_hours": max_stale,
            "max_duplicate_ratio": max_dup,
            "max_unknown_time_ratio": max_unknown,
        },
        "global": {
            "raw_records": st.get("raw_records", 0),
            "kept_records": st.get("kept_records", len(rows)),
            "duplicate_ratio": st.get("duplicate_ratio", 0),
            "unknown_time_ratio": st.get("unknown_time_ratio", 0),
        },
        "platforms": {},
        "recommendations": [],
        "status": "ok",
    }

    for name, pc in cfg.platforms.items():
        cfgp = cfg.platform_config(name)
        if not cfgp.get("enabled", False):
            continue
        rs = by_platform.get(name, [])
        posts = [r for r in rs if r.get("kind") in POST_KINDS]
        comments = [r for r in rs if r.get("kind") == "comment"]
        times = [r["time"] for r in rs if r.get("time")]
        last = max(times) if times else None
        stale_h = round((now - last) / 3600, 1) if last else None
        unknown = sum(1 for r in rs if not r.get("time"))
        unknown_ratio = round(unknown / len(rs), 4) if rs else 0

        # comment coverage: collected / reported, only for posts with a counter
        expected = 0
        reported_posts = 0
        zero_gap_posts = 0
        per_post = Counter()
        for c in comments:
            per_post[(c.get("platform"), c.get("parent_id"))] += 1
        for p in posts:
            n = p.get("comment_count")
            try:
                n = int(float(n))
            except (TypeError, ValueError):
                continue
            if n <= 0:
                continue
            reported_posts += 1
            expected += n
            got = per_post.get((p.get("platform"), p.get("id")), 0)
            if got == 0:
                zero_gap_posts += 1
        collected = len(comments)
        comment_ratio = round(min(1.0, collected / expected), 4) if expected else None

        # freshness / completeness / accuracy status
        checks = {}
        checks["freshness"] = ("pass" if last and stale_h is not None and stale_h <= max_stale
                               else "fail" if last else "unknown")
        if pc.get("completeness", {}).get("has_comments", True):
            checks["completeness"] = ("pass" if (len(posts) >= min_posts and
                                                 (comment_ratio is None or comment_ratio >= min_comment_ratio))
                                      else "fail")
        else:
            checks["completeness"] = "pass" if len(posts) >= min_posts else "fail"
        checks["accuracy"] = ("pass" if unknown_ratio <= max_unknown else "fail")

        status = "ok"
        if "fail" in checks.values():
            status = "fail"
        elif "unknown" in checks.values():
            status = "warn"
        if status == "fail":
            out["status"] = "fail"
        elif status == "warn" and out["status"] == "ok":
            out["status"] = "warn"

        out["platforms"][name] = {
            "label": pc.get("label", name),
            "adapter": pc.get("adapter"),
            "records": len(rs),
            "posts": len(posts),
            "comments": len(comments),
            "comment_expected": expected,
            "comment_ratio": comment_ratio,
            "posts_with_reported_comments": reported_posts,
            "posts_with_zero_collected": zero_gap_posts,
            "last_record": last,
            "last_record_iso": cfg.date_label(last),
            "staleness_hours": stale_h,
            "unknown_time_ratio": unknown_ratio,
            "checks": checks,
            "status": status,
        }

        # recommendations
        if checks["freshness"] == "fail":
            out["recommendations"].append(
                f"{pc.get('label', name)}: 最新数据滞后 {stale_h}h（目标 ≤{max_stale}h），重新运行采集并检查登录态/限流。")
        if checks["completeness"] == "fail" and len(posts) < min_posts:
            out["recommendations"].append(
                f"{pc.get('label', name)}: 帖子只有 {len(posts)} 条（目标 ≥{min_posts}），扩大关键词或翻页。")
        if (comment_ratio is not None and comment_ratio < min_comment_ratio):
            out["recommendations"].append(
                f"{pc.get('label', name)}: 评论覆盖 {comment_ratio:.0%}（目标 ≥{min_comment_ratio:.0%}），对高评论帖执行 detail 补抓。")
        if zero_gap_posts:
            out["recommendations"].append(
                f"{pc.get('label', name)}: {zero_gap_posts} 个有评论数的帖子一条评论都没抓到，优先补抓。")
        if unknown_ratio > max_unknown:
            out["recommendations"].append(
                f"{pc.get('label', name)}: {unknown_ratio:.0%} 记录缺时间，检查时间字段解析。")

    if out["global"]["duplicate_ratio"] > max_dup:
        out["recommendations"].append(
            f"全局重复率 {out['global']['duplicate_ratio']:.0%}（目标 ≤{max_dup:.0%}），检查去重键与补抓重叠。")

    return out


def to_markdown(cfg: Config, a: dict) -> str:
    lines = ["# 采集完整度 / 新鲜度审计", ""]
    lines.append(f"- 生成时间：{cfg.date_label(a['generated_at'])}")
    w = a.get("window") or {}
    lines.append(f"- 数据窗口：{cfg.date_label(w.get('since'))} ~ {cfg.date_label(w.get('until'))}")
    g = a["global"]
    lines.append(f"- 原始 {g['raw_records']} 条，保留 {g['kept_records']} 条，重复率 {g['duplicate_ratio']:.1%}，缺时间 {g['unknown_time_ratio']:.1%}")
    lines.append(f"- 总体状态：**{a['status']}**")
    lines += ["", "| 平台 | 记录 | 帖子 | 评论 | 评论覆盖 | 最新数据 | 滞后(h) | 状态 |", "|---|---:|---:|---:|---:|---|---:|---|"]
    for name, p in a["platforms"].items():
        cr = "—" if p["comment_ratio"] is None else f"{p['comment_ratio']:.0%}"
        st = {"ok": "✅", "warn": "🟡", "fail": "❌"}.get(p["status"], p["status"])
        lines.append(f"| {p['label']} | {p['records']} | {p['posts']} | {p['comments']} | {cr} | {p['last_record_iso'] or '—'} | {p['staleness_hours'] if p['staleness_hours'] is not None else '—'} | {st} |")
    lines += ["", "## 建议", ""]
    if a["recommendations"]:
        lines += [f"- {x}" for x in a["recommendations"]]
    else:
        lines.append("- 无。")
    lines += ["", "## 判定口径", "",
              "- 新鲜度：最新一条记录距现在的时长，超过阈值即失败。",
              "- 完整度：帖子数是否达标；有评论数的帖子，已采评论 / 平台报告评论数。",
              "- 准确度：缺时间比例；全局重复率。",
              "- 平台报告的评论数是下限而非真值，覆盖率 >100% 会被截断为 100%。"]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    rows, st = load(cfg)
    result = audit(cfg, rows, st)
    cfg.metrics_dir.mkdir(parents=True, exist_ok=True)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    json_write(cfg.metrics_dir / "audit.json", result)
    md = to_markdown(cfg, result)
    (cfg.reports_dir / "audit.md").write_text(md, encoding="utf-8")
    print(md)
    if a.strict and result["status"] == "fail":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
