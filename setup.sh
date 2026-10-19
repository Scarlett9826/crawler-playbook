#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "== 1/5 submodules =="
if [ -f .gitmodules ]; then
  git submodule update --init --recursive
fi

echo "== 2/5 python venv =="
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

echo "== 3/5 playwright chromium =="
python -m playwright install chromium >/dev/null 2>&1 || true

echo "== 4/5 MediaCrawler venv =="
if [ -f vendors/MediaCrawler/main.py ]; then
  if [ ! -x vendors/MediaCrawler/.venv/bin/python ]; then
    python3 -m venv vendors/MediaCrawler/.venv
    vendors/MediaCrawler/.venv/bin/python -m pip install -q --upgrade pip
    if [ -f vendors/MediaCrawler/requirements.txt ]; then
      vendors/MediaCrawler/.venv/bin/python -m pip install -q -r vendors/MediaCrawler/requirements.txt || \
        echo "  warning: MediaCrawler deps failed; try 'cd vendors/MediaCrawler && uv sync'"
    fi
  fi
else
  echo "  MediaCrawler submodule missing; run: git submodule update --init"
fi

echo "== 5/5 system checks =="
command -v ffmpeg >/dev/null && echo "  ffmpeg: $(ffmpeg -version 2>/dev/null | head -1)" || echo "  ffmpeg: MISSING (video transcription will fail)"
python tools/preflight.py || true

echo
echo "Done. Next:"
echo "  cp .env.example .env    # fill credentials"
echo "  cp config/project.example.yaml config/project.yaml"
echo "  .venv/bin/python -m pipeline.audit --project config/project.yaml"
