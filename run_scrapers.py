#!/usr/bin/env python3
"""CLI-skript för att köra alla scrapers, lagra resultat och scora leads."""

import argparse
from db import init_db, upsert_procurement, get_all_procurements, update_score, deduplicate_procurements
from scorer import score_procurement
from scrapers import ALL_SCRAPERS


def run(sources: list[str] | None = None, skip_scoring: bool = False, ollama_model: str = "ministral-3-14b", skip_analysis: bool = False):
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

    # Dedup before scoring
    print("\nDeduplicerar upphandlingar...")
    removed = deduplicate_procurements()
    print(f"Borttagna dubbletter: {removed}")

    if not skip_scoring:
        print("\nScorar alla upphandlingar...")
        score_all()

    run_ai_prefilter(ollama_model=ollama_model)

    if not skip_analysis:
        run_deep_analysis(ollama_model=ollama_model)

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


def run_ai_prefilter(ollama_model: str = "ministral-3-14b"):
    """Run local AI prefilter on procurements that passed sector gate (score > 0)."""
    print(f"\nKör lokal AI-prefilter (Ollama, modell: {ollama_model}) på gate-passerade upphandlingar...")
    from analyzer import ollama_prefilter_all
    ollama_prefilter_all(model=ollama_model, min_score=1)


def run_deep_analysis(min_score: int = 1, force: bool = False, ollama_model: str = "ministral-3-14b"):
    """Run Ollama deep analysis on all AI-relevant procurements."""
    print(f"\nKör Ollama-djupanalys (modell: {ollama_model}) på relevanta upphandlingar...")
    from analyzer import analyze_all_relevant
    analyze_all_relevant(min_score=min_score, force=force, model=ollama_model)


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
    parser.add_argument(
        "--ollama-model",
        default="ministral-3-14b",
        help="LLM-modell för AI-prefilter och djupanalys (standard: ministral-3-14b)",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Hoppa över Ollama-djupanalys",
    )
    args = parser.parse_args()

    if args.score_only:
        score_all()
        run_ai_prefilter(ollama_model=args.ollama_model)
        if not args.skip_analysis:
            run_deep_analysis(ollama_model=args.ollama_model)
    else:
        run(sources=args.sources, skip_scoring=args.skip_scoring, ollama_model=args.ollama_model, skip_analysis=args.skip_analysis)


if __name__ == "__main__":
    main()
