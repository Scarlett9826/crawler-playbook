"""Thin wrapper around the MediaCrawler submodule.

We do not vendor MediaCrawler code. We call its CLI and write JSONL into
data/raw/<platform>/. See config/platforms.yaml for the canonical commands.

Usage:
    python -m pipeline.collect.media_crawler xiaohongshu search
    python -m pipeline.collect.media_crawler bilibili detail --ids BV1xx,BV2xx
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from ..config import Config
from ..state import CrawlState

CODE = {
    "xiaohongshu": "xhs",
    "douyin": "dy",
    "bilibili": "bili",
    "zhihu": "zhihu",
    "weibo": "wb",
    "kuaishou": "ks",
    "tieba": "tieba",
}


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} [media_crawler] {msg}", flush=True)


def find_python(cfg: Config) -> list[str] | None:
    env_py = cfg.env.get("MEDIACRAWLER_PYTHON", "").strip()
    if env_py:
        return [env_py]
    venv = cfg.media_crawler_dir / ".venv" / "bin" / "python"
    if venv.exists():
        return [str(venv)]
    if shutil.which("uv"):
        return ["uv", "run", "python"]
    if shutil.which("python3"):
        return ["python3"]
    return None


def build_cmd(cfg: Config, platform: str, mode: str, *,
              keywords: str = "", ids: str = "", page: int = 1) -> list[str]:
    pc = cfg.platform(platform)
    code = pc.get("platform_code") or CODE.get(platform, platform)
    pcfg = cfg.platform_config(platform)
    login = "qrcode"
    headless = "yes" if pcfg.get("headless") else "no"
    max_notes = int(pcfg.get("max_notes", 50))
    max_comments = int(pcfg.get("max_comments", 300))

    args = [
        "main.py",
        "--platform", code,
        "--lt", login,
        "--type", mode,
        "--save_data_option", "jsonl",
        "--save_data_path", str(cfg.raw_dir / platform),
        "--get_comment", "yes",
        "--get_sub_comment", "yes",
        "--max_comments_count_singlenotes", str(max_comments),
        "--crawler_max_notes_count", str(max_notes),
        "--headless", headless,
    ]
    if mode == "search":
        if not keywords:
            keywords = ",".join(cfg.queries(platform)) or ",".join(
                cfg.keywords().get("core") or [])
        args += ["--keywords", keywords, "--start", str(page)]
    elif mode == "detail":
        if ids:
            args += ["--specified_id", ids]
    return args


def run(cfg: Config, platform: str, mode: str, *,
        keywords: str = "", ids: str = "", page: int = 1,
        dry_run: bool = False) -> int:
    py = find_python(cfg)
    if not py:
        raise SystemExit("No Python interpreter for MediaCrawler. Run ./setup.sh")
    if not (cfg.media_crawler_dir / "main.py").exists():
        raise SystemExit(
            f"MediaCrawler submodule missing at {cfg.media_crawler_dir}\n"
            "Run: git submodule update --init --recursive")

    cmd = py + build_cmd(cfg, platform, mode, keywords=keywords, ids=ids, page=page)
    log(" ".join(cmd))
    if dry_run:
        return 0

    out_dir = cfg.raw_dir / platform
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"run-{datetime.now():%Y%m%d-%H%M%S}.log"

    env = dict(os.environ)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
        if cfg.env.get(key):
            env[key] = cfg.env[key]

    with log_path.open("w", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            cmd, cwd=str(cfg.media_crawler_dir), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            logf.write(line)
            logf.flush()
            if any(k in line for k in ("ERROR", "Login", "search ", "comments", "DONE")):
                print(line.rstrip()[:200], flush=True)
        rc = proc.wait()
    log(f"exit={rc} log={log_path}")
    return rc


def refill(cfg: Config, platform: str, ids: list[str], *,
           retries: int = 2, interval: int = 8, dry_run: bool = False) -> int:
    """Re-crawl details for a list of IDs to improve comment coverage."""
    failed = 0
    for i, vid in enumerate(ids, 1):
        for attempt in range(retries + 1):
            log(f"[{i}/{len(ids)}] refill {vid} attempt {attempt + 1}")
            rc = run(cfg, platform, "detail", ids=vid, dry_run=dry_run)
            if rc == 0:
                break
            time.sleep(interval)
        else:
            failed += 1
    return failed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("platform", choices=list(CODE))
    ap.add_argument("mode", choices=["search", "detail"])
    ap.add_argument("--keywords", default="")
    ap.add_argument("--ids", default="")
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--project", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    cfg = Config(a.project)
    cfg.ensure_dirs()
    st = CrawlState(cfg.state_file,
                    overlap_hours=int((cfg.project.get("crawl") or {}).get("overlap_hours", 6)),
                    project_since=cfg.window_start)
    if not a.dry_run:
        st.mark_started(a.platform)
    rc = run(cfg, a.platform, a.mode, keywords=a.keywords, ids=a.ids, page=a.page,
             dry_run=a.dry_run)
    if not a.dry_run:
        st.mark_finished(a.platform, stats={"exit": rc}, success=(rc == 0))
    sys.exit(rc)


if __name__ == "__main__":
    main()
