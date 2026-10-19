# YouTube

- adapter: `youtube`
- 登录：无需
- 命令：
  - 一条龙：`.venv/bin/python -m pipeline.collect.youtube.run`
  - 搜索：`.venv/bin/python -m pipeline.collect.youtube.search`
  - 字幕/转写：`.venv/bin/python -m pipeline.collect.youtube.transcript`
  - 评论：`.venv/bin/python -m pipeline.collect.youtube.comments`
- 产物：
  - `data/raw/youtube/search_*.jsonl`
  - `data/raw/youtube/videos_*.jsonl`（含转写）
  - `data/raw/youtube/comments_*.jsonl`
- 流程：
  1. `yt-dlp "ytsearchN:<query>" --dump-json` 搜索并取元数据
  2. `youtube-transcript-api` 优先取字幕
  3. 无字幕时 `yt-dlp -x` 下音频 + `faster-whisper`
  4. `youtube-comment-downloader` 取评论（免 API key）
- 关键坑：
  - 云 IP 容易被 ban，必要时用住宅代理
  - 年龄/地区限制视频会失败，记录并跳过
  - 自动字幕可能无标点，质量差时回退 Whisper
  - 评论接口变动时优先检查 `youtube-comment-downloader` 版本
