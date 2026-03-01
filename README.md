# Upphandlingsbevakning

Svenskt verktyg for att bevaka offentliga upphandlingar inom ledarskap, utbildning och organisationsutveckling. Byggt for HAST Utvecklings saljteam.

Scrapar TED, KommersAnnons och e-Avrop, scorar leads med nyckelordsbaserad 2-stegs gate, kor AI-analys med lokal LLM (Ministral 3 14B), och hanterar en 6-stegs saljpipeline.

## Funktioner

- **Automatisk skrapning** — TED API, KommersAnnons, e-Avrop med exponentiell backoff
- **2-stegs scoring** — Sektor-gate + viktade nyckelord/CPV-koder (0-100 poang)
- **AI-analys** — Prefilter + djupanalys med function calling (kravsammanfattning, matchning, prisstrategi)
- **Saljpipeline** — 6 steg: bevakad, kvalificerad, anbud pagar, inskickad, vunnen, forlorad
- **Fleranvandarstod** — KAM, saljchef och admin-roller med bcrypt-auth
- **Kundkonton** — 33 seedade konton med auto-lankning via buyer-alias
- **Bevakningslistor** — Nyckelords- och kontobevakningar med notiser
- **Admin-dashboard** — Manuell skrapning, scoring, datarensning, systemstatus
- **Intern chatt, kalender, notiser** — Teamsamarbete i dashboarden

## Installation

```bash
git clone https://github.com/DanielWarg/Upphandling.git
cd Upphandling
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Anvandning

```bash
# Starta dashboard
streamlit run app.py

# Kor scraping + full pipeline
python3 run_scrapers.py

# Bara specifik kalla
python3 run_scrapers.py --sources ted

# Omscora utan skrapning
python3 run_scrapers.py --score-only

# Hoppa over AI-djupanalys
python3 run_scrapers.py --skip-analysis
```

## AI-analys (valfritt)

Kraver lokal llama-server med Ministral 3 14B:

```bash
# Ladda ner modell
# Placera GGUF i ~/.cache/models/Ministral-3-14B-Instruct-2512-Q4_K_M.gguf

# Starta server
llama-server \
  --model ~/.cache/models/Ministral-3-14B-Instruct-2512-Q4_K_M.gguf \
  --port 8081 --ctx-size 16384 --jinja

# Konfigurera endpoint
echo "LLM_BASE_URL=http://localhost:8081/v1" > .env
```

## Inloggning

| Roll | Anvandare | Losenord |
|------|-----------|----------|
| Admin | admin | admin |
| KAM | anna_lindberg | changeme123 |
| KAM | erik_svensson | changeme123 |
| KAM | maria_johansson | changeme123 |
| Saljchef | peter_nilsson | changeme123 |

## Tester

```bash
python3 -m pytest tests/ -v          # alla 71 tester
python3 -m pytest tests/test_scorer.py -v  # specifik fil
```

## Teknikstack

- **Frontend**: Streamlit (multi-page, dark SaaS-tema)
- **Databas**: SQLite (WAL-mode, 15 tabeller)
- **Skrapning**: httpx + BeautifulSoup
- **AI**: llama-server + Ministral 3 14B (function calling)
- **Auth**: streamlit-authenticator (bcrypt, cookie-sessions)
- **Modeller**: Pydantic (TenderRecord med validering)

## Licens

Privat projekt — HAST Utveckling.
