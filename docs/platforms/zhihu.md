# 知乎

- adapter: `media_crawler`（platform_code: `zhihu`）
- 登录：扫码
- 命令：`.venv/bin/python -m pipeline.collect.media_crawler zhihu search`
- 产物：`data/raw/zhihu/**/*.jsonl`
- 关键坑：
  - 回答正文与评论结构不同
  - 搜索排序受登录态影响
