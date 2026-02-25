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
- llama-server + Ministral 3 14B (lokal AI-analys via OpenAI-kompatibelt API)

## AI-analys
- **Prefilter**: Ollama/llama-server, snabb relevans-check per upphandling
- **Djupanalys**: Ministral 3 14B via llama-server med function calling (strukturerad JSON-output)
- **Modell-GGUF**: `~/.cache/models/Ministral-3-14B-Instruct-2512-Q4_K_M.gguf`
- **Endpoint**: Konfigurerbar via `LLM_BASE_URL` i `.env` (default: `http://localhost:11434/v1`)
- Starta llama-server: `llama-server --model ~/.cache/models/Ministral-3-14B-Instruct-2512-Q4_K_M.gguf --port 8081 --ctx-size 16384 --jinja`

## Kommandon
- `python3 run_scrapers.py` — hämta alla källor + scora + AI-analys
- `python3 run_scrapers.py --sources ted` — bara TED
- `python3 run_scrapers.py --score-only` — omscora utan skrapning
- `python3 run_scrapers.py --skip-analysis` — hoppa över djupanalys
- `python3 run_scrapers.py --ollama-model <namn>` — välj annan LLM-modell
- `streamlit run app.py` — starta dashboard

## Kodkonventioner
- Svensk UI-text, engelska kodidentifierare
- Typhintar på funktionssignaturer
- Alla scrapers ärver `scrapers/base.py:BaseScraper`
- Databasåtkomst går genom `db.py` (aldrig rå SQL i andra filer)
- Scoringlogik finns i `scorer.py`
- AI-analys i `analyzer.py` — `_call_ollama()` för text, `_call_ollama_tools()` för function calling
- Frontendtema: svart/orange/grått SaaS-stil, inga emojis, inga AI-ikoner

## Git
- Remote: https://github.com/DanielWarg/Upphandling
- Branch: main
- .gitignore exkluderar __pycache__, *.db, .env, venv
