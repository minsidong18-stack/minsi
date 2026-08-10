#!/usr/bin/env python3
"""Monitor Binance announcements and email newly published items."""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path


API_URL = (
    "https://www.binance.com/bapi/composite/v1/public/cms/article/"
    "catalog/list/query?catalogId=48&pageNo=1&pageSize=20"
)
STATE_FILE = Path("data/seen.json")


def fetch_announcements() -> list[dict[str, str]]:
    request = urllib.request.Request(
        API_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; BinanceAnnouncementMailer/1.0)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to fetch Binance announcements: {exc}") from exc

    articles = payload.get("data", {}).get("articles", [])
    if not articles:
        raise RuntimeError("Binance returned no announcements; response format may have changed")

    result = []
    for article in articles:
        code = str(article.get("code", "")).strip()
        title = str(article.get("title", "")).strip()
        if code and title:
            result.append(
                {
                    "code": code,
                    "title": title,
                    "url": f"https://www.binance.com/en/support/announcement/{code}",
                }
            )
    if not result:
        raise RuntimeError("No valid announcements found in Binance response")
    return result


def load_seen() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return {str(item) for item in data.get("seen_codes", [])}
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        raise RuntimeError(f"Unable to read {STATE_FILE}: {exc}") from exc


def save_seen(codes: list[str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps({"seen_codes": codes[:200]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def send_email(items: list[dict[str, str]], *, test: bool = False) -> None:
    email_address = os.environ.get("QQ_EMAIL", "").strip()
    auth_code = os.environ.get("QQ_AUTH_CODE", "").strip()
    recipient = os.environ.get("TO_EMAIL", "").strip() or email_address
    if not email_address or not auth_code or not recipient:
        raise RuntimeError("QQ_EMAIL, QQ_AUTH_CODE and TO_EMAIL (optional) must be configured")

    message = EmailMessage()
    message["From"] = email_address
    message["To"] = recipient
    if test:
        message["Subject"] = "Binance 公告监控测试成功"
        message.set_content("GitHub Actions 已成功连接 QQ 邮箱 SMTP。\n")
    else:
        message["Subject"] = f"Binance 新公告（{len(items)} 条）"
        body = ["发现 Binance 新公告：", ""]
        for item in reversed(items):
            body.extend([item["title"], item["url"], ""])
        message.set_content("\n".join(body))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.qq.com", 465, context=context, timeout=30) as smtp:
        smtp.login(email_address, auth_code)
        smtp.send_message(message)


def main() -> int:
    announcements = fetch_announcements()
    seen = load_seen()
    current_codes = [item["code"] for item in announcements]

    if os.environ.get("SEND_TEST_EMAIL", "").lower() == "true":
        send_email([], test=True)
        print("Test email sent successfully")

    if not seen:
        save_seen(current_codes)
        print(f"Initialized baseline with {len(current_codes)} announcements; no alert sent")
        return 0

    new_items = [item for item in announcements if item["code"] not in seen]
    if new_items:
        send_email(new_items)
        print(f"Sent {len(new_items)} new announcement(s)")
    else:
        print("No new announcements")

    merged = current_codes + [code for code in seen if code not in current_codes]
    save_seen(merged)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
