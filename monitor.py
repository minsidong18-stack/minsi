#!/usr/bin/env python3
"""Monitor Binance announcements and selected Binance Square posts."""

from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
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

NEW_COIN_KEYWORDS = (
    "首个上线",
    "新币上线",
    "上线新币",
    "上线现货",
    "上线合约",
    "开放交易",
    "交易开放",
    "盘前交易",
    "launchpool",
    "hodler",
    "megadrop",
    "空投",
    "will list",
    "listing",
)
TRADING_COMPETITION_KEYWORDS = (
    "交易赛",
    "交易大赛",
    "交易竞赛",
    "交易挑战",
    "排行榜开启",
    "冲榜",
    "trading competition",
    "leaderboard",
)
COMPETITION_CONTEXT = ("交易", "合约", "现货", "双币投资")
COMPETITION_REWARD = ("奖池", "排行榜", "竞赛", "大赛", "挑战")
ALPHA_CONTEXT = ("币安 alpha", "binance alpha")
ALPHA_ACTION = ("上线", "交易开放", "空投", "申领代币", "新币")


def fetch_json(url: str, label: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Clienttype": "web",
            "User-Agent": "Mozilla/5.0 (compatible; BinanceMonitor/2.0)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise RuntimeError(f"Unable to fetch {label}: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} returned an unexpected response")
    return payload


def fetch_announcements() -> list[dict[str, str]]:
    payload = fetch_json(ANNOUNCEMENT_API_URL, "Binance announcements")
    articles = payload.get("data", {}).get("articles", [])
    if not articles:
        raise RuntimeError(
            "Binance returned no announcements; response format may have changed"
        )

    result = []
    for article in articles:
        code = str(article.get("code", "")).strip()
        title = str(article.get("title", "")).strip()
        if code and title:
            result.append(
                {
                    "id": code,
                    "source": "币安新币公告",
                    "title": title,
                    "url": f"https://www.binance.com/zh-CN/support/announcement/{code}",
                }
            )
    if not result:
        raise RuntimeError("No valid announcements found in Binance response")
    return result


def fetch_square_posts() -> list[dict[str, str]]:
    payload = fetch_json(SQUARE_API_URL, "Binance Square posts")
    if not payload.get("success"):
        raise RuntimeError(
            f"Binance Square returned error code {payload.get('code', 'unknown')}"
        )

    contents = payload.get("data", {}).get("contents", [])
    if not contents:
        raise RuntimeError(
            "Binance Square returned no posts; response format may have changed"
        )

    result = []
    for post in contents:
        post_id = str(post.get("id", "")).strip()
        text = str(post.get("bodyTextOnly") or post.get("title") or "").strip()
        text = re.sub(r"\s+", " ", text)
        if post_id and text:
            result.append(
                {
                    "id": post_id,
                    "source": "币安Binance华语 · 广场",
                    "title": text,
                    "url": f"https://www.binance.com/zh-CN/square/post/{post_id}",
                }
            )
    if not result:
        raise RuntimeError("No valid Binance Square posts found in response")
    return result


def square_post_is_relevant(text: str) -> bool:
    normalized = text.casefold()
    if any(keyword in normalized for keyword in NEW_COIN_KEYWORDS):
        return True
    if any(word in normalized for word in ALPHA_CONTEXT) and any(
        word in normalized for word in ALPHA_ACTION
    ):
        return True
    if any(keyword in normalized for keyword in TRADING_COMPETITION_KEYWORDS):
        return True
    return any(word in normalized for word in COMPETITION_CONTEXT) and any(
        word in normalized for word in COMPETITION_REWARD
    )


def load_state() -> tuple[set[str], set[str], bool]:
    if not STATE_FILE.exists():
        return set(), set(), False
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        announcement_codes = data.get(
            "seen_announcement_codes", data.get("seen_codes", [])
        )
        square_initialized = "seen_square_post_ids" in data
        return (
            {str(item) for item in announcement_codes},
            {str(item) for item in data.get("seen_square_post_ids", [])},
            square_initialized,
        )
    except (OSError, json.JSONDecodeError, AttributeError, TypeError) as exc:
        raise RuntimeError(f"Unable to read {STATE_FILE}: {exc}") from exc


def merge_recent(current: list[str], seen: set[str], limit: int = 300) -> list[str]:
    return (current + [item for item in seen if item not in current])[:limit]


def save_state(announcement_codes: list[str], square_post_ids: list[str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "seen_announcement_codes": announcement_codes[:300],
        "seen_square_post_ids": square_post_ids[:300],
    }
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def send_email(items: list[dict[str, str]], *, test: bool = False) -> None:
    email_address = os.environ.get("QQ_EMAIL", "").strip()
    auth_code = "".join(os.environ.get("QQ_AUTH_CODE", "").split())
    recipient = os.environ.get("TO_EMAIL", "").strip() or email_address
    if not email_address or not auth_code or not recipient:
        raise RuntimeError("QQ_EMAIL, QQ_AUTH_CODE and TO_EMAIL (optional) must be configured")

    message = EmailMessage()
    message["From"] = email_address
    message["To"] = recipient
    if test:
        message["Subject"] = "Binance 监控测试成功"
        message.set_content(
            "GitHub Actions 已成功连接 QQ 邮箱 SMTP。\n"
            "监控来源：币安新币公告 + 币安Binance华语广场。\n"
            "广场筛选：新币、Alpha、空投、Launchpool、交易赛和排行榜。\n"
        )
    else:
        message["Subject"] = f"Binance 重要动态（{len(items)} 条）"
        body = ["发现新的 Binance 重要动态：", ""]
        for item in reversed(items):
            body.extend(
                [
                    f"【{item['source']}】",
                    item["title"],
                    item["url"],
                    "",
                ]
            )
        message.set_content("\n".join(body))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.qq.com", 465, context=context, timeout=30) as smtp:
            smtp.login(email_address, auth_code)
            smtp.send_message(message)
        return
    except (smtplib.SMTPException, OSError) as exc:
        print(f"QQ SMTP port 465 failed ({type(exc).__name__}); trying port 587")

    try:
        with smtplib.SMTP("smtp.qq.com", 587, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(email_address, auth_code)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise RuntimeError(f"QQ SMTP failed on ports 465 and 587: {exc}") from exc


def main() -> int:
    announcements = fetch_announcements()
    try:
        square_posts = fetch_square_posts()
        square_available = True
    except RuntimeError as exc:
        square_posts = []
        square_available = False
        print(f"WARNING: {exc}; continuing with announcements only", file=sys.stderr)

    seen_announcements, seen_square_posts, square_initialized = load_state()
    current_announcement_ids = [item["id"] for item in announcements]
    current_square_ids = [item["id"] for item in square_posts]

    if os.environ.get("SEND_TEST_EMAIL", "").lower() == "true":
        send_email([], test=True)
        print("Test email sent successfully")

    alerts: list[dict[str, str]] = []
    if seen_announcements:
        alerts.extend(
            item for item in announcements if item["id"] not in seen_announcements
        )
    else:
        print(
            f"Initialized announcement baseline with {len(current_announcement_ids)} items"
        )

    if square_available:
        if square_initialized:
            new_square_posts = [
                item for item in square_posts if item["id"] not in seen_square_posts
            ]
            relevant_posts = [
                item for item in new_square_posts if square_post_is_relevant(item["title"])
            ]
            alerts.extend(relevant_posts)
            print(
                f"Checked {len(new_square_posts)} new Square post(s); "
                f"{len(relevant_posts)} matched the filters"
            )
        else:
            print(
                f"Initialized Binance Square baseline with {len(current_square_ids)} posts; "
                "no historical Square alert sent"
            )

    if alerts:
        send_email(alerts)
        print(f"Sent {len(alerts)} important Binance update(s)")
    else:
        print("No new important Binance updates")

    merged_announcements = merge_recent(current_announcement_ids, seen_announcements)
    merged_square = (
        merge_recent(current_square_ids, seen_square_posts)
        if square_available
        else list(seen_square_posts)
    )
    save_state(merged_announcements, merged_square)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
