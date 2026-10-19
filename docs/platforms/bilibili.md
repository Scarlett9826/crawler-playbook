# B站

- adapter: `media_crawler`（platform_code: `bili`）
- 登录：扫码
- 命令：`.venv/bin/python -m pipeline.collect.media_crawler bilibili search`
- 产物：`data/raw/bilibili/**/*.jsonl`
- 评论：一级/二级评论分开抓；详情模式补抓
- 关键坑：
  - 一级评论与二级评论接口不同
  - 长视频转写耗时长，建议先抽样
