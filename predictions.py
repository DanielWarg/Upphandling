"""Historical pattern analysis for predicting future procurements."""

from datetime import datetime
from collections import defaultdict

from db import get_all_procurements, get_all_accounts


def predict_reprocurements() -> list[dict]:
    """Analyze historical procurement patterns to predict future reprocurements.

    Logic: Group procurements by buyer/account, find repeated similar procurements,
    calculate average interval, predict next occurrence.
    """
    procurements = get_all_procurements()
    accounts = get_all_accounts()

    # Group procurements by account (buyer)
    by_buyer: dict[str, list[dict]] = defaultdict(list)
    for p in procurements:
        buyer = (p.get("buyer") or "").lower().strip()
        if buyer and p.get("published_date"):
            by_buyer[buyer].append(p)

    predictions: list[dict] = []

    for buyer, procs in by_buyer.items():
        if len(procs) < 2:
            continue

        # Sort by publication date
        procs.sort(key=lambda p: p.get("published_date") or "")

        # Find pairs with similar titles (simple word overlap)
        seen_clusters: list[list[dict]] = []
        for p in procs:
            title_words = set(p.get("title", "").lower().split())
            placed = False
            for cluster in seen_clusters:
                ref_words = set(cluster[0].get("title", "").lower().split())
                overlap = len(title_words & ref_words) / max(len(title_words | ref_words), 1)
                if overlap > 0.4:
                    cluster.append(p)
                    placed = True
                    break
            if not placed:
                seen_clusters.append([p])

        # For clusters with 2+ entries, calculate intervals
        for cluster in seen_clusters:
            if len(cluster) < 2:
                continue

            dates = []
            for p in cluster:
                try:
                    d = datetime.fromisoformat(p["published_date"][:10])
                    dates.append(d)
                except (ValueError, TypeError):
                    continue

            if len(dates) < 2:
                continue

            dates.sort()
            intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates) - 1)]
            avg_days = sum(intervals) / len(intervals)
            avg_years = round(avg_days / 365.25, 1)

            if avg_years < 1 or avg_years > 15:
                continue

            # Predict next
            last_date = max(dates)
            from datetime import timedelta
            predicted = last_date + timedelta(days=avg_days)

            # Find account name
            account_name = buyer.title()
            for acc in accounts:
                if acc.get("normalized_name") and acc["normalized_name"] in buyer:
                    account_name = acc["name"]
                    break

            predictions.append({
                "title": cluster[0].get("title", "")[:80],
                "account": account_name,
                "avg_years": avg_years,
                "predicted_date": predicted.strftime("%Y-%m-%d"),
                "last_date": last_date.strftime("%Y-%m-%d"),
                "occurrences": len(dates),
            })

    # Sort by predicted date
    predictions.sort(key=lambda p: p.get("predicted_date", "9999"))
    return predictions
