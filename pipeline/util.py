"""Small shared helpers: text cleaning, time parsing, JSONL IO."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


def clean_text(value: Any) -> str:
    """Strip HTML, collapse whitespace. Keeps CJK punctuation."""
    if value is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = text.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", text).strip()


def to_epoch(value: Any) -> int | None:
    """Accept seconds, milliseconds, microseconds, or a datetime string."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return int(value.timestamp())
    try:
        num = float(value)
    except (TypeError, ValueError):
        return parse_time(value)
    if num > 1e17:        # microseconds
        num /= 1_000_000
    elif num > 1e14:      # microseconds-ish
        num /= 1_000_000
    elif num > 1e12:      # milliseconds
        num /= 1000
    if num < 1e9:         # nonsense
        return None
    return int(num)


_CN_DATE = re.compile(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})")
_RFC = "%a %b %d %H:%M:%S %z %Y"


def parse_time(value: Any, tz_offset_hours: int = 8) -> int | None:
    """Parse common Chinese and X/RFC date strings."""
    if not value:
        return None
    s = str(value).strip()
    try:
        return int(datetime.strptime(s, _RFC).timestamp())
    except ValueError:
        pass
    m = _CN_DATE.search(s)
    if m:
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                          tzinfo=timezone(timedelta(hours=tz_offset_hours)))
            return int(dt.timestamp())
        except ValueError:
            return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt).replace(
                tzinfo=timezone(timedelta(hours=tz_offset_hours)))
            return int(dt.timestamp())
        except ValueError:
            continue
    return None


def epoch_to_iso(value: int | None, tz_offset_hours: int = 8) -> str:
    if not value:
        return ""
    tz = timezone(timedelta(hours=tz_offset_hours))
    return datetime.fromtimestamp(value, tz).strftime("%Y-%m-%d %H:%M:%S")


def now_epoch() -> int:
    return int(time.time())


def stable_hash(*parts: Any, n: int = 16) -> str:
    h = hashlib.sha1()
    for p in parts:
        h.update(str(p).encode("utf-8", "ignore"))
        h.update(b"\x00")
    return h.hexdigest()[:n]


def jsonl_read(path: str | Path) -> Iterable[dict]:
    p = Path(path)
    if not p.exists():
        return
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def jsonl_write(path: str | Path, rows: Iterable[dict]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def json_read(path: str | Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def json_write(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def compile_any(patterns: list[str] | None) -> re.Pattern | None:
    if not patterns:
        return None
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.I)


def chunks(items: list, size: int) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i:i + size]
