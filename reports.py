#!/usr/bin/env python3
"""Weekly pipeline report generation.

Usage:
    python reports.py                    # Current week
    python reports.py --week 2026-W09    # Specific week
    python reports.py --email            # Also send via email
"""

import argparse
from datetime import datetime, timedelta

from db import (
    init_db, get_pipeline_items, get_pipeline_summary,
    get_pipeline_summary_by_user, get_all_procurements,
    get_recent_activity, STAGE_LABELS,
)


def generate_report(week: str | None = None) -> dict:
    """Generate a weekly pipeline report.

    Returns dict with report sections ready for display or email.
    """
    init_db()

    # Determine week boundaries
    if week:
        year, wk = week.split("-W")
        start = datetime.strptime(f"{year}-W{wk}-1", "%Y-W%W-%w")
    else:
        now = datetime.now()
        start = now - timedelta(days=now.weekday())
    start = start.replace(hour=0, minute=0, second=0)
    end = start + timedelta(days=7)

    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    week_label = start.strftime("%Y-V%V")

    # Pipeline summary
    summary = get_pipeline_summary()
    by_user = get_pipeline_summary_by_user()

    # All pipeline items
    all_items = get_pipeline_items()
    active_stages = ["bevakad", "kvalificerad", "anbud_pagaende", "inskickad"]
    active_items = [i for i in all_items if i.get("stage") in active_stages]
    total_weighted = sum(
        (i.get("pipeline_value") or i.get("estimated_value") or 0) * (i.get("probability", 0)) / 100
        for i in active_items
    )

    # New relevant this week
    all_procs = get_all_procurements()
    new_this_week = [
        p for p in all_procs
        if (p.get("created_at") or "") >= start_str
        and (p.get("created_at") or "") < end_str
        and (p.get("score") or 0) > 0
        and p.get("ai_relevance") != "irrelevant"
    ]

    # Stage changes this week
    activities = get_recent_activity(limit=100)
    week_activities = [
        a for a in activities
        if (a.get("timestamp") or "") >= start_str
        and (a.get("timestamp") or "") < end_str
    ]

    # Upcoming deadlines
    upcoming_deadlines = []
    for item in active_items:
        dl = item.get("deadline")
        if dl and start_str <= dl[:10] <= (start + timedelta(days=14)).strftime("%Y-%m-%d"):
            upcoming_deadlines.append(item)

    # Win/loss
    won = [i for i in all_items if i.get("stage") == "vunnen"]
    lost = [i for i in all_items if i.get("stage") == "forlorad"]

    report = {
        "week": week_label,
        "period": f"{start_str} — {end_str}",
        "pipeline_total": len(active_items),
        "pipeline_weighted_value": total_weighted,
        "new_relevant_count": len(new_this_week),
        "new_relevant": new_this_week[:10],
        "activity_count": len(week_activities),
        "activities": week_activities[:20],
        "upcoming_deadlines": sorted(upcoming_deadlines, key=lambda i: i.get("deadline") or "")[:10],
        "stage_summary": {
            STAGE_LABELS.get(s, s): summary.get(s, {}).get("count", 0)
            for s in active_stages
        },
        "by_user": by_user,
        "won_count": len(won),
        "lost_count": len(lost),
        "win_rate": f"{len(won) / (len(won) + len(lost)) * 100:.0f}%" if (len(won) + len(lost)) > 0 else "—",
    }

    return report


def format_report_text(report: dict) -> str:
    """Format report as plain text for email/CLI."""
    lines = [
        f"VECKORAPPORT — {report['week']}",
        f"Period: {report['period']}",
        "=" * 50,
        "",
        f"PIPELINE-ÖVERSIKT",
        f"  Aktiva deals: {report['pipeline_total']}",
        f"  Viktat pipeline-värde: {report['pipeline_weighted_value']:,.0f} SEK",
        f"  Vunna: {report['won_count']}  Förlorade: {report['lost_count']}  Win rate: {report['win_rate']}",
        "",
        "FÖRDELNING PER STEG:",
    ]

    for stage, count in report["stage_summary"].items():
        lines.append(f"  {stage}: {count}")

    lines.extend([
        "",
        f"NYA RELEVANTA UPPHANDLINGAR ({report['new_relevant_count']} st):",
    ])
    for p in report.get("new_relevant", []):
        lines.append(f"  - {p.get('title', '')[:60]} ({p.get('buyer', '')})")

    lines.extend([
        "",
        f"KOMMANDE DEADLINES ({len(report.get('upcoming_deadlines', []))} st):",
    ])
    for item in report.get("upcoming_deadlines", []):
        lines.append(f"  - {item.get('deadline', '')[:10]}: {item.get('title', '')[:60]}")

    lines.extend([
        "",
        f"AKTIVITET DENNA VECKA ({report['activity_count']} händelser)",
        "",
        "KAM-FÖRDELNING:",
    ])
    for user, stages in report.get("by_user", {}).items():
        total = sum(d.get("count", 0) for d in stages.values())
        weighted = sum(d.get("weighted_value", 0) for d in stages.values())
        lines.append(f"  {user}: {total} deals, {weighted:,.0f} SEK viktat")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generera veckorapport")
    parser.add_argument("--week", help="Vecka i format YYYY-WNN (t.ex. 2026-W09)")
    parser.add_argument("--email", action="store_true", help="Skicka rapport via e-post")
    args = parser.parse_args()

    report = generate_report(week=args.week)
    text = format_report_text(report)
    print(text)

    if args.email:
        from notify import send_email
        # Send to all users with email
        from db import get_connection
        conn = get_connection()
        users = conn.execute("SELECT email FROM users WHERE email IS NOT NULL").fetchall()
        conn.close()

        for user in users:
            if user["email"]:
                send_email(user["email"], f"Veckorapport {report['week']}", text)
                print(f"Skickade till {user['email']}")


if __name__ == "__main__":
    main()
