"""Tiny template renderer and markdown -> HTML wrapper.

Templates use {{KEY}} placeholders. No extra dependency beyond `markdown`.
"""
from __future__ import annotations

import re
from pathlib import Path

import markdown as mdlib

from ..config import Config
from ..config import resolve

PLACEHOLDER = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")

CSS = """
:root{--fg:#1d1d1f;--mut:#6e6e73;--line:#e5e5ea;--acc:#ff6900;--bg:#fafafa}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.75 -apple-system,"PingFang SC","Helvetica Neue",sans-serif}
header{background:linear-gradient(135deg,#ff6900,#ff9a4d);color:#fff;padding:42px 0 34px}
header .w{max-width:1040px;margin:auto;padding:0 32px}
header h1{margin:0 0 6px;font-size:28px}header p{margin:0;opacity:.9;font-size:13px}
main{max-width:1040px;margin:-20px auto 60px;padding:34px 42px;background:#fff;border-radius:14px;box-shadow:0 4px 24px rgba(0,0,0,.06)}
h2{margin:40px 0 14px;padding-left:12px;border-left:4px solid var(--acc);font-size:21px}
h2:first-of-type{margin-top:6px}h3{margin:26px 0 8px;font-size:17px}
blockquote{margin:0 0 18px;padding:13px 17px;background:#fff6ef;border-radius:8px;color:#7a3d00}
blockquote p{margin:0}
table{width:100%;border-collapse:collapse;margin:12px 0 18px;font-size:13.5px;display:block;overflow-x:auto}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#f5f5f7;font-weight:600;white-space:nowrap}
tr:hover td{background:#fcfcfd}
hr{border:none;border-top:1px dashed var(--line);margin:32px 0}
code{background:#f2f2f7;padding:1px 5px;border-radius:4px}
li{margin:4px 0}
@media print{header{padding:18px 0}main{box-shadow:none;margin:0}}
"""


def render(template: str | Path, context: dict) -> str:
    text = Path(template).read_text(encoding="utf-8")
    return PLACEHOLDER.sub(lambda m: str(context.get(m.group(1), "")), text)


def render_named(cfg: Config, name: str, context: dict) -> str:
    p = cfg.root / "templates" / "reports" / f"{name}.md"
    return render(p, context)


def to_html(body_md: str, title: str, subtitle: str = "") -> str:
    body = mdlib.markdown(body_md, extensions=["tables", "fenced_code", "sane_lists"])
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{CSS}</style></head><body>
<header><div class="w"><h1>{title}</h1><p>{subtitle}</p></div></header>
<main>{body}</main></body></html>"""


def write(cfg: Config, name: str, body_md: str, out_stem: str,
          title: str, subtitle: str = "") -> Path:
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / f"{out_stem}.md").write_text(body_md, encoding="utf-8")
    html = to_html(body_md, title, subtitle)
    out = cfg.reports_dir / f"{out_stem}.html"
    out.write_text(html, encoding="utf-8")
    return out


def resolve_path(cfg: Config, p: str) -> Path:
    return resolve(p)
