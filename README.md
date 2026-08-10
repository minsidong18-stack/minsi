# Binance 重要动态邮件监控

GitHub Actions 每五分钟检查两个来源：

- 币安“新币上线”官方公告
- 币安广场官方认证账号“币安Binance华语”

广场帖子仅在包含新币、Alpha、空投、Launchpool、交易赛、排行榜或奖池等
信号时发送邮件。程序会按公告编号和广场帖子编号分别去重。第一次启用一个
来源时只建立基线，不补发历史内容。

## GitHub Actions Secrets

- `QQ_EMAIL`：完整的 QQ 邮箱地址
- `QQ_AUTH_CODE`：QQ 邮箱 SMTP 授权码，不是 QQ 密码
- `TO_EMAIL`：可选的收件地址；不添加时默认发给 `QQ_EMAIL`

不要把这些值写进仓库文件、提交、Issue 或聊天消息。

添加完成后，打开 **Actions → Monitor Binance announcements → Run workflow**，
如需测试邮件可勾选 **Send a test email** 后运行一次。

## 注意事项

- 仓库保持公开，可继续免费使用标准 GitHub-hosted runner。
- GitHub 繁忙时，定时任务可能延迟。
- 币安广场使用公开网站数据地址。如果币安修改地址，程序会记录警告，原有
  的官方公告检查仍会继续运行。
- GitHub 可能在公开仓库连续 60 天没有活动后暂停定时工作流；届时重新启用
  即可。
