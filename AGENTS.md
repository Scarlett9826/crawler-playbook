# AGENTS.md — operating instructions for an AI agent

This repository collects and analyzes public social-media content. Your job is
to run it correctly, keep the data **complete, accurate, and fresh**, and never
leak credentials or project-identifying terms.

## 0. Hard rules

1. **Never commit secrets.** `.env`, cookies, browser profiles, tokens, and raw
   user data stay out of git. Check `.gitignore` before adding files.
2. **Anonymization scope is fixed:** only the anonymized brand and the LLM proxy
   must be replaced. Competitors, third-party auditors, benchmarks, and platform
   names stay as-is.
3. **Do not over-crawl.** Respect the request interval, retries, and per-platform
   limits in `config/project.yaml`.
4. **Do not fabricate a comparison.** A video without a self-tested, same-task,
   multi-model comparison must not produce a showcase.
5. **Never edit `vendors/`.** It is a third-party submodule with its own license.

## 1. First run

```bash
./setup.sh
cp .env.example .env
cp config/project.example.yaml config/project.yaml
.venv/bin/python tools/preflight.py
```

If preflight fails, fix the environment before crawling:

| Failure | Fix |
|---|---|
| MediaCrawler submodule missing | `git submodule update --init --recursive` |
| `ffmpeg` missing | install ffmpeg; video transcription will fail without it |
| `yt-dlp` missing | `pip install yt-dlp` |
| LLM keys missing | fill `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` in `.env` |
| X cookies missing | only needed for the X collector |

## 2. Decision tree: which collector?

Read `config/platforms.yaml` for the authoritative matrix.

```
platform → adapter
  xiaohongshu / douyin / bilibili / zhihu → media_crawler
  weibo                                  → weibo
  wechat                                 → wechat
  x                                      → x
  youtube                                → youtube
```

### MediaCrawler platforms

```bash
# search by keywords from config
.venv/bin/python -m pipeline.collect.media_crawler xiaohongshu search
.venv/bin/python -m pipeline.collect.media_crawler douyin search
.venv/bin/python -m pipeline.collect.media_crawler bilibili search
.venv/bin/python -m pipeline.collect.media_crawler zhihu search

# refill comments for specific posts
.venv/bin/python -m pipeline.collect.media_crawler bilibili detail --ids BV1xx,BV2xx
```

Raw output: `data/raw/<platform>/`.

### X

```bash
.venv/bin/python -m pipeline.collect.x.search
.venv/bin/python -m pipeline.collect.x.threads
.venv/bin/python -m pipeline.collect.x.video
```

Raw output: `data/raw/x/search_*.jsonl`, `anchors_*.jsonl`, `replies_*.jsonl`.

### YouTube

```bash
.venv/bin/python -m pipeline.collect.youtube.run
# or step by step
.venv/bin/python -m pipeline.collect.youtube.search
.venv/bin/python -m pipeline.collect.youtube.transcript
.venv/bin/python -m pipeline.collect.youtube.comments
```

Subtitles are preferred; Whisper is the fallback.

### Weibo

```bash
.venv/bin/python -m pipeline.collect.weibo.crawl
```

### WeChat

```bash
.venv/bin/python -m pipeline.collect.wechat.crawl
```

The browser opens; solve any captcha manually. Articles are written to
`data/raw/wechat/articles_*.jsonl`.

## 3. Normalize, then audit

Always run these two before analysis:

```bash
.venv/bin/python -m pipeline.normalize
.venv/bin/python -m pipeline.audit --strict
```

`normalize` writes `data/normalized/combined.jsonl` and `stats.json`.
`audit` writes `data/metrics/audit.json` and `data/reports/audit.md`.

**Stop and fix if audit fails.** Do not proceed to labeling with stale or
incomplete data. Use the recommendations in `audit.md`:

| Symptom | Action |
|---|---|
| staleness too high | re-run the platform collector; check login state |
| comment coverage low | run detail refill on high-comment posts |
| posts with 0 collected comments | refill those IDs first |
| duplicate ratio high | check dedupe keys and overlapping refills |
| unknown time ratio high | inspect the platform's time field |

Incremental state lives in `data/state/crawl_state.json`. It records the last
successful run per platform and applies `crawl.overlap_hours`.

## 4. Label and analyze

```bash
.venv/bin/python -m pipeline.label
.venv/bin/python -m pipeline.analyze.metrics
.venv/bin/python -m pipeline.analyze.themes
.venv/bin/python -m pipeline.analyze.balanced
.venv/bin/python -m pipeline.analyze.deep
.venv/bin/python -m pipeline.analyze.negative
```

The labeler uses any OpenAI-compatible endpoint. The claim taxonomy is in
`config/taxonomy.example.yaml`; change it per project.

## 5. Video pipeline

Input manifest: `data/raw/video/index.jsonl`, one JSON object per video with
`platform`, `id`, `url`, `title`, `description`, `author`, `time`.

```bash
# optional: download audio
.venv/bin/python -m pipeline.video.download

# transcribe (faster-whisper)
.venv/bin/python -m pipeline.video.transcribe

# triage + conditional routing
.venv/bin/python -m pipeline.video.run --offline
```

Routing rules (see `config/video_routing.yaml`):

- self-tested + same task + >=2 models + numbers → `showcases.jsonl` (high)
- same but no numbers → `showcases.jsonl` (low)
- single-model demo → KOL eval only, tag `single_model_demo`
- same model, different harness/version → KOL eval only, tag `usage_evidence`
- media relay / official benchmark → `claims_media.jsonl`
- tutorial / entertainment → excluded
- uncertain / visual-only → `manual_review.jsonl` (OCR reserved)

**Never** put a media relay or a single-model demo into the showcase library.

## 6. Data contract

Every normalized record has:

```
platform, platform_label, kind, id, parent_id, title, text, author,
time, time_known, like, comment_count, url, src, relevant, inherit
```

`kind` is one of `post | article | tweet | video | comment`.

Labels add:

```
key, rel, sent (pos|neg|neu|mix), src (official|media|kol|user),
claims[], stance{code: buy|reject|neutral}, topics[], comp[], quote
```

Showcase schema and KOL schema are in `docs/05-data-schema.md`.

## 7. Failure playbook (summary)

| Situation | Action |
|---|---|
| QR login expired | re-run the collector and scan again |
| captcha | complete it manually in the opened browser |
| 403 / empty results | slow down, check login, try a proxy |
| X media URL expired | download from the tweet URL, not the CDN variant |
| YouTube IP ban | use a residential proxy; skip age/region-locked videos |
| subtitle missing | fall back to Whisper |
| long video | chunk by transcript segments; keep timestamps |
| uncertain showcase | route to `manual_review.jsonl`, do not guess |

Full details: `docs/07-failure-playbook.md`.

## 8. Verification checklist

Before declaring a run done:

```bash
.venv/bin/python tools/check_anonymity.py
.venv/bin/python tools/check_paths.py
.venv/bin/python -m pipeline.audit --strict
```

- [ ] no secrets in `git status`
- [ ] audit status is `ok`
- [ ] every enabled platform has posts
- [ ] comment ratio meets target (or a refill was attempted)
- [ ] no showcase from relay / tutorial / single-model content
- [ ] reports render to `data/reports/`

## 9. Where to look

| Need | File |
|---|---|
| platform matrix | `config/platforms.yaml` |
| project settings | `config/project.yaml` |
| claim taxonomy | `config/taxonomy.example.yaml` |
| model aliases | `config/models.yaml` |
| KOL registry | `config/kol.yaml` |
| video routing | `config/video_routing.yaml` |
| schema | `docs/05-data-schema.md` |
| runbook | `docs/04-runbook.md` |
| failures | `docs/07-failure-playbook.md` |
| analysis framework | `docs/09-analysis-framework.md` |
| third-party licenses | `NOTICE` |
