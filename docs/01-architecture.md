# 架构

## 三条采集路线

| 路线 | 适用平台 | 原理 | 优点 | 风险 |
|---|---|---|---|---|
| 内部 API 封装 | 小红书、抖音、B站、知乎 | 复用 MediaCrawler 的签名与请求 | 字段全、评论接口成熟 | 依赖 submodule 与登录态 |
| 页面网络拦截 | 微博、X | Playwright 打开页面，拦截 JSON 响应 | 不依赖第三方库，接口变动可快速修 | 需要真实浏览器与登录态 |
| 页面解析 | 微信公众号 | 搜狗搜索 + 文章页 DOM | 能拿正文 | 验证码、跳转链、无评论 |

## 数据层

```
raw（平台原始）
  → normalize（统一 schema、去重、相关性继承、时间窗）
  → labels（逐条 LLM 标注）
  → metrics（聚合指标）
  → reports（模板渲染）
```

## 三个护栏

1. **完整度**：帖子数、评论覆盖率、零评论帖计数。
2. **准确度**：去重率、缺时间比例、父子挂靠。
3. **新鲜度**：最新记录滞后时长、增量游标、重叠窗口。

`pipeline.audit` 把三者量化，`--strict` 时失败即退出。

## 增量策略

`data/state/crawl_state.json` 记录每个平台最后一次成功时间。下一轮起点：

```
since = max(project.since, last_success - overlap_hours)
```

重叠窗口用于捕捉迟到评论与编辑，不会导致全量重抓。

## 视频分支

视频不走文本主链路，先分诊：

```
transcribe → triage → route
  ├─ showcase_extract
  ├─ claims_media
  ├─ kol_eval_only
  ├─ manual_review
  └─ exclude
```

## 目录职责

| 目录 | 职责 |
|---|---|
| `pipeline/collect` | 只负责采，不做分析 |
| `pipeline/normalize.py` | 只负责统一与去重 |
| `pipeline/label.py` | 只负责逐条标注 |
| `pipeline/analyze` | 只负责聚合 |
| `pipeline/report` | 只负责渲染 |
| `tools` | 环境与合规检查 |
