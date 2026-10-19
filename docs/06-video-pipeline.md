# 视频流水线

## 目标

不是“给每条视频打分”，而是产出两个证据库：

1. **对比 Showcase**：谁在什么任务上对比了哪些模型、怎么测、结果如何。
2. **KOL 评价**：每个 KOL 的分维度判断、证据原话、可信度。

## 流程

```
index.jsonl
  → download（yt-dlp，抽音频）
  → transcribe（faster-whisper）
  → triage（内容类型 / 是否自测 / showcase 类型）
  → route
      ├─ showcase_extract → 校验 → 去重 → showcase
      ├─ claims_media    → 官方/媒体声明
      ├─ manual_review   → 待复核
      └─ kol_eval_only   → KOL 评价
```

## 转写策略

1. **字幕优先**（YouTube）：有字幕就不跑 ASR，快且省。
2. **Whisper 回退**：无字幕、X 视频、国内平台视频。
3. 技术名词用 `initial_prompt` 注入。
4. 长视频按转写段落切分，保留时间戳。

## 分诊规则

| 观察 | 路由 |
|---|---|
| 自测 + 同题 + ≥2 模型 + 数字 | showcase（高） |
| 自测 + 同题 + ≥2 模型 + 无数字 | showcase（低，定性） |
| 单模型演示 | 只进 KOL 评价，标签 `single_model_demo` |
| 同模型换 harness/版本 | 只进 KOL 评价，标签 `usage_evidence` |
| 媒体转述 / 官方跑分 | 官方/媒体声明库 |
| 教程 / 娱乐 | 排除 |
| 不确定 / 画面为主 | 人工复核（`needs_ocr`） |

## OCR 预留

`pipeline/video/frame_text.py` 提供 `FrameTextProvider` 接口，默认 `NoopProvider`。
启用方式：

```yaml
video:
  frame_text:
    enabled: true
    provider: rapidocr
```

showcase 抽取器已经接受 `frame_text` 字段，后续不需要改 schema。

## 切片

当前只输出表格 + 时间戳，不下载视频、不切片。
如后续需要切片，可按 `showcases.jsonl` 的 `timestamps` 用 ffmpeg 裁剪，不需要改 schema。
