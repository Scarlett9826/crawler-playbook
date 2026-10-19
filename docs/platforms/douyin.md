# 抖音

- adapter: `media_crawler`（platform_code: `dy`）
- 登录：扫码（可能追加手机号验证）
- 命令：`.venv/bin/python -m pipeline.collect.media_crawler douyin search`
- 产物：`data/raw/douyin/**/*.jsonl`
- 评论：详情模式
- 关键坑：
  - 视频直链有时效，转写要尽快
  - 手机号验证需人工完成
