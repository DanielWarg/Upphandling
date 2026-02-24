# Upphandlingsbevakning MVP - Veckoplan

## Kontext
Hogia behover ett verktyg for att bevaka svenska kollektivtrafikupphandlingar och scora leads. Vi bygger en MVP pa en vecka med Python + Streamlit + SQLite + Scrapling.

## Arkitektur

```
[TED API] -----> |                  |
[Mercell]  ----> | Scrapling/HTTP   | --> [Normalizer] --> [SQLite] --> [Streamlit Dashboard]
[e-Avrop]  ----> | Source Adapters  |                         |
[KommersAnnons]->|                  |                    [Lead Scorer]
```

## Projektstruktur

```
upphandling/
  app.py                  # Streamlit dashboard (huvudentry)
  db.py                   # SQLite schema + CRUD
  scorer.py               # Keyword-baserad lead scoring
  scrapers/
    __init__.py
    base.py               # BaseScraper med gemensamt interface
    ted.py                # TED API (REST, gratis, ingen auth)
    mercell.py            # Mercell web scraping via Scrapling
    eavrop.py             # e-Avrop web scraping via Scrapling
    kommers.py            # KommersAnnons web scraping via Scrapling
  run_scrapers.py         # CLI-script: kor alla scrapers + scoring
  requirements.txt
```

## Datakallor (prioritetsordning)

### 1. TED API (Dag 1)
- **Endpoint:** `POST https://api.ted.europa.eu/v3/notices/search`
- **Gratis, ingen auth for publicerade notices**
- **Filter:** country=SWE, CPV-koder 60xxxxxx (transport)
- Implementera med vanlig `httpx` (behover inte Scrapling)

### 2. Mercell Annonsdatabas (Dag 2)
- **URL:** `https://app.mercell.com/search?filter=delivery_place_code:SE`
- **Scrapling StealthyFetcher** (kan ha bot-skydd)
- Parsa listsidor, extrahera metadata per annons

### 3. KommersAnnons (Dag 2-3)
- **URL:** `https://www.kommersannons.se/elite/notice/noticelist.aspx`
- **Scrapling Fetcher** (enklare sida)
- Parsa listsida, filtrera pa kollektivtrafik-CPV

### 4. e-Avrop (Dag 3)
- **URL:** e-avrop.com sokfunktion
- **Scrapling StealthyFetcher**
- Parsa listsidor

## Databasschema (SQLite)

```sql
CREATE TABLE procurements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,              -- ted/mercell/kommers/eavrop
  source_id TEXT NOT NULL,
  title TEXT NOT NULL,
  buyer TEXT,
  geography TEXT,
  cpv_codes TEXT,                    -- komma-separerade
  procedure_type TEXT,
  published_date TEXT,
  deadline TEXT,
  estimated_value REAL,
  currency TEXT,
  status TEXT,
  url TEXT,
  description TEXT,
  score INTEGER DEFAULT 0,          -- 0-100 lead score
  score_rationale TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(source, source_id)
);
```

## Lead Scoring (Dag 4)

Keyword-baserad scoring med viktade termer:

**Hog vikt (20p vardera):**
- realtid, realtidsinformation, realtidssystem
- trafikledning, trafikledningssystem
- dataplattform, informationsplattform

**Medel vikt (10p vardera):**
- bestallningscentral, samordningscentral
- passagerarinformation, resenarsinformation
- NeTEx, SIRI, GTFS
- ITxPT

**Bas vikt (5p vardera):**
- kollektivtrafik, busstrafik, tagtrafik
- serviceresor, fardtjanst, sjukresor, skolskjuts

**Buyer bonus (10p):**
- Om koparen ar en kand region/RKM fran rapporten

Max score: 100 (cappat)

## Streamlit Dashboard (Dag 4-5)

### Sidor:
1. **Dashboard** - Nya upphandlingar, topp-scores, snart deadline
2. **Sok & Filter** - Fritext, CPV, region, score-range, kallsystem
3. **Detaljvy** - All metadata, score-breakdown, lank till kalla
4. **Installningar** - Konfigura scoring-vikter

### Komponenter:
- `st.dataframe` for listor med sortering/filtrering
- `st.metric` for KPI:er (nya idag, snitt-score, antal hog-fit)
- `st.bar_chart` for score-fordelning
- Color-coding: Rod (hog score), Gul (medel), Gra (lag)

## Dagplan

| Dag | Fokus |
|-----|-------|
| 1 | Projektsetup, SQLite-schema, TED API-scraper |
| 2 | Mercell + KommersAnnons scrapers med Scrapling |
| 3 | e-Avrop scraper, normalizer, dedup-logik |
| 4 | Lead scorer, Streamlit dashboard (grund) |
| 5 | Dashboard polish, filter/sok, detaljvy |
| 6 | Testning, edge cases, felhantering |
| 7 | Dokumentation, deploy-instruktioner, demo |

## Verifiering

1. Kor `python run_scrapers.py` - ska hamta upphandlingar fran alla kallor
2. Kor `streamlit run app.py` - dashboard ska visa data med scores
3. Verifiera att TED-data matchar manuell sokning pa ted.europa.eu
4. Verifiera att scoring rankar trafiklednings-upphandlingar hogst
5. Testa dedup: kora scrapers 2 ganger, ska inte skapa dubletter
