#!/usr/bin/env python3
"""Background notification worker — sends pending notifications via email and Slack.

Run via cron every 15 minutes:
    */15 * * * * cd /path/to/project && python3 notify.py
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv

from db import (
    init_db, get_all_procurements, get_pipeline_items,
    get_notifications, create_notification, get_all_active_watches,
    get_connection,
)

load_dotenv()

# SMTP config
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@upphandling.local")


def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email notification. Returns True on success."""
    if not SMTP_HOST or not to:
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def send_slack(webhook_url: str, text: str) -> bool:
    """Send a Slack notification via webhook. Returns True on success."""
    if not webhook_url:
        return False

    try:
        resp = httpx.post(webhook_url, json={"text": text}, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"Slack error: {e}")
        return False


def check_deadline_warnings():
    """Create notifications for procurements with deadlines within 7 days."""
    pipeline_items = get_pipeline_items()
    now = datetime.now()
    week_from_now = now + timedelta(days=7)

    for item in pipeline_items:
        if item.get("stage") in ("vunnen", "forlorad"):
            continue

        deadline = item.get("deadline")
        if not deadline:
            continue

        try:
            dl = datetime.fromisoformat(deadline.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, TypeError):
            continue

        if now <= dl <= week_from_now:
            assigned = item.get("assigned_to")
            if not assigned:
                continue

            days_left = (dl - now).days
            create_notification(
                username=assigned,
                notification_type="deadline_warning",
                title=f"Deadline om {days_left} dagar: {(item.get('title') or '')[:60]}",
                body=f"Deadline: {deadline[:10]}. Köpare: {item.get('buyer', '')}",
                procurement_id=item["id"],
            )


def dispatch_unsent_notifications():
    """Send pending notifications via email and Slack."""
    conn = get_connection()

    # Get users with email/slack config
    users_row = conn.execute("SELECT * FROM users").fetchall()
    user_config = {u["username"]: dict(u) for u in users_row}

    # Get unsent notifications
    pending = conn.execute("""
        SELECT * FROM notifications
        WHERE sent_via_email = 0 OR sent_via_slack = 0
        ORDER BY created_at DESC
        LIMIT 100
    """).fetchall()

    for notif in pending:
        notif = dict(notif)
        username = notif["user_username"]
        config = user_config.get(username, {})

        email = config.get("email")
        slack_url = config.get("slack_webhook_url")

        email_sent = notif.get("sent_via_email", 0)
        slack_sent = notif.get("sent_via_slack", 0)

        if not email_sent and email:
            success = send_email(email, notif["title"], notif.get("body") or notif["title"])
            if success:
                conn.execute("UPDATE notifications SET sent_via_email = 1 WHERE id = ?", (notif["id"],))

        if not slack_sent and slack_url:
            text = f"*{notif['title']}*\n{notif.get('body') or ''}"
            success = send_slack(slack_url, text)
            if success:
                conn.execute("UPDATE notifications SET sent_via_slack = 1 WHERE id = ?", (notif["id"],))

    conn.commit()
    conn.close()


def main():
    """Run all notification checks and dispatch."""
    init_db()

    print(f"[{datetime.now().isoformat()}] Running notification worker...")

    print("  Checking deadline warnings...")
    check_deadline_warnings()

    print("  Dispatching unsent notifications...")
    dispatch_unsent_notifications()

    print("  Done.")


if __name__ == "__main__":
    main()
