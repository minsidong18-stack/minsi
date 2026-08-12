#!/usr/bin/env python3
"""Send a daily health report for the Binance monitor."""

from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path


ANNOUNCEMENT_API_URL = (
    "https://www.binance.com/bapi/composite/v1/public/cms/article/"
    "catalog/list/query?catalogId=48&pageNo=1&pageSize=20"
)
SQUARE_API_URL = (
    "https://www.binance.com/bapi/composite/v2/friendly/pgc/content/"
    "queryUserProfilePageContentsWithFilter?username=binancezh"
    "&timeOffset=-1&filterType=ALL"
)
STATE_FILE = Path("data/seen.json")
CHINA_TZ = timezone(timedelta(hours=8), name="CST")


def fetch_count(url: str, path: tuple[str, ...]) -> int:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Clienttype": "web",
            "User-Agent": "Mozilla/5.0 (compatible; BinanceMonitorHealth/1.0)",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.load(response)
    for key in path:
        value = value[key]
    if not isinstance(value, list) or not value:
        raise RuntimeError("返回的数据列表为空或格式已经改变")
    return len(value)


def check_source(label: str, url: str, path: tuple[str, ...]) -> tuple[str, bool]:
    try:
        count = fetch_count(url, path)
        return f"{label}：正常（本次读取 {count} 条）", True
    except (KeyError, TypeError, ValueError, RuntimeError, OSError, urllib.error.URLError) as exc:
        return f"{label}：异常（{type(exc).__name__}）", False


def state_summary() -> str:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        announcements = data.get("seen_announcement_codes", data.get("seen_codes", []))
        square_posts = data.get("seen_square_post_ids", [])
        return f"历史记录：公告 {len(announcements)} 条，广场帖子 {len(square_posts)} 条"
    except (OSError, json.JSONDecodeError, AttributeError, TypeError):
        return "历史记录：异常（无法读取去重记录）"


def send_report(body: str, healthy: bool) -> None:
    email_address = os.environ.get("QQ_EMAIL", "").strip()
    auth_code = "".join(os.environ.get("QQ_AUTH_CODE", "").split())
    recipient = os.environ.get("TO_EMAIL", "").strip() or email_address
    if not email_address or not auth_code or not recipient:
        raise RuntimeError("QQ_EMAIL、QQ_AUTH_CODE 或收件地址尚未配置")

    message = EmailMessage()
    message["From"] = email_address
    message["To"] = recipient
    message["Subject"] = "Binance 监控每日健康报告" if healthy else "⚠ Binance 监控部分异常"
    message.set_content(body)

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465, context=context, timeout=30) as smtp:
            smtp.login(email_address, auth_code)
            smtp.send_message(message)
        return
    except (smtplib.SMTPException, OSError):
        pass

    with smtplib.SMTP("smtp.qq.com", 587, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(email_address, auth_code)
        smtp.send_message(message)


def main() -> None:
    announcement_line, announcement_ok = check_source(
        "官方新币公告", ANNOUNCEMENT_API_URL, ("data", "articles")
    )
    square_line, square_ok = check_source(
        "币安华语广场", SQUARE_API_URL, ("data", "contents")
    )
    now = datetime.now(CHINA_TZ)
    healthy = announcement_ok and square_ok
    conclusion = "两个数据源均正常，监控任务仍在运行。" if healthy else "至少一个数据源异常，请查看 GitHub Actions。"
    body = "\n".join(
        [
            f"检查时间：{now:%Y-%m-%d %H:%M:%S %Z}",
            announcement_line,
            square_line,
            state_summary(),
            f"结论：{conclusion}",
        ]
    )
    send_report(body, healthy)
    print(body)
    print("Health report email sent successfully")


if __name__ == "__main__":
    main()
