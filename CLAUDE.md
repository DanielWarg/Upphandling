# Upphandlingsbevakning — Fas2 Säljstöd

## Projekt
Svenskt verktyg för att bevaka upphandlingar inom ledarskap, utbildning och organisationsutveckling åt HAST Utveckling. Scrapar TED, Mercell, KommersAnnons, e-Avrop och scorar leads. Fas2 utökar med flerannvändarstöd, pipeline-hantering, kundkonton, samarbete och notiser för HAST:s säljteam (3 KAM + 1 säljchef).

## Teknikstack
- Python 3.11+
- Streamlit (frontend-dashboard, multi-page)
- SQLite (databas, fil: upphandlingar.db, WAL-mode)
- httpx (TED API)
- Scrapling (webbskrapning: Mercell, KommersAnnons, e-Avrop)
- pandas (datahantering)
- llama-server + Ministral 3 14B (lokal AI-analys via OpenAI-kompatibelt API)
- streamlit-authenticator (auth, bcrypt, cookie-sessions)
- streamlit-sortables (drag & drop kanban)
- streamlit-calendar (FullCalendar.js)

## AI-analys
- **Modell**: Ministral 3 14B (ENDA modellen vi kör — levererar bäst resultat)
- **Server**: llama-server (INTE Ollama, INTE Qwen, INTE Gemini)
- **Prefilter**: Snabb relevans-check per upphandling — filtrerar brus efter nyckelordsscoringen
- **Djupanalys**: Function calling med strukturerad JSON-output (kravsammanfattning, matchning, prisstrategi, anbudshjälp)
- **GGUF**: `~/.cache/models/Ministral-3-14B-Instruct-2512-Q4_K_M.gguf`
- **Endpoint**: `LLM_BASE_URL=http://localhost:8081/v1` i `.env`
- **Starta**: `llama-server --model ~/.cache/models/Ministral-3-14B-Instruct-2512-Q4_K_M.gguf --port 8081 --ctx-size 16384 --jinja`
- **OBS**: Använd ALDRIG andra modeller (Qwen, Llama etc). Ministral 3 14B är testad och validerad.

## Kommandon
- `python3 run_scrapers.py` — hämta alla källor + scora + AI-analys + pipeline + konto-länkning
- `python3 run_scrapers.py --sources ted` — bara TED
- `python3 run_scrapers.py --score-only` — omscora utan skrapning
- `python3 run_scrapers.py --skip-analysis` — hoppa över djupanalys
- `python3 run_scrapers.py --ollama-model <namn>` — välj annan LLM-modell
- `streamlit run app.py` — starta dashboard
- `python3 migrate.py` — migrera databas (Fas1 → Fas2)
- `python3 migrate.py --status` — visa schemaversion
- `python3 notify.py` — skicka väntande notiser (e-post/Slack)
- `python3 reports.py` — generera veckorapport
- `python3 reports.py --week 2026-W09` — specifik vecka
- `python3 reports.py --email` — skicka rapport via e-post

## Filstruktur
```
├── app.py                 # Streamlit dashboard (auth gate + routing)
├── auth.py                # Autentisering (streamlit-authenticator wrapper)
├── db.py                  # SQLite schema + CRUD (alla tabeller)
├── scorer.py              # Nyckelordsscoring (2-stegs gate + scoring)
├── analyzer.py            # AI-analys (Ollama/Gemini)
├── predictions.py         # Historisk mönsteranalys + prediktion
├── reports.py             # Veckorapport-generering (CLI + e-post)
├── notify.py              # Bakgrundsnotiser (e-post/Slack, cron)
├── migrate.py             # DB-migreringshanterare
├── run_scrapers.py        # CLI-orchestrator (scraping + pipeline + konto-länkning)
├── config/
│   └── users.yaml         # Användarkonfiguration (bcrypt-hashade lösenord)
├── pages/
│   ├── my_page.py         # Personlig startsida (KAM/säljchef)
│   ├── pipeline.py        # 6-stegs pipeline-kanban med drag & drop
│   ├── team_overview.py   # Säljchefs teamöversikt
│   ├── accounts.py        # Kundkonton med dashboard + kontakter + avtal
│   ├── timeline.py        # Avtalstidslinje (visuell)
│   ├── messages.py        # Intern chatt (st.chat_message)
│   ├── calendar_page.py   # Delad kalender (streamlit-calendar)
│   ├── notifications_page.py  # Notiscenter
│   ├── reports.py         # Rapportsida (säljchef)
│   └── integrations.py    # Integrationssida (säljchef)
├── scrapers/
│   ├── base.py, ted.py, mercell.py, kommers.py, eavrop.py
├── integrations/
│   ├── base.py            # BaseIntegration (ABC)
│   ├── notion_stub.py     # Notion-stubb
│   └── hubspot_stub.py    # HubSpot-stubb
└── upphandlingar.db       # SQLite-databas (WAL-mode)
```

## Databas (12 tabeller)
- `procurements` — upphandlingar (+ account_id FK)
- `analyses` — AI-analyser
- `labels` — feedback-etiketter (+ user_username)
- `users` — användare (kam/saljchef)
- `pipeline` — 6-stegs säljpipeline (bevakad→vunnen/förlorad)
- `procurement_notes` — anteckningar per upphandling
- `accounts` — kundkonton (Västtrafik etc)
- `contacts` — kontaktpersoner per konto
- `user_dashboard` — personlig konto-dashboard per användare
- `watch_list` — bevakningslistor (konto/nyckelord)
- `contract_timeline` — avtal med start/slut/option
- `messages` — intern kommunikation
- `calendar_events` — manuella kalenderhändelser
- `notifications` — notiser (in-app, e-post, Slack)
- `schema_version` — migreringsversion

## Kodkonventioner
- Svensk UI-text, engelska kodidentifierare
- Typhintar på funktionssignaturer
- Alla scrapers ärver `scrapers/base.py:BaseScraper`
- Databasåtkomst går genom `db.py` (aldrig rå SQL i andra filer)
- Scoringlogik finns i `scorer.py`
- AI-analys i `analyzer.py`
- Auth i `auth.py` — `check_auth()`, `get_current_user()`, `require_role()`
- Alla sidor i `pages/` tar `current_user: dict` som argument
- Roller: `kam` (KAM) och `saljchef` (säljchef med utökade rättigheter)
- Pipeline-steg: bevakad, kvalificerad, anbud_pagaende, inskickad, vunnen, forlorad
- Frontendtema: svart/orange/grått SaaS-stil, inga emojis, inga AI-ikoner

## Git
- Remote: https://github.com/DanielWarg/Upphandling
- Branch: main
- .gitignore exkluderar __pycache__, *.db, .env, venv, config/users.yaml
