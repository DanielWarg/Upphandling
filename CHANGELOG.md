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

- **TED** (`scrapers/ted.py`): dynamisk datumcutoff (6 månader tillbaka istället för hardkodat)
- **KommersAnnons** (`scrapers/kommers.py`):
  - Borttaget klient-side nyckelordsfilter — serverns sökfilter hanterar relevans
  - Ny `_fetch_buyer()` — hämtar köpare från detaljsida
  - MAX_PAGES ökad från 3 till 5
- **e-Avrop** (`scrapers/eavrop.py`):
  - Borttaget klient-side filter — scorer hanterar relevans
  - Ny `_fetch_detail()` — hämtar beskrivning och geografi från detaljsida
  - MAX_PAGES ökad från 4 till 6
- **Mercell**: exkluderad från ALL_SCRAPERS (kräver auth, TED täcker samma EU-upphandlingar)

### Buggfixar

- Fixat säkerhetsbug i admin-autentisering (lösenord valideras korrekt)
- Fixat `__import__("datetime")` hack — använder proper import av `timedelta`
- Sista "Hogia"-referensen i `seed_accounts()` uppdaterad till HAST Utveckling

### Tester

- Borttagna `TestKommersRelevanceFilter` och `TestEAvropRelevanceFilter` (klient-filter borttagna)
- Nya `TestKommersNoClientFilter` och `TestEAvropNoClientFilter`
- 71 tester passerar

### Databasstatistik

- 416 upphandlingar (196 kommers, 116 TED, 104 e-Avrop)
- 35 AI-analyser genomförda
- 35 pipeline-poster (alla i bevakad-steget)
- 16 konton seedade, 88 bevakningar aktiva
- Fältkomplettering: title 100%, buyer 81%, deadline 82%, description 69%, estimated_value 28%
