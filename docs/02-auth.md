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

> **小红书建议用小号登录。** 新设备/异地登录、频繁请求容易触发风控，可能导致账号被限流或权限受限；不要用主账号。抖音、B站、知乎同理，能用小号就用小号。

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

需要两个 Cookie：`auth_token` 和 `ct0`。

### 推荐：用 Chrome 扩展导出（代采/远程协作）

1. 在 Chrome 安装 **Get your cookies**（或同类 Cookie 导出扩展）。
2. 打开并登录 `x.com`。
3. 点击扩展，导出/复制当前站点的 Cookie。
4. 把 Cookie 粘贴给部署者，由部署者填入 `.env`：

```
X_AUTH_TOKEN=...
X_CT0_TOKEN=...
```

5. **不要把账号密码发给任何人。** Cookie 等同于登录态，只发给可信的部署者；用完可以退出登录，让旧 Cookie 失效。

### 备选：开发者工具手动取

| 变量 | 来源 |
|---|---|
| `X_AUTH_TOKEN` | DevTools → Application → Cookies → x.com → `auth_token` |
| `X_CT0_TOKEN` | 同上 → `ct0` |

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
