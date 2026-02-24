#!/usr/bin/env python3
"""CLI script to run all scrapers, store results, and score leads."""

import argparse
import sys
from db import init_db, upsert_procurement, get_all_procurements, update_score
from scorer import score_procurement
from scrapers import ALL_SCRAPERS


def run(sources: list[str] | None = None, skip_scoring: bool = False):
    """Run scrapers and optionally score results."""
    init_db()

    total_new = 0
    for scraper_cls in ALL_SCRAPERS:
        scraper = scraper_cls()
        if sources and scraper.name not in sources:
            print(f"[{scraper.name}] Skipping (not in selected sources)")
            continue

        print(f"\n{'='*50}")
        print(f"Running {scraper.name} scraper...")
        print(f"{'='*50}")

        try:
            items = scraper.fetch()
            for item in items:
                upsert_procurement(item)
                total_new += 1
        except Exception as e:
            print(f"[{scraper.name}] Failed: {e}")
            continue

    print(f"\nTotal procurements stored/updated: {total_new}")

    if not skip_scoring:
        print("\nScoring all procurements...")
        score_all()

    print("\nDone!")


def score_all():
    """Re-score all procurements in the database."""
    init_db()
    procurements = get_all_procurements()
    for p in procurements:
        score, rationale = score_procurement(
            title=p.get("title", ""),
            description=p.get("description", ""),
            buyer=p.get("buyer", ""),
            cpv_codes=p.get("cpv_codes", ""),
        )
        update_score(p["id"], score, rationale)
    print(f"Scored {len(procurements)} procurements")


def main():
    parser = argparse.ArgumentParser(description="Run procurement scrapers")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["ted", "mercell", "kommers", "eavrop"],
        help="Only run specific scrapers (default: all)",
    )
    parser.add_argument(
        "--score-only",
        action="store_true",
        help="Only re-score existing data, don't scrape",
    )
    parser.add_argument(
        "--skip-scoring",
        action="store_true",
        help="Skip scoring after scraping",
    )
    args = parser.parse_args()

    if args.score_only:
        score_all()
    else:
        run(sources=args.sources, skip_scoring=args.skip_scoring)


if __name__ == "__main__":
    main()
