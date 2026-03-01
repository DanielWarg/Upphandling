# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projekt

Svenskt verktyg för att bevaka upphandlingar inom ledarskap, utbildning och organisationsutveckling åt HAST Utveckling. Scrapar TED, KommersAnnons och e-Avrop, scorar leads med nyckelordsbaserad 2-stegs gate, kör AI-analys med Ministral 3 14B, och hanterar en 6-stegs säljpipeline för HAST:s säljteam (3 KAM + 1 säljchef + 1 admin).

## Kommandon

```bash
# Dashboard
streamlit run app.py

# Scraping + full pipeline
python3 run_scrapers.py                    # alla källor
python3 run_scrapers.py --sources ted      # bara TED
python3 run_scrapers.py --score-only       # omscora utan skrapning
python3 run_scrapers.py --skip-analysis    # hoppa över AI-djupanalys

# Tester
python3 -m pytest tests/ -v                                          # alla (71 st)
python3 -m pytest tests/test_scorer.py -v                            # en fil
python3 -m pytest tests/test_scorer.py::TestScoring::test_high_relevance_scores_high -v  # ett test

# Databas
python3 migrate.py --status                # visa schemaversion

# AI-server (krävs för analys)
llama-server --model ~/.cache/models/Ministral-3-14B-Instruct-2512-Q4_K_M.gguf --port 8081 --ctx-size 16384 --jinja
```

## Arkitektur — Dataflöde

```
Scrapers (ted/kommers/eavrop)
    → list[TenderRecord]  (Pydantic, models.py)
    → db.upsert_procurement()  (SQLite, UNIQUE(source, source_id))
    → scorer.score_procurement()  (2-stegs gate + viktade nyckelord → 0-100)
    → analyzer.ollama_prefilter_all()  (snabb AI-relevanscheck)
    → analyzer.analyze_all_relevant()  (djupanalys med function calling)
    → db.ensure_pipeline_entry()  (score>0 + ai_relevance=relevant → pipeline)
    → db.auto_link_procurements_to_accounts()  (buyer-alias-matchning)
```

## Nyckelarkitektur

**Auth** (`auth.py`): Admin-användare injiceras i streamlit-authenticator config vid runtime med plaintext-lösenord (`auto_hash=True` hashar). Authenticator cachas i `session_state["_authenticator"]`. Roller: `admin`, `kam`, `saljchef`.

**Sidor** (`pages/*.py`): Varje sida exporterar en `render_X()` funktion utan parametrar — hämtar `current_user` från `st.session_state`. Admin-sidan visas villkorligt i `app.py` baserat på roll.

**Scrapers** (`scrapers/*.py`): Alla ärver `BaseScraper(ABC)` med `fetch() → list[TenderRecord]`. Registrerade i `ALL_SCRAPERS` i `__init__.py`. Använder `with_backoff()` för exponentiell retry vid 429/5xx.

**Scoring** (`scorer.py`): Returnerar 3-tupel `(score, rationale, breakdown)`. Steg 1: sector gate (blockerar irrelevanta sektorer, kräver utbildningssignal). Steg 2: viktad nyckelordspoäng + buyer-bonus + CPV-bonus, max 100.

**AI-analys** (`analyzer.py`): Tvåfas — prefilter (snabb relevans) + djupanalys (function calling → kravsammanfattning, matchningsanalys, prisstrategi, anbudshjälp). ENDA modell: Ministral 3 14B via llama-server (`LLM_BASE_URL` i `.env`). Använd ALDRIG andra modeller.

**Databas** (`db.py`): ALL databasåtkomst går genom denna fil — aldrig rå SQL i andra filer. `upsert_procurement()` accepterar både `dict` och `TenderRecord`. WAL-mode, 15 tabeller, 14 index.

## Kodkonventioner

- Svensk UI-text, engelska kodidentifierare
- Typhintar på funktionssignaturer
- `on_progress: Callable[[str], None]` callback-mönster för att streama status till Streamlit UI
- Pipeline-steg: `bevakad`, `kvalificerad`, `anbud_pagaende`, `inskickad`, `vunnen`, `forlorad`
- Frontend: svart/orange/grått SaaS-tema, inga emojis, inga AI-ikoner
- Tester använder `tmp_db` fixture (monkeypatch `DB_PATH` → isolerad temp-databas per test)

## Inloggning

- Admin: `admin` / `admin` (hårdkodad i auth.py)
- KAM: `anna_lindberg`, `erik_svensson`, `maria_johansson` (lösenord: `changeme123`)
- Säljchef: `peter_nilsson` (lösenord: `changeme123`)

## Git

- Remote: https://github.com/DanielWarg/Upphandling
- Branch: main
- `.gitignore` exkluderar: `__pycache__`, `*.db`, `.env`, `venv/`, `config/users.yaml`
