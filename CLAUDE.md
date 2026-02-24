# Upphandlingsbevakning MVP

## Project
Swedish public transport procurement monitoring tool for Hogia. Scrapes TED, Mercell, KommersAnnons, e-Avrop and scores leads by keyword relevance.

## Tech stack
- Python 3.11+
- Streamlit (frontend dashboard)
- SQLite (database, file: upphandlingar.db)
- httpx (TED API)
- Scrapling (web scraping: Mercell, KommersAnnons, e-Avrop)
- pandas (data manipulation)

## Commands
- `python3 run_scrapers.py` — fetch all sources + score
- `python3 run_scrapers.py --sources ted` — only TED
- `python3 run_scrapers.py --score-only` — re-score without scraping
- `streamlit run app.py` — launch dashboard

## Code conventions
- Swedish comments/UI text, English code identifiers
- Type hints on function signatures
- All scrapers extend `scrapers/base.py:BaseScraper`
- Database access goes through `db.py` (never raw SQL in other files)
- Scoring logic lives in `scorer.py`
- Frontend theme: black/orange/grey SaaS style, no emojis, no AI icons

## Git
- Remote: https://github.com/DanielWarg/Upphandling
- Branch: main
- .gitignore excludes __pycache__, *.db, .env, venv
