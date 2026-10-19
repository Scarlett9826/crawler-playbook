# X / Twitter

- adapter: `x`
- 登录：`X_AUTH_TOKEN` + `X_CT0_TOKEN`
- 代采取 Cookie：让对方在 Chrome 安装 **Get your cookies** 扩展，登录 x.com 后导出 Cookie，粘贴给部署者；**不要索要账号密码**
- 命令：
  - `.venv/bin/python -m pipeline.collect.x.search`
  - `.venv/bin/python -m pipeline.collect.x.threads`
  - `.venv/bin/python -m pipeline.collect.x.video`
- 产物：`data/raw/x/search_*.jsonl`、`anchors_*.jsonl`、`replies_*.jsonl`
- 关键坑：
  - SearchTimeline / TweetDetail 是内部 GraphQL，字段会变
  - 视频用推文 URL 下载，不要存 CDN 直链
  - 搜索与评论区需要登录态
