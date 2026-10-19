# 小红书

- adapter: `media_crawler`（platform_code: `xhs`）
- 登录：扫码
- 命令：`.venv/bin/python -m pipeline.collect.media_crawler xiaohongshu search`
- 产物：`data/raw/xiaohongshu/**/*.jsonl`
- 评论：详情模式；单帖上限见 `config/project.yaml`
- 关键坑：
  - `xsec_token` 随搜索结果下发，详情必须带 `xsec_source`
  - 未登录时详情为空
  - 滑块验证需人工完成
