# Upphandlingsbevakning

Svenskt verktyg för att bevaka offentliga upphandlingar och bidrag inom ledarskap, utbildning och organisationsutveckling. Byggt för HAST Utvecklings säljteam (3 KAM + 1 säljchef + 1 admin).

Scrapar sex källor, scorar leads med nyckelordsbaserad 2-stegs gate, kör AI-analys med lokal LLM (Ministral 3 14B), och hanterar säljpipeline + bidragspipeline.

## Funktioner

**Upphandlingar**
- **Automatisk skrapning** — TED, KommersAnnons, e-Avrop, Mercell med exponentiell backoff
- **2-stegs scoring** — Sektorgate + viktade nyckelord/CPV-koder (0–100 poäng)
- **AI-analys** — Prefilter + djupanalys med function calling (kravsammanfattning, matchning, prisstrategi, anbudshjälp)
- **Säljpipeline** — 6 steg: bevakad → kvalificerad → anbud pågår → inskickad → vunnen/förlorad

**Bidrag**
- **Bidragsbevakning** — Vinnova (API) och Tillväxtverket (RSS + Playwright-detaljer)
- **Bidragspipeline** — 6 steg: hittad → matchad → ansökan pågår → inskickad → beviljad/avslagen
- **Företagsregister** — Kundföretag med AI-profilering via webbplatsanalys
- **Automatisk matchning** — Nyckelordsscoring + AI-matchning av företag mot bidrag

**Gemensamt**
- **Fleranvändarstöd** — KAM, säljchef och admin-roller med bcrypt-auth
- **Kundkonton** — 33 seedade konton med auto-länkning via buyer-alias
- **Bevakningslistor** — Nyckelords- och kontobevakningar med notiser
- **AI-assistent** — Intern chatt med RAG-sökning mot upphandlingsdatabasen
- **Admin-dashboard** — Manuell skrapning, scoring, datarensning, systemstatus
- **Kalender & notiser** — Deadlines och teamsamarbete i dashboarden

## Installation

```bash
git clone https://github.com/DanielWarg/Upphandling.git
cd Upphandling
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Mercell kräver Playwright (valfritt)
playwright install chromium
```

## Användning

```bash
# Starta dashboard
streamlit run app.py

# Kör scraping + full pipeline
python3 run_scrapers.py

# Bara specifik källa
python3 run_scrapers.py --sources ted
python3 run_scrapers.py --sources vinnova,tillvaxtverket

# Omscora utan skrapning
python3 run_scrapers.py --score-only

# Hoppa över AI-djupanalys
python3 run_scrapers.py --skip-analysis
```

## AI-analys (valfritt)

Kräver lokal llama-server med Ministral 3 14B:

```bash
# Placera GGUF i ~/.cache/models/
# Starta server
llama-server \
  --model ~/.cache/models/Ministral-3-14B-Instruct-2512-Q4_K_M.gguf \
  --port 8081 --ctx-size 16384 --jinja

# Konfigurera endpoint
echo "LLM_BASE_URL=http://localhost:8081/v1" > .env
```

AI-analys används för:
- Prefilter (snabb relevanscheck) av upphandlingar och bidrag
- Djupanalys med function calling (kravsammanfattning, matchningsanalys, prisstrategi, anbuds-/ansökningshjälp)
- Företagsprofilering via webbplatsanalys
- Matchning av företag mot bidrag/utlysningar

## Inloggning

| Roll | Användare | Lösenord |
|------|-----------|----------|
| Admin | admin | admin |
| KAM | anna_lindberg | changeme123 |
| KAM | erik_svensson | changeme123 |
| KAM | maria_johansson | changeme123 |
| Säljchef | peter_nilsson | changeme123 |

## Tester

```bash
python3 -m pytest tests/ -v               # alla 309 tester
python3 -m pytest tests/test_scorer.py -v  # specifik fil
```

## Teknikstack

- **Frontend**: Streamlit (multi-page, svart/orange SaaS-tema)
- **Databas**: SQLite (WAL-mode, 17 tabeller, 14 index)
- **Skrapning**: httpx + BeautifulSoup + Playwright (Mercell/Vinnova/Tillväxtverket)
- **AI**: llama-server + Ministral 3 14B (function calling, JSON-mode)
- **Auth**: streamlit-authenticator (bcrypt, cookie-sessions)
- **Modeller**: Pydantic (TenderRecord med validering)

## Arkitektur

```
Scrapers (TED/KommersAnnons/e-Avrop/Mercell/Vinnova/Tillväxtverket)
  → list[TenderRecord]
  → db.upsert_procurement()
  → scorer.score_procurement()       (2-stegs gate → 0-100)
  → analyzer.ollama_prefilter_all()  (AI-relevanscheck)
  → analyzer.analyze_all_relevant()  (djupanalys med function calling)
  → db.ensure_pipeline_entry()       (score>0 + relevant → pipeline)
  → db.auto_link_procurements_to_accounts()
```

## Licens

Privat projekt — HAST Utveckling.
