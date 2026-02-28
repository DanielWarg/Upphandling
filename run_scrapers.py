#!/usr/bin/env python3
"""CLI-skript för att köra alla scrapers, lagra resultat och scora leads."""

import argparse
from typing import Callable

from db import (
    init_db, upsert_procurement, get_all_procurements, update_score,
    deduplicate_procurements, ensure_pipeline_entry, seed_accounts,
    auto_link_procurements_to_accounts, get_all_active_watches, create_notification,
    archive_expired_procurements, cross_source_deduplicate, create_deadline_calendar_events,
)
from scorer import score_procurement
from scrapers import ALL_SCRAPERS


def scrape_sources(sources: list[str] | None = None, on_progress: Callable[[str], None] | None = None) -> dict[str, int]:
    """Run scrapers and upsert results. Returns {source: count}."""
    init_db()
    result_counts: dict[str, int] = {}

    for scraper_cls in ALL_SCRAPERS:
        scraper = scraper_cls()
        if sources and scraper.name not in sources:
            if on_progress:
                on_progress(f"Hoppar över {scraper.name} (ej vald)")
            continue

        if on_progress:
            on_progress(f"Hämtar från {scraper.name}...")
        else:
            print(f"\n{'='*50}\nKör {scraper.name} scraper...\n{'='*50}")

        try:
            items = scraper.fetch()
            count = 0
            for item in items:
                upsert_procurement(item)
                count += 1
            result_counts[scraper.name] = count
            if on_progress:
                on_progress(f"{scraper.name}: {count} upphandlingar hämtade")
            else:
                print(f"[{scraper.name}] {count} upphandlingar lagrade/uppdaterade")
        except Exception as e:
            if on_progress:
                on_progress(f"{scraper.name}: Fel — {e}")
            else:
                print(f"[{scraper.name}] Failed: {e}")
            result_counts[scraper.name] = 0

    return result_counts


def run_dedup(on_progress: Callable[[str], None] | None = None) -> int:
    """Deduplicate procurements within same source. Returns removed count."""
    if on_progress:
        on_progress("Deduplicerar upphandlingar...")
    else:
        print("\nDeduplicerar upphandlingar...")
    removed = deduplicate_procurements()
    msg = f"Borttagna dubbletter: {removed}"
    if on_progress:
        on_progress(msg)
    else:
        print(msg)
    return removed


def score_all(on_progress: Callable[[str], None] | None = None) -> int:
    """Score all procurements. Returns count scored."""
    init_db()
    if on_progress:
        on_progress("Scorar alla upphandlingar...")
    else:
        print("\nScorar alla upphandlingar...")
    procurements = get_all_procurements()
    for i, p in enumerate(procurements):
        score, rationale, breakdown = score_procurement(
            title=p.get("title", ""),
            description=p.get("description", ""),
            buyer=p.get("buyer", ""),
            cpv_codes=p.get("cpv_codes", ""),
        )
        update_score(p["id"], score, rationale, breakdown)
        if on_progress and (i + 1) % 50 == 0:
            on_progress(f"Scorat {i + 1}/{len(procurements)}...")
    msg = f"Scorade {len(procurements)} upphandlingar"
    if on_progress:
        on_progress(msg)
    else:
        print(msg)
    return len(procurements)


def run_ai_prefilter(ollama_model: str = "Ministral-3-14B-Instruct-2512-Q4_K_M.gguf", on_progress: Callable[[str], None] | None = None):
    """Run local AI prefilter on procurements that passed sector gate (score > 0)."""
    msg = f"Kör lokal AI-prefilter (modell: {ollama_model})..."
    if on_progress:
        on_progress(msg)
    else:
        print(f"\n{msg}")
    from analyzer import ollama_prefilter_all
    ollama_prefilter_all(model=ollama_model, min_score=1)
    if on_progress:
        on_progress("AI-prefilter klar")


def run_deep_analysis(min_score: int = 1, force: bool = False, ollama_model: str = "Ministral-3-14B-Instruct-2512-Q4_K_M.gguf", on_progress: Callable[[str], None] | None = None):
    """Run deep analysis on all AI-relevant procurements."""
    msg = f"Kör djupanalys (modell: {ollama_model})..."
    if on_progress:
        on_progress(msg)
    else:
        print(f"\n{msg}")
    from analyzer import analyze_all_relevant
    analyze_all_relevant(min_score=min_score, force=force, model=ollama_model)
    if on_progress:
        on_progress("Djupanalys klar")


def create_pipeline_entries(on_progress: Callable[[str], None] | None = None) -> int:
    """Auto-create pipeline entries for procurements with score>0 and ai_relevance=relevant."""
    if on_progress:
        on_progress("Skapar pipeline-poster...")
    else:
        print("\nSkapar pipeline-poster för relevanta upphandlingar...")
    procurements = get_all_procurements()
    count = 0
    for p in procurements:
        score = p.get("score") or 0
        ai_rel = p.get("ai_relevance")
        if score > 0 and ai_rel == "relevant":
            ensure_pipeline_entry(p["id"])
            count += 1
    msg = f"Pipeline-poster: {count} relevanta upphandlingar"
    if on_progress:
        on_progress(msg)
    else:
        print(msg)
    return count


def link_accounts(on_progress: Callable[[str], None] | None = None) -> int:
    """Seed accounts and auto-link procurements."""
    if on_progress:
        on_progress("Seedar konton och länkar upphandlingar...")
    else:
        print("\nSeedar konton och länkar upphandlingar...")
    seed_accounts()
    linked = auto_link_procurements_to_accounts()
    msg = f"Länkade {linked} upphandlingar till konton"
    if on_progress:
        on_progress(msg)
    else:
        print(msg)
    return linked


def check_watch_lists(on_progress: Callable[[str], None] | None = None) -> int:
    """Check new procurements against active watch lists and create notifications."""
    if on_progress:
        on_progress("Kontrollerar bevakningslistor...")
    else:
        print("\nKontrollerar bevakningslistor...")

    watches = get_all_active_watches()
    if not watches:
        return 0

    from datetime import datetime, timedelta
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    procurements = get_all_procurements()
    new_procs = [p for p in procurements if (p.get("created_at") or "") >= yesterday]

    if not new_procs:
        return 0

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

    msg = f"Bevakningsnotiser: {notified}"
    if on_progress:
        on_progress(msg)
    else:
        print(msg)
    return notified


def run(sources: list[str] | None = None, skip_scoring: bool = False,
        ollama_model: str = "Ministral-3-14B-Instruct-2512-Q4_K_M.gguf",
        skip_analysis: bool = False, on_progress: Callable[[str], None] | None = None):
    """Kör scrapers och scora resultat."""
    init_db()

    scrape_sources(sources, on_progress=on_progress)
    run_dedup(on_progress=on_progress)

    # Cross-source dedup
    msg = "Cross-source deduplicering..."
    if on_progress:
        on_progress(msg)
    else:
        print(f"\n{msg}")
    cross_removed = cross_source_deduplicate()
    msg = f"Cross-source dubbletter borttagna: {cross_removed}"
    if on_progress:
        on_progress(msg)
    else:
        print(msg)

    # Archive expired
    msg = "Arkiverar utgangna upphandlingar..."
    if on_progress:
        on_progress(msg)
    else:
        print(f"\n{msg}")
    archived = archive_expired_procurements()
    msg = f"Arkiverade: {archived}"
    if on_progress:
        on_progress(msg)
    else:
        print(msg)

    if not skip_scoring:
        score_all(on_progress=on_progress)

    run_ai_prefilter(ollama_model=ollama_model, on_progress=on_progress)

    if not skip_analysis:
        run_deep_analysis(ollama_model=ollama_model, on_progress=on_progress)

    create_pipeline_entries(on_progress=on_progress)
    link_accounts(on_progress=on_progress)
    check_watch_lists(on_progress=on_progress)

    # Create deadline calendar events
    msg = "Skapar kalenderhandelser for deadlines..."
    if on_progress:
        on_progress(msg)
    else:
        print(f"\n{msg}")
    cal_count = create_deadline_calendar_events()
    msg = f"Kalenderhandelser skapade: {cal_count}"
    if on_progress:
        on_progress(msg)
    else:
        print(msg)

    if on_progress:
        on_progress("Klart!")
    else:
        print("\nKlart!")


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
        default="Ministral-3-14B-Instruct-2512-Q4_K_M.gguf",
        help="LLM-modell för AI-prefilter och djupanalys (standard: Ministral-3-14B-Instruct-2512-Q4_K_M.gguf)",
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
