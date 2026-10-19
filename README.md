# crawler-playbook

一个可复用的**社交舆情采集与分析工具**：把公开平台上的帖子、评论、文章、视频采下来，统一成一套 schema，逐条标注，再按固定框架产出报告。

核心目标只有三个词：**完整、准确、新鲜**。

- **完整**：帖子要采到，评论要补抓；用“平台报告评论数 vs 实际采到数”做覆盖率审计。
- **准确**：字段统一、去重、评论继承父帖相关性、缺时间/重复率可量化。
- **新鲜**：增量抓取、状态游标、滞后时长检查，超过阈值直接报错。

---

## 1. 平台覆盖

| 平台 | 采集方式 | 帖子 | 评论 | 视频 |
|---|---|---:|---:|---:|
| 小红书 | MediaCrawler（submodule） | ✅ | ✅ | — |
| 抖音 | MediaCrawler | ✅ | ✅ | ✅ 音频 |
| B站 | MediaCrawler | ✅ | ✅ | ✅ 音频 |
| 知乎 | MediaCrawler | ✅ | ✅ | — |
| 微博 | 自建（m.weibo.cn 接口拦截） | ✅ | ✅ | — |
| 微信公众号 | 自建（搜狗微信 + 文章页） | ✅ 正文 | — | — |
| X / Twitter | 自建（Playwright 拦截 GraphQL） | ✅ | ✅ | ✅ 音频 |
| YouTube | 自建（yt-dlp + 字幕 + 评论下载器） | ✅ | ✅ | ✅ |

> YouTube 已接入搜索、字幕/Whisper 回退、评论；命令见 `docs/04-runbook.md`。

---

## 2. 快速开始

```bash
git clone <this repo> crawler-playbook
cd crawler-playbook
./setup.sh

cp .env.example .env          # 填 LLM 与 X 凭据
cp config/project.example.yaml config/project.yaml
# 编辑 project.yaml：品牌、产品、关键词、时间窗、平台开关

.venv/bin/python tools/preflight.py
```

最小闭环：

```bash
# 1) 采集（示例：B站搜索）
.venv/bin/python -m pipeline.collect.media_crawler bilibili search

# 2) 归一化
.venv/bin/python -m pipeline.normalize

# 3) 完整度 / 新鲜度审计
.venv/bin/python -m pipeline.audit --strict

# 4) 逐条标注
.venv/bin/python -m pipeline.label

# 5) 指标
.venv/bin/python -m pipeline.analyze.metrics
.venv/bin/python -m pipeline.analyze.themes
.venv/bin/python -m pipeline.analyze.balanced
.venv/bin/python -m pipeline.analyze.deep
```

---

## 3. 目录

```
config/            配置：平台矩阵、项目、宣发点、模型名、KOL、维度、路由
pipeline/          代码
  collect/         各平台采集器
  video/           下载、转写、分诊、showcase、声明、复核
  kol/             KOL 身份、评价抽取、聚合
  analyze/         指标、主题、对称口径、补充维度、负面导出
  report/          模板渲染、HTML
templates/         报告模板
docs/              架构、认证、反爬、runbook、schema、视频、失败手册、合规、分析框架
tools/             preflight、匿名检查、路径检查
examples/demo/     合成示例
vendors/           MediaCrawler（git submodule）
data/              采集与产物（gitignore）
```

---

## 4. 数据流

```
data/raw/<platform>/*.jsonl
        │  normalize
        ▼
data/normalized/combined.jsonl  +  stats.json
        │  label
        ▼
data/labels/labels.jsonl
        │  analyze
        ▼
data/metrics/*.json
        │  report
        ▼
data/reports/*.md / *.html
```

视频：

```
data/raw/video/index.jsonl
        │ download -> transcribe
        ▼
data/raw/video/audio/*.m4a -> data/raw/video/tx/*.json
        │ video.run（分诊 + 条件路由）
        ▼
data/video/triage.jsonl
        ├─ showcases.jsonl        自测 + 同题 + 多模型
        ├─ claims_media.jsonl     官方 / 媒体声明
        └─ manual_review.jsonl    不确定 / 画面为主
```

---

## 5. 完整度 / 新鲜度审计

`pipeline.audit` 是这套工具的护栏，输出 `data/metrics/audit.json` 与 `data/reports/audit.md`：

| 指标 | 含义 | 默认阈值 |
|---|---|---|
| staleness_hours | 最新一条记录距现在多久 | ≤ 24h |
| comment_ratio | 已采评论 / 平台报告评论数 | ≥ 50% |
| duplicate_ratio | 去重率 | ≤ 15% |
| unknown_time_ratio | 缺时间记录占比 | ≤ 5% |
| posts | 每平台帖子数 | ≥ 1 |

任何一项不达标都会给出具体建议，例如“N 个有评论数的帖子一条评论都没抓到，优先补抓”。加 `--strict` 时失败会返回非零退出码，适合放进定时任务。

**增量抓取**：`data/state/crawl_state.json` 记录每个平台最后一次成功时间；下一轮从 `last_success - overlap_hours` 开始，避免漏掉迟到评论，又不会全量重抓。

---

## 6. 视频：不是每条都有 showcase

视频先分诊，再决定做什么：

```
1. 是 KOL 吗？        否 → 普通情感分析
2. 是本人实测吗？     否 → 官方/媒体声明库
3. 同题 ≥2 模型吗？   否 → 只进 KOL 评价（单模型演示 / 用法证据）
4. 有可核对数字吗？   有 → 高置信 showcase；无 → 低置信
5. 画面为主？         是 → 人工复核（OCR 接口预留）
6. 赞助/邀请码？      是 → 降权，不混入独立证据
```

---

## 7. 配置

| 文件 | 作用 |
|---|---|
| `config/platforms.yaml` | 平台 → 工具 → 命令 → 认证 → 产物 → 坑 |
| `config/project.example.yaml` | 品牌、产品、关键词、时间窗、平台开关、阈值 |
| `config/taxonomy.example.yaml` | 宣发点代码与竞品 |
| `config/models.yaml` | 模型别名归一化 |
| `config/kol.yaml` | KOL 身份与独立性 |
| `config/video_dimensions.yaml` | 视频/文本共用的评价维度 |
| `config/video_routing.yaml` | 分诊阈值与路由 |

所有路径都相对于仓库根目录，脚本可在任意机器运行。

---

## 8. 脱敏

按项目约定，仓库内只对**品牌相关标识与 LLM 代理**做替换；竞品、第三方机构、平台名保留。

```bash
python tools/check_anonymity.py   # 必须 0 命中
python tools/check_paths.py       # 必须 0 命中
```

---

## 9. 实现状态

已实现：

- MediaCrawler 封装（搜索 / 详情 / 补抓）
- X 搜索、讨论串、媒体字段提取、视频下载
- 微博、微信公众号采集
- 归一化、去重、相关性继承、增量状态
- 完整度 / 新鲜度审计
- LLM 标注（OpenAI 兼容）
- 指标 / 主题 / 对称口径 / 补充维度 / 负面导出
- YouTube 搜索、字幕、评论、Whisper 回退
- 视频下载、Whisper 转写、分诊、showcase 抽取、声明抽取、人工复核队列
- 视频 KOL 的 LLM 维度抽取（视频 + 文本统一）
- KOL 身份解析、文本评价抽取、维度聚合
- 报告模板与 HTML 渲染
- preflight、匿名检查、路径检查

预留：

- OCR（`pipeline/video/frame_text.py` 接口已留）
- 自动切片（当前只出表格 + 时间戳）

---

## 10. 合规

- MediaCrawler 是非商业学习许可；本仓库自有代码为 MIT，但不覆盖 submodule。
- 各平台 ToS 限制抓取；本工具面向研究与学习。
- 不提交任何密钥、Cookie、登录态、原始用户数据。
