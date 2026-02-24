# Upphandlingsbevakning MVP

## Projekt
Svenskt verktyg för att bevaka kollektivtrafikupphandlingar åt Hogia. Scrapar TED, Mercell, KommersAnnons, e-Avrop och scorar leads efter nyckelordsrelevans.

## Teknikstack
- Python 3.11+
- Streamlit (frontend-dashboard)
- SQLite (databas, fil: upphandlingar.db)
- httpx (TED API)
- Scrapling (webbskrapning: Mercell, KommersAnnons, e-Avrop)
- pandas (datahantering)

## Kommandon
- `python3 run_scrapers.py` — hämta alla källor + scora
- `python3 run_scrapers.py --sources ted` — bara TED
- `python3 run_scrapers.py --score-only` — omscora utan skrapning
- `streamlit run app.py` — starta dashboard

## Kodkonventioner
- Svensk UI-text, engelska kodidentifierare
- Typhintar på funktionssignaturer
- Alla scrapers ärver `scrapers/base.py:BaseScraper`
- Databasåtkomst går genom `db.py` (aldrig rå SQL i andra filer)
- Scoringlogik finns i `scorer.py`
- Frontendtema: svart/orange/grått SaaS-stil, inga emojis, inga AI-ikoner

## Git
- Remote: https://github.com/DanielWarg/Upphandling
- Branch: main
- .gitignore exkluderar __pycache__, *.db, .env, venv
