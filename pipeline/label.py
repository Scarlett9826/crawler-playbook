"""Per-record LLM labelling (OpenAI-compatible endpoint).

Input : data/normalized/combined.jsonl
Output: data/labels/labels.jsonl  (resume-safe)

Each label:
  key, rel, sent, src, claims, stance, topics, comp, quote
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .config import Config
from .util import jsonl_read, jsonl_write

SYSTEM = """你是舆情标注员。分析对象：{brand} 的 {product}。
对每条记录输出一个 JSON 对象：
- k: 记录编号（原样）
- rel: 1=确实在讨论该产品/品牌/团队；0=无关（同名技术、纯竞品、纯广告）
- sent: 对产品的态度 pos|neg|neu|mix。转述事实=neu；反讽=neg；只骂竞品不算 neg
- src: official（官方/团队）| media（新闻/通稿/转述）| kol（有自测或系统观点的博主）| user（普通用户）
- claims: 涉及的宣发点代码列表
- stance: {{代码: buy|reject|neutral}}，对 claims 中每一项的态度
- topics: ≤3 个具体中文短标签（如"刷分质疑""思考过长""价格便宜""删库"）
- comp: 提到的竞品规范名
- quote: pos/neg/mix 时摘最有代表性的原文 ≤60 字，否则 ""

宣发点：
{claims}

竞品：{competitors}

评论类记录会附带"所属帖"标题，用它理解语境。
只输出 JSON 数组，不要解释或 markdown。"""


def build_system(cfg: Config) -> str:
    p = cfg.project.get("project") or {}
    claims = cfg.taxonomy.get("claims") or {}
    claim_lines = "\n".join(f"{k}={v.get('name','')}：{v.get('desc','')}"
                            for k, v in claims.items())
    comps = cfg.taxonomy.get("competitors") or []
    return SYSTEM.format(brand=p.get("brand", "品牌"),
                         product=p.get("product", "产品"),
                         claims=claim_lines or "（未配置）",
                         competitors="、".join(comps) or "（未配置）")


def key_of(r: dict) -> str:
    return f'{r.get("platform")}|{r.get("kind")}|{r.get("id")}|{(r.get("text") or "")[:40]}'


def call(cfg: Config, system: str, item: dict) -> str | None:
    llm = cfg.llm()
    base = (llm.get("base_url") or "").rstrip("/")
    if not base or not llm.get("api_key"):
        raise SystemExit("LLM_BASE_URL / LLM_API_KEY not configured (.env)")
    body = json.dumps({
        "model": llm.get("model"),
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": json.dumps(item, ensure_ascii=False)}],
        "temperature": float(llm.get("temperature", 0)),
        "max_tokens": int(llm.get("max_tokens", 8000)),
    }).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions", body,
        {"Content-Type": "application/json",
         "Authorization": f"Bearer {llm['api_key']}"})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.load(r)["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  retry {i} {type(e).__name__} {str(e)[:100]}", flush=True)
            time.sleep(4 * (i + 1))
    return None


def parse(text: str | None) -> list[dict]:
    if not text:
        return []
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def prepare(cfg: Config, limit: int | None, done: set[str]) -> list[tuple[str, dict]]:
    rows = list(jsonl_read(cfg.normalized_dir / "combined.jsonl"))
    titles = {(r["platform"], r.get("id")): (r.get("title") or r.get("text") or "")[:80]
              for r in rows if r.get("kind") != "comment"}
    out = []
    for r in rows:
        if not re.sub(r"\[[^\]]{1,8}\]|[\U0001F000-\U0001FFFF\u2600-\u27BF\s@]",
                      "", r.get("text") or "").strip():
            continue
        k = key_of(r)
        if k in done:
            continue
        item = {
            "k": k, "平台": r.get("platform"), "类型": r.get("kind"),
            "赞": r.get("like"), "正文": (r.get("text") or "")[:700],
        }
        if r.get("title"):
            item["标题"] = r["title"][:100]
        if r.get("kind") == "comment":
            item["所属帖"] = titles.get((r["platform"], r.get("parent_id")), "")
        out.append((k, item))
        if limit and len(out) >= limit:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    out_path = cfg.labels_dir / "labels.jsonl"
    done = {d.get("key") for d in jsonl_read(out_path) if d.get("key")}
    jobs = prepare(cfg, a.limit, done)
    system = build_system(cfg)
    print(f"todo={len(jobs)} done={len(done)}")

    if a.dry_run:
        print(system)
        if jobs:
            print(json.dumps(jobs[0][1], ensure_ascii=False, indent=2))
        return

    workers = a.workers or int((cfg.project.get("llm") or {}).get("concurrency", 3))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lock_rows: list[dict] = []

    def work(job):
        k, item = job
        items = []
        # label one at a time for reliability; batch later if needed
        res = parse(call(cfg, system, item))
        for d in res:
            d["key"] = k
            items.append(d)
        return items

    with open(out_path, "a", encoding="utf-8") as fo, ThreadPoolExecutor(workers) as ex:
        for n, items in enumerate(ex.map(work, jobs), 1):
            for d in items:
                fo.write(json.dumps(d, ensure_ascii=False) + "\n")
            fo.flush()
            if n % 20 == 0:
                print(f"  {n}/{len(jobs)}", flush=True)
    print("done ->", out_path)


if __name__ == "__main__":
    main()
