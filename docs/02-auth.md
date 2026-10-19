# 认证

所有凭据只放 `.env` 或本地浏览器 profile，绝不入库。

## 小红书 / 抖音 / B站 / 知乎（MediaCrawler）

默认扫码：

```bash
.venv/bin/python -m pipeline.collect.media_crawler xiaohongshu search
```

- 首次运行会弹出浏览器，扫码登录。
- `SAVE_LOGIN_STATE=True` 会把登录态写入 `vendors/MediaCrawler/browser_data/`（已 gitignore）。
- 登录失效时重跑即可。

## 微博

`m.weibo.cn` 游客态通常可搜索；评论接口可能需要登录。

- 登录态由 Playwright 的浏览器上下文持有。
- 若评论为空，先在浏览器里登录微博，再重跑。
- 如需持久化，可把 `launch(channel="chrome", headless=True)` 改为 `launch_persistent_context` 指向 `.profiles/weibo`。

## 微信公众号

使用持久化 Chrome profile：

```
.profiles/wechat/
```

- 首次运行打开浏览器；搜狗出现验证码时手动点选。
- 文章必须通过搜狗跳转链在真实浏览器里打开，直接请求会被拦。

## X / Twitter

需要两个 Cookie：

| 变量 | 来源 |
|---|---|
| `X_AUTH_TOKEN` | DevTools → Application → Cookies → x.com → `auth_token` |
| `X_CT0_TOKEN` | 同上 → `ct0` |

写入 `.env`：

```
X_AUTH_TOKEN=...
X_CT0_TOKEN=...
```

验证：

```bash
.venv/bin/python -m pipeline.collect.x.search --dry-run
```

## LLM

任意 OpenAI 兼容端点：

```
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=...
LLM_MODEL=your-model
```

`pipeline.label`、视频分诊/showcase、KOL 抽取都走这套配置。
