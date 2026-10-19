# 微信公众号

- adapter: `wechat`
- 登录：持久化浏览器 profile（`.profiles/wechat/`）
- 命令：`.venv/bin/python -m pipeline.collect.wechat.crawl`
- 产物：`data/raw/wechat/articles_*.jsonl`
- 关键坑：
  - 搜狗微信有验证码，需人工过
  - 文章必须跟随搜狗跳转链在真实浏览器打开
  - 无评论区，只有正文
