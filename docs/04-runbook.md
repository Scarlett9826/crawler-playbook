# Runbook

所有命令在仓库根目录执行。

## 0. 准备

```bash
./setup.sh
cp .env.example .env
cp config/project.example.yaml config/project.yaml
.venv/bin/python tools/preflight.py
```

## 1. 采集

### 小红书 / 抖音 / B站 / 知乎

```bash
.venv/bin/python -m pipeline.collect.media_crawler xiaohongshu search
.venv/bin/python -m pipeline.collect.media_crawler douyin search
.venv/bin/python -m pipeline.collect.media_crawler bilibili search
.venv/bin/python -m pipeline.collect.media_crawler zhihu search
```

评论补抓：

```bash
.venv/bin/python -m pipeline.collect.media_crawler bilibili detail --ids BV1xx,BV2xx
```

### YouTube

```bash
# 一条龙：搜索 + 字幕/Whisper + 评论
.venv/bin/python -m pipeline.collect.youtube.run

# 分步
.venv/bin/python -m pipeline.collect.youtube.search
.venv/bin/python -m pipeline.collect.youtube.transcript
.venv/bin/python -m pipeline.collect.youtube.comments
```

### 微博

```bash
.venv/bin/python -m pipeline.collect.weibo.crawl
```

### 微信公众号

```bash
.venv/bin/python -m pipeline.collect.wechat.crawl
```

### X

```bash
.venv/bin/python -m pipeline.collect.x.search
.venv/bin/python -m pipeline.collect.x.threads
.venv/bin/python -m pipeline.collect.x.video
```

### 视频

先准备 `data/raw/video/index.jsonl`：

```json
{"platform":"YouTube","id":"abc","url":"https://youtube.com/watch?v=abc","title":"...","author":"...","time":0}
```

```bash
.venv/bin/python -m pipeline.video.download
.venv/bin/python -m pipeline.video.transcribe
.venv/bin/python -m pipeline.video.run --offline
```

## 2. 归一化 + 审计

```bash
.venv/bin/python -m pipeline.normalize
.venv/bin/python -m pipeline.audit --strict
```

看 `data/reports/audit.md`。不达标先补抓，再往下走。

## 3. 标注

```bash
.venv/bin/python -m pipeline.label
# 小样本试跑
.venv/bin/python -m pipeline.label --limit 50
```

## 4. 分析

```bash
.venv/bin/python -m pipeline.analyze.metrics
.venv/bin/python -m pipeline.analyze.themes
.venv/bin/python -m pipeline.analyze.balanced
.venv/bin/python -m pipeline.analyze.deep
.venv/bin/python -m pipeline.analyze.negative
```

## 5. KOL

```bash
.venv/bin/python -m pipeline.kol.extract
.venv/bin/python -m pipeline.kol.aggregate
```

## 6. 报告

```bash
.venv/bin/python -m pipeline.report.make_html \
  --input data/reports/audit.md \
  --output data/reports/audit.html \
  --title "采集审计"
```

## 7. 验收

```bash
.venv/bin/python tools/check_anonymity.py
.venv/bin/python tools/check_paths.py
.venv/bin/python -m pipeline.audit --strict
```
