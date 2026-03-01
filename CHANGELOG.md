# Changelog

## Fas 3 — Admin, datarensning & scraperförbättringar (2026-02-28)

### Ny funktionalitet

- **Admin-sida** (`pages/admin.py`): 5-flikars administrationsgränssnitt
  - Datahämtning: manuell skrapning per källa + full pipeline-körning med 10 steg
  - Scoring & Analys: scora alla, AI-prefilter, djupanalys — med progress-visning
  - Datarensning: arkivera utgångna, rensa gamla expired (>180 dagar), cross-source dedup
  - Användare & Bevakningar: synka YAML-användare, skapa default-bevakningar, kalenderevents
  - Systemstatus: 12 KPI-metrics, per-källa-breakdown, datakvalitet-fältifyllnad

- **Admin-autentisering** (`auth.py`): admin-användare injiceras i authenticator vid runtime
  - Säker bcrypt-hashning av admin-lösenord
  - Enhetlig inloggningsflow — ingen separat admin-form
  - Admin-roll med villkorad sidvisning i navigationen

- **6 nya databasfunktioner** (`db.py`):
  - `archive_expired_procurements()` — markera utgångna upphandlingar
  - `purge_old_expired(days=180)` — radera gamla expired-poster
  - `cross_source_deduplicate()` — fuzzy dedup mellan källor (titel+köpare)
  - `sync_users_from_yaml()` — synka users-tabell från YAML-config
  - `seed_default_watches(username)` — skapa nyckelords- och kontobevakningar
  - `create_deadline_calendar_events()` — auto-skapa kalenderevents för deadlines

- **CLI-förbättringar** (`run_scrapers.py`):
  - `scrape_sources()` exponerad som callable med `on_progress`-callback
  - Alla pipeline-funktioner exponerade individuellt (dedup, score, prefilter, etc.)
  - Full pipeline med cross-source dedup, arkivering och kalenderevents

### Scraperförbättringar

- **TED**: dynamisk datumcutoff (6 månader tillbaka istället för hårdkodat)
- **KommersAnnons**: borttaget klient-side filter, ny `_fetch_buyer()` från detaljsida, MAX_PAGES 3→5
- **e-Avrop**: borttaget klient-side filter, ny `_fetch_detail()` (beskrivning+geografi), MAX_PAGES 4→6
- **Mercell**: exkluderad (kräver auth, TED täcker samma EU-upphandlingar)

### Buggfixar

- Fixat säkerhetsbug i admin-autentisering (lösenord validerades inte)
- Fixat `__import__("datetime")` hack — proper import av `timedelta`
- Sista "Hogia"-referensen uppdaterad till HAST Utveckling

---

## Fas 2 — Säljstöd & AI-standardisering (2026-02-26 – 2026-02-28)

### Ny funktionalitet

- **Flerannvändarstöd**: roller (KAM/säljchef), YAML-baserad auth med bcrypt + cookie-sessions
- **6-stegs säljpipeline**: bevakad → kvalificerad → anbud pågår → inskickad → vunnen/förlorad
- **Kundkonton**: 16 seedade konton med buyer-alias-matching, auto-länkning av upphandlingar
- **Bevakningslistor**: nyckelords- och kontobevakningar med notiser vid matchning
- **Intern chatt**: `st.chat_message`-baserad kommunikation mellan teammedlemmar
- **Delad kalender**: FullCalendar.js-integration via streamlit-calendar
- **Notiscenter**: in-app, e-post och Slack-notiser
- **Pydantic-modeller** (`models.py`): `TenderRecord` med computed `hash_fingerprint` och `to_db_dict()`
- **Score breakdown**: detaljerad poängredovisning med nyckelords- och CPV-matchning
- **Backoff-modul** (`scrapers/backoff.py`): `with_backoff()` för retry vid 429/5xx

### AI-standardisering

- Standardiserat på **Ministral 3 14B** som enda LLM (bort med Gemini, Qwen, Llama)
- **llama-server** som inference-backend (inte Ollama)
- Function calling med strukturerad JSON-output (kravsammanfattning, matchning, prisstrategi)
- All kontext uppdaterad från Hogia till HAST Utveckling

### Tester

- 71 tester: TED-normalisering, scorer (sector gate + scoring + breakdown), Pydantic-modeller, scraper-parsing

---

## Fas 1 — MVP & grundfunktionalitet (2026-02-24 – 2026-02-26)

### Ny funktionalitet

- **TED API-scraper**: v3 sök-API med CPV-koder och fulltextsökning för svenska upphandlingar
- **KommersAnnons-scraper**: httpx + BeautifulSoup, server-side sökfilter
- **e-Avrop-scraper**: ASP.NET WebForms med ViewState-paginering
- **Mercell-scraper** (stubb): kräver autentisering, exkluderad i Fas 3
- **Nyckelordsscoring** (`scorer.py`): 2-stegs gate (sektorfilter + utbildningscheck) + poängsättning
- **AI-analys** (`analyzer.py`): lokal AI-prefilter + djupanalys via llama-server
- **Streamlit-dashboard**: dark SaaS-tema (svart/orange/grått), kanban-vy, sök och filter
- **SQLite-databas**: WAL-mode, 15 tabeller, full CRUD via `db.py`
- **Deduplicering**: inom källa (source+source_id), cross-source (fuzzy titel+köpare)

### UI

- Svensk UI-text, engelska kodidentifierare
- Responsiv kanban med drag & drop (streamlit-sortables)
- Filtrering: score, källa, AI-relevans, datum
- Datumvisning och deadline-countdown

### Infrastruktur

- CI-pipeline med lint
- `.env`-konfiguration för LLM-endpoint
- `run_scrapers.py` CLI med flaggor: `--sources`, `--score-only`, `--skip-analysis`
