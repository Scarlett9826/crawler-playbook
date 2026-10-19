"""Build a showcase report from data/video/showcases.jsonl."""
from __future__ import annotations

import argparse
from collections import defaultdict

from ..config import Config
from ..util import jsonl_read
from .render import write

TITLE = "对比 Showcase 汇总"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    a = ap.parse_args()
    cfg = Config(a.project)
    rows = list(jsonl_read(cfg.video_dir / "showcases.jsonl"))

    by_task = defaultdict(list)
    for s in rows:
        by_task[s.get("task") or "未标注任务"].append(s)

    lines = [f"> 有效 showcase：{len(rows)}；任务数：{len(by_task)}", ""]
    for task, items in by_task.items():
        lines += [f"## {task}", "",
                  "| 视频 | 模型 | 结果 | 结论 | 置信度 | 时间戳 |",
                  "|---|---|---|---|---|---|"]
        for s in items:
            video = s.get("video") or {}
            models = "、".join(m.get("canonical", "") for m in s.get("models", []))
            results = "；".join(
                f'{r.get("model","")} {r.get("metric","")}={r.get("value","")}{r.get("unit","")}'
                for r in s.get("results", [])) or "—"
            verdict = (s.get("verdict") or {}).get("summary") or "—"
            ts = s.get("timestamps") or {}
            lines.append(f'| {video.get("title","")[:40]} | {models} | {results} | {verdict} | {s.get("confidence","")} | {ts.get("start",0)}–{ts.get("end",0)}s |')
        lines += [""]

    lines += ["## 说明", "",
              "- 仅收录自测 + 同题 + 多模型的对比。",
              "- 离线启发式只识别模型与时间范围，不解析数字；配置 LLM 后会补全结果与结论。",
              "- 媒体转述、教程、娱乐、单模型演示不在此表。"]
    out = write(cfg, "showcase", "\n".join(lines) + "\n", "showcase", TITLE,
                f"{len(rows)} 条有效 showcase")
    print(out)


if __name__ == "__main__":
    main()
