# Deployment Guide — Upphandlingsbevakning Fas2

## Systemkrav

- Python 3.11+
- 4 GB RAM (8 GB rekommenderat med LLM)
- llama-server (för AI-analys, valfritt)

## Installation

```bash
# Klona och installera
git clone https://github.com/DanielWarg/Upphandling.git
cd Upphandling
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Konfigurera
cp .env.example .env
# Redigera .env med dina API-nycklar

cp config/users.yaml.example config/users.yaml
# Redigera users.yaml med dina användare och lösenord
```

## Användarkonfiguration

### Skapa bcrypt-hashade lösenord

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'DITT_LOSENORD', bcrypt.gensalt()).decode())"
```

### config/users.yaml

```yaml
credentials:
  usernames:
    fornamn_efternamn:
      email: user@example.com
      name: Förnamn Efternamn
      password: "$2b$12$BCRYPT_HASH"
      role: kam  # eller saljchef
cookie:
  expiry_days: 30
  key: EN_SLUMPMASSIG_NYCKEL
  name: upphandling_auth
```

Roller:
- `kam` — Key Account Manager, ser sina egna deals och upphandlingar
- `saljchef` — Säljchef, ser hela teamets pipeline, rapporter, integrationer

## Databasmigrering

### Ny installation

Databasen skapas automatiskt vid första körning.

### Uppgradering från Fas1

```bash
python3 migrate.py           # Applicera alla migreringar
python3 migrate.py --status  # Kontrollera version
```

Migreringen:
1. Skapar alla nya tabeller (pipeline, accounts, messages, etc.)
2. Seedar konton (Västtrafik, Skånetrafiken, etc.)
3. Migrerar relevanta upphandlingar till pipeline
4. Länkar upphandlingar till konton
5. Seedar användare från users.yaml

## Starta dashboard

```bash
streamlit run app.py
```

Dashboard nås på `http://localhost:8501`.

## Scraping

```bash
# Fullständig körning (scraping + scoring + AI + pipeline)
python3 run_scrapers.py

# Bara specifika källor
python3 run_scrapers.py --sources ted mercell

# Omscora utan ny scraping
python3 run_scrapers.py --score-only

# Hoppa över djupanalys
python3 run_scrapers.py --skip-analysis
```

## AI-analys (valfritt)

```bash
# Starta llama-server
llama-server \
  --model ~/.cache/models/Ministral-3-14B-Instruct-2512-Q4_K_M.gguf \
  --port 8081 \
  --ctx-size 16384 \
  --jinja
```

Konfigurera i `.env`:
```
LLM_BASE_URL=http://localhost:8081/v1
```

## Notiser (cron)

Kör var 15:e minut:
```bash
crontab -e
# Lägg till:
*/15 * * * * cd /path/to/Upphandling && /path/to/venv/bin/python3 notify.py
```

Kräver SMTP-konfiguration i `.env` för e-post.

## Veckorapporter

```bash
python3 reports.py                    # Aktuell vecka
python3 reports.py --week 2026-W09    # Specifik vecka
python3 reports.py --email            # Skicka via e-post
```

## Filstruktur

```
├── app.py                 # Streamlit dashboard (huvudapp)
├── auth.py                # Autentisering (streamlit-authenticator)
├── db.py                  # SQLite schema + CRUD
├── scorer.py              # Nyckelordsscoring
├── analyzer.py            # AI-analys (Ollama/Gemini)
├── predictions.py         # Historisk mönsteranalys
├── reports.py             # Veckorapport-generering
├── notify.py              # E-post/Slack-notiser (cron)
├── migrate.py             # Databasmigrering
├── run_scrapers.py        # CLI-orchestrator
├── config/
│   └── users.yaml         # Användarkonfiguration (bcrypt)
├── pages/
│   ├── my_page.py         # Personlig startsida
│   ├── pipeline.py        # Drag & drop pipeline
│   ├── team_overview.py   # Säljchefs teamvy
│   ├── accounts.py        # Kundkonton
│   ├── timeline.py        # Avtalstidslinje
│   ├── messages.py        # Intern chatt
│   ├── calendar_page.py   # Delad kalender
│   ├── notifications_page.py  # Notiscenter
│   ├── reports.py         # Rapportsida
│   └── integrations.py    # Integrationssida
├── scrapers/
│   ├── base.py            # BaseScraper
│   ├── ted.py             # TED API
│   ├── mercell.py         # Mercell
│   ├── kommers.py         # KommersAnnons
│   └── eavrop.py          # E-Avrop
├── integrations/
│   ├── base.py            # BaseIntegration (ABC)
│   ├── notion_stub.py     # Notion-stubb
│   └── hubspot_stub.py    # HubSpot-stubb
└── upphandlingar.db       # SQLite-databas (WAL-mode)
```

## Felsökning

**Login fungerar inte**
- Kontrollera att `config/users.yaml` finns och har rätt format
- Verifiera lösenordshash: `python3 -c "import bcrypt; print(bcrypt.checkpw(b'password', b'$2b$12$...'))""`

**Databasen är låst**
- SQLite WAL-mode hanterar 4 samtidiga användare bra
- Om problem: `sqlite3 upphandlingar.db 'PRAGMA wal_checkpoint(TRUNCATE)'`

**Notiser skickas inte**
- Kontrollera SMTP-konfiguration i `.env`
- Testa manuellt: `python3 notify.py`
- Kontrollera att användare har e-post i `users`-tabellen
