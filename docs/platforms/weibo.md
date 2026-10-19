# 微博

- adapter: `weibo`
- 登录：游客或 Cookie
- 命令：`.venv/bin/python -m pipeline.collect.weibo.crawl`
- 产物：`data/raw/weibo/posts_*.jsonl`、`comments_*.jsonl`
- 关键坑：
  - `getIndex` 与 `comments/hotflow` 是两个接口
  - 相对时间无法直接解析，需要抓取时间兜底
  - 评论为空时先登录
