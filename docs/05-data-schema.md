# 数据 Schema

## 1. 统一记录（normalized/combined.jsonl）

| 字段 | 类型 | 说明 |
|---|---|---|
| platform | str | 平台 id（xiaohongshu / douyin / bilibili / zhihu / weibo / wechat / x / youtube） |
| platform_label | str | 展示名 |
| kind | str | post / article / tweet / video / comment |
| id | str | 平台内 ID |
| parent_id | str | 评论所属帖子；帖子为空 |
| title | str | 标题 |
| text | str | 正文 |
| author | str | 作者 |
| time | int | epoch 秒 |
| time_known | bool | 是否解析出时间 |
| like | int | 点赞 |
| comment_count | int/null | 平台报告的评论数（完整度用） |
| url | str | 原链接 |
| src | str | 来源标记 |
| relevant | bool | 是否与主题相关 |
| inherit | bool | 是否从父帖继承相关性 |

## 2. 标注（labels/labels.jsonl）

| 字段 | 类型 | 说明 |
|---|---|---|
| key | str | platform\|kind\|id\|text[:40] |
| rel | 0/1 | 是否相关 |
| sent | pos/neg/neu/mix | 情感 |
| src | official/media/kol/user | 来源 |
| claims | list[str] | 涉及的宣发点代码 |
| stance | dict | {代码: buy/reject/neutral} |
| topics | list[str] | ≤3 个主题标签 |
| comp | list[str] | 竞品 |
| quote | str | 代表原话 |

## 3. Showcase（video/showcases.jsonl）

```json
{
  "showcase_id": "youtube_abc_120",
  "video": {"platform":"youtube","id":"abc","url":"...","title":"...","author":"...","published_at":0},
  "task": "3D 建模",
  "models": [{"raw":"DS V4","canonical":"DeepSeek"}],
  "setup": {"prompt":"","dataset":"","budget":"","runs":1,"notes":""},
  "results": [{"model":"DeepSeek","metric":"耗时","value":"12","unit":"分钟","evidence":"explicit"}],
  "verdict": {"winner":"DeepSeek","margin":"2x","summary":"..."},
  "timestamps": {"start":120,"end":480},
  "quotes": [{"t":130,"text":"..."}],
  "caveats": ["只跑了一次"],
  "confidence": "high|medium|low"
}
```

## 4. 官方 / 媒体声明（video/claims_media.jsonl）

```json
{
  "claim_code": "A",
  "claim": "榜单第一",
  "metric": "排名",
  "value": "46",
  "quote": "...",
  "timestamp": 12,
  "evidence": "explicit|vague",
  "video": {"platform":"...","id":"...","url":"...","title":"..."}
}
```

## 5. KOL 评价（kol/evals.jsonl）

```json
{
  "source": "text|video",
  "kol": {"kol_id":"kol_001","name":"...","independence":"independent|semi|sponsored|unknown","known":true},
  "content": {"platform":"...","id":"...","url":"...","published_at":0,"timestamps":{}},
  "overall": {"stance":"pos|neg|mix|neu","summary":"...","recommendation":"use|conditional|avoid|unknown"},
  "dimensions": [
    {"dim":"coding","verdict":"pos|neg|mix|neu","strength":"strong|moderate|weak",
     "evidence":["..."],"compared_to":["DeepSeek"]}
  ],
  "claims": {"A":"buy"},
  "methodology": {"tasks":[],"runs":null,"reproducible":"yes|no|unclear"},
  "evidence_quality": "high|medium|low"
}
```

## 6. 分诊（video/triage.jsonl）

```json
{
  "platform":"...","id":"...","url":"...","title":"...","author":"...",
  "triage": {
    "content_type":"kol_review|media_relay|tutorial|entertainment|user_complaint|tech_analysis|other",
    "is_own_test":true,
    "showcase":{"present":"yes|no|uncertain","type":"head_to_head|...","models_tested":[],
                "same_task":true,"has_numbers":true,"visual_only_suspected":false},
    "needs_ocr":false,
    "confidence":"high|medium|low",
    "reason":"...",
    "route":{"route":"showcase_extract|claims_media|manual_review|kol_eval_only|exclude","tag":"..."}
  }
}
```
