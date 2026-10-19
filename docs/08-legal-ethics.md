# 合规与伦理

## 定位

本工具面向**研究与学习**，用于理解公开讨论中的用户反馈。它不是商业监控产品，也不提供规避平台风控的能力。

## 平台条款

- 各平台 ToS 通常禁止未经许可的自动化抓取。
- robots.txt 与接口条款可能随时变化。
- 你需要在本地判断自己的使用是否合规；仓库不构成法律意见。

## 第三方许可证

| 项目 | 许可证 | 说明 |
|---|---|---|
| MediaCrawler | NON-COMMERCIAL LEARNING LICENSE 1.1 | 仅作 submodule 调用；不得按 MIT 重新分发 |
| yt-dlp | Unlicense（源码） | 打包二进制可能含 GPLv3+ |
| youtube-transcript-api | MIT | |
| youtube-comment-downloader | MIT | |
| faster-whisper | MIT | |
| Playwright | Apache-2.0 | |
| ffmpeg | 取决于构建 | |

详见 `NOTICE`。

## 数据处理

- 不提交 Cookie、token、登录态、浏览器 profile。
- 不提交原始用户数据；样本需脱敏。
- 报告中引用原话时，去掉用户名与链接。
- 删除音频/视频，只保留转写与结构化结果。

## 抓取伦理

- 控制频率，不造成平台负担。
- 不抓取私密内容、不绕过访问控制。
- 不用于骚扰、画像、定向攻击。
- 发现敏感个人信息时，删除而不是保存。
