#!/usr/bin/env python3
"""CLI-skript för att köra alla scrapers, lagra resultat och scora leads."""

import argparse
from db import (
    init_db, upsert_procurement, get_all_procurements, update_score,
    deduplicate_procurements, ensure_pipeline_entry, seed_accounts,
    auto_link_procurements_to_accounts, get_all_active_watches, create_notification,
)
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

    # Auto-create pipeline entries for relevant procurements
    print("\nSkapar pipeline-poster för relevanta upphandlingar...")
    create_pipeline_entries()

    # Seed accounts and auto-link
    print("\nSeedar konton och länkar upphandlingar...")
    seed_accounts()
    linked = auto_link_procurements_to_accounts()
    print(f"Länkade {linked} upphandlingar till konton")

    # Check watch lists
    print("\nKontrollerar bevakningslistor...")
    check_watch_lists()

    print("\nKlart!")


def score_all():
    """Omscora alla upphandlingar i databasen."""
    init_db()
    procurements = get_all_procurements()
    for p in procurements:
        score, rationale, breakdown = score_procurement(
            title=p.get("title", ""),
            description=p.get("description", ""),
            buyer=p.get("buyer", ""),
            cpv_codes=p.get("cpv_codes", ""),
        )
        update_score(p["id"], score, rationale, breakdown)
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


def create_pipeline_entries():
    """Auto-create pipeline entries for procurements with score>0 and ai_relevance=relevant."""
    procurements = get_all_procurements()
    count = 0
    for p in procurements:
        score = p.get("score") or 0
        ai_rel = p.get("ai_relevance")
        if score > 0 and ai_rel == "relevant":
            ensure_pipeline_entry(p["id"])
            count += 1
    print(f"Pipeline-poster: {count} relevanta upphandlingar")


def check_watch_lists():
    """Check new procurements against active watch lists and create notifications."""
    watches = get_all_active_watches()
    if not watches:
        return

    from datetime import datetime, timedelta
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    procurements = get_all_procurements()
    new_procs = [p for p in procurements if (p.get("created_at") or "") >= yesterday]

    if not new_procs:
        return

    notified = 0
    for watch in watches:
        for proc in new_procs:
            matched = False

            if watch["watch_type"] == "account" and watch.get("account_normalized"):
                buyer_lower = (proc.get("buyer") or "").lower()
                aliases = (watch.get("buyer_aliases") or "").lower().split(",")
                aliases.append(watch["account_normalized"])
                for alias in aliases:
                    if alias.strip() and alias.strip() in buyer_lower:
                        matched = True
                        break

            elif watch["watch_type"] == "keyword" and watch.get("keyword"):
                kw = watch["keyword"].lower()
                text = f"{proc.get('title', '')} {proc.get('description', '')}".lower()
                if kw in text:
                    matched = True

            if matched:
                create_notification(
                    username=watch["user_username"],
                    notification_type="watch_match",
                    title=f"Ny upphandling matchar bevakning: {(proc.get('title') or '')[:60]}",
                    body=f"Köpare: {proc.get('buyer', '')}. Källa: {proc.get('source', '')}",
                    procurement_id=proc["id"],
                )
                notified += 1

    print(f"Bevakningsnotiser: {notified}")


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
