# 独立云端定时推送

GitHub 的 schedule 可能延迟数小时或丢失。cron-job.org 负责独立触发，GitHub Actions 继续负责论文处理和发信。两者均在云端，Mac 关机不影响运行。GitHub 自带的 10:00、10:17、10:37 定时保留为备用。

## 1. 创建仅限该仓库的 GitHub Token

在 https://github.com/settings/personal-access-tokens/new 创建 Fine-grained personal access token：

- Resource owner：wxx7777。
- Repository access：Only select repositories，仅选择 zotero-arxiv-daily。
- Repository permissions：Actions = Read and write；Metadata 为自动只读。
- 设置合适的到期日期并记录，令牌到期前需要在 cron-job.org 更新。

令牌填入 cron-job.org 的 Authorization 请求头，不要发到聊天、仓库、URL 或截图中。现有 gh 的广泛授权不需要复制给第三方。

## 2. 创建 cron-job.org 任务

登录 https://console.cron-job.org/ ，创建一个任务：

- 名称：Zotero arXiv daily - China 10 AM。
- URL：https://api.github.com/repos/wxx7777/zotero-arxiv-daily/actions/workflows/main.yml/dispatches
- 方法：POST。
- 时区：Asia/Shanghai。
- 自定义时间：每天 10:00、10:20、10:40、11:00、11:20、11:40（首次 10:00，其余为补偿检查）。
- 请求头：Accept = application/vnd.github+json；Content-Type = application/json；Authorization = Bearer 后加新建的 Token；X-GitHub-Api-Version = 2026-03-10；User-Agent = zotero-arxiv-daily-scheduler。
- 请求正文：`{"ref":"main","inputs":{"force":false}}`。
- 开启执行失败、连续失败自动禁用、故障恢复的通知。

完整 API 创建模板见 config/cron-job.example.json，默认禁用，替换 Token 并检查设置后再启用。

## 3. 测试和验收

点击 Test run，GitHub 启动接口应返回 2xx（200 或 204，取决于 API 版本）。Actions 应出现 workflow_dispatch 运行。

当天已有 digest-sent-YYYY-MM-DD 回执时，新触发只检查后跳过，不能再次发送。只有 SMTP 接受邮件后才生成此回执；空跑的绿色工作流不会被视为已发信。没有匹配论文时也会发中文空日报。运行失败或超过 25 分钟会报告失败，后续触发可重试。

回执表示 SMTP 接受，不代表收件箱位置或已读。独立定时器绕过 GitHub 的 cron，但仍依赖 GitHub 执行器、arXiv、DeepSeek 和邮箱服务，不提供绝对准点保证。

下一次真正的自动运行仍需在次日核验。若手动确需重复发送，可在 GitHub Run workflow 中勾选 force；云端定时任务必须保持 false。
