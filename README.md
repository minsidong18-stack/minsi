# Binance announcement email monitor

Every five minutes, GitHub Actions checks the newest Binance announcements. The
first run creates a baseline without emailing historical items. Later runs send
only newly seen announcements through QQ Mail SMTP.

## Required GitHub Actions secrets

- `QQ_EMAIL`: your full QQ email address
- `QQ_AUTH_CODE`: the QQ Mail SMTP authorization code (not your QQ password)
- `TO_EMAIL`: optional recipient; omit it to send to `QQ_EMAIL`

Never put these values in repository files, commits, issues, or chat messages.

After adding the secrets, open **Actions → Monitor Binance announcements → Run
workflow**, enable **Send a test email**, and run it once.

## Notes

- The repository should stay public to use standard GitHub-hosted runners for free.
- GitHub may delay scheduled jobs during busy periods.
- GitHub automatically disables scheduled workflows in public repositories after
  60 days without repository activity; re-enable the workflow if that happens.
