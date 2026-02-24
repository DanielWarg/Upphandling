#!/usr/bin/env python3
"""CLI-skript för att köra alla scrapers, lagra resultat och scora leads."""

import argparse
import sys
from db import init_db, upsert_procurement, get_all_procurements, update_score
from scorer import score_procurement
from scrapers import ALL_SCRAPERS


def run(sources: list[str] | None = None, skip_scoring: bool = False):
    """Kör scrapers och scora resultat."""
    init_db()

    total_new = 0
    for scraper_cls in ALL_SCRAPERS:
        scraper = scraper_cls()
        if sources and scraper.name not in sources:
            print(f"[{scraper.name}] Hoppar över (ej vald källa)")
            continue

        print(f"\n{'='*50}")
        print(f"Kör {scraper.name} scraper...")
        print(f"{'='*50}")

        try:
            items = scraper.fetch()
            for item in items:
                upsert_procurement(item)
                total_new += 1
        except Exception as e:
            print(f"[{scraper.name}] Failed: {e}")
            continue

    print(f"\nTotalt lagrade/uppdaterade upphandlingar: {total_new}")

    if not skip_scoring:
        print("\nScorar alla upphandlingar...")
        score_all()

    print("\nKlart!")


def score_all():
    """Omscora alla upphandlingar i databasen."""
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
    print(f"Scorade {len(procurements)} upphandlingar")


def main():
    parser = argparse.ArgumentParser(description="Kör upphandlings-scrapers")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["ted", "mercell", "kommers", "eavrop"],
        help="Kör bara specifika scrapers (standard: alla)",
    )
    parser.add_argument(
        "--score-only",
        action="store_true",
        help="Bara omscora befintlig data, scrapa inte",
    )
    parser.add_argument(
        "--skip-scoring",
        action="store_true",
        help="Hoppa över scoring efter scraping",
    )
    args = parser.parse_args()

    if args.score_only:
        score_all()
    else:
        run(sources=args.sources, skip_scoring=args.skip_scoring)


if __name__ == "__main__":
    main()
