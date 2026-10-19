"""Topic tables -> data/metrics/themes.json"""
from __future__ import annotations

import argparse

from ..config import Config
from ..util import json_write
from .common import load, topic_table


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    a = ap.parse_args()
    cfg = Config(a.project)
    rows, labels, rel = load(cfg)
    out = {
        "negative": topic_table(rows, rel, {"neg"}),
        "positive": topic_table(rows, rel, {"pos"}),
        "mixed": topic_table(rows, rel, {"mix"}),
    }
    json_write(cfg.metrics_dir / "themes.json", out)
    print("negative:", [(x["topic"], x["n"]) for x in out["negative"][:10]])
    print("positive:", [(x["topic"], x["n"]) for x in out["positive"][:10]])


if __name__ == "__main__":
    main()
