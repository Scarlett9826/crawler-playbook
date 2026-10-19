"""Render a markdown report into a self-contained HTML file.

Usage:
  python -m pipeline.report.make_html --input data/reports/audit.md \
      --output data/reports/audit.html --title "采集审计"
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .render import to_html


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default=None)
    ap.add_argument("--title", default="Report")
    ap.add_argument("--subtitle", default="")
    a = ap.parse_args()
    src = Path(a.input)
    body = src.read_text(encoding="utf-8")
    html = to_html(body, a.title, a.subtitle)
    out = Path(a.output) if a.output else src.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
