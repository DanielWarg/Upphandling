# Upphandlingsbevakning — Systemöversikt

> Dokument avsett som kontext för AI-assistenter som ska analysera och förbättra systemet.

## Vad systemet gör

Svenskt verktyg som bevakar offentliga upphandlingar relevanta för **Hogia Public Transport Systems** — en leverantör av IT-system för kollektivtrafik (realtid, trafikledning, reseplanering, beordring, anropsstyrd trafik).

Systemet scrapar upphandlingar från EU:s TED-databas, scorar dem efter relevans för Hogia, och presenterar dem i en Streamlit-dashboard med kanban-vy och AI-driven analys via Gemini 2.0 Flash.

---

## Teknikstack

| Komponent | Teknologi |
|-----------|-----------|
| Backend | Python 3.11+ |
| Frontend | Streamlit 1.54 |
| Databas | SQLite (WAL-mode) |
| API-klient | httpx |
| AI/LLM | Google Gemini 2.0 Flash via `google-genai` |
| Env | python-dotenv, `.env` för API-nycklar |

## Arkitektur

```
run_scrapers.py          CLI — kör scrapers + scoring
    |
    +-- scrapers/ted.py  TED API v3 (EU-upphandlingar)
    +-- scrapers/base.py Abstrakt basklass för scrapers
    |
    +-- scorer.py        Tvåstegs nyckelords-scoring
    +-- db.py            SQLite CRUD (procurements + analyses)
    |
app.py                   Streamlit dashboard (5 sidor)
    |
    +-- analyzer.py      Gemini 2.0 Flash AI-analys
```

---

## Datafönster

TED-scrapern hämtar svenska upphandlingar med CPV-koder:
- `60*` — Transport
- `48*` — Programvara
- `72*` — IT-tjänster

Tidsfönster: `publication-date > 2025-09-01` (senaste ~6 månader).

---

## Scoring-system (scorer.py)

### Trestegs-approach

**Steg 1 — Operations-detektor:**
Titlar som matchar mönster som "kollektivtrafik på väg", "busstrafik", "linjetrafik" etc. klassas som **trafikdrift** (att köra bussar) och får score 0. Dessa är irrelevanta för Hogia som säljer IT-system, inte kör bussar.

**Steg 2 — Transport-kontext:**
Upphandlingen MÅSTE ha transport/kollektivtrafik-kontext för att scora. En IT-upphandling för sjukvård eller utbildning är irrelevant oavsett om det är programvara. Transport-kontext identifieras via:
- Nyckelord: "kollektivtrafik", "biljett", "hållplats", "skolskjuts", "färdtjänst", "realtidsinformation", "GTFS", "NeTEx", "SIRI" etc.
- Känd köpare: Trafikbolag som Västtrafik, Skånetrafiken, Trafiknämnden etc.

**Steg 3 — IT-gate:**
Kräver minst en IT-/system-signal: "biljettsystem", "realtidssystem", "systemlösning", "programvara", "bokningssystem" etc. ELLER IT-CPV-kod (48*, 72*) kombinerat med transport-kontext.

### Poängvikter

| Kategori | Nyckelord (exempel) | Poäng |
|----------|---------------------|-------|
| Hög | realtidsinformation, trafikledningssystem, pubtrans, beordringssystem | 20-30 |
| Medel | passagerarinformation, netex, gtfs, biljettsystem, bokningssystem | 10-15 |
| Bas | kollektivtrafik, serviceresor, skolskjuts | 3-5 |
| Negativa | kontorsmaterial, medicinsk, tolkbokning, drivmedel | -10 till -20 |
| Känd köpare | Västtrafik, Skånetrafiken, Trafiknämnden etc. | +10 |
| IT-CPV | 48* (programvara), 72* (IT-tjänster) | +8 |

### Kända köpare (transport)

Skånetrafiken, Västtrafik, Trafiknämnden (Stockholm), Uppsalatrafik, Östgötatrafiken, Länstrafiken Kronoberg, Kalmar Länstrafik, Hallandstrafiken, Blekingetrafiken, Dalatrafik, X-trafik, Din Tur, Samtrafiken, Svealandstrafiken, Keolis, Nobina, Arriva m.fl.

### Aktuellt resultat

Med 526 hämtade upphandlingar ger scoringen ~9 relevanta träffar (score > 0). Resten filtreras bort som irrelevanta (trafikdrift, icke-transport-IT, eller helt orelaterat).

---

## AI-analys (analyzer.py)

### Modell
Gemini 2.0 Flash (1M context, ~0.01 USD/analys)

### Prompt-design

**System-prompt** definierar en senior upphandlingsrådgivare med expertis inom:
- LOU/LUF (lagen om offentlig upphandling / försörjningssektorn)
- Alla upphandlingsförfaranden (öppet, selektivt, förhandlat, etc.)
- Utvärderingsmodeller (bästa pris-kvalitetsförhållande, lägsta pris, etc.)
- ESPD, ramavtal, dynamiska inköpssystem
- SKI-ramavtal, Kammarkollegiets ramavtal

**User-prompt** innehåller:
- All metadata (titel, köpare, geografi, CPV, deadline, värde)
- Beskrivning från scraping
- Fulltext från TED XML (om tillgänglig, max 50k tecken)
- Detaljerad Hogia-kontext (produkter, standarder, referenskunder, styrkor, svagheter)

### Output-format (JSON)

```json
{
  "kravsammanfattning": "Markdown — scope, volym, tidsplan, ska-krav vs bör-krav",
  "matchningsanalys": "Markdown — produkt-för-produkt matchning, styrkor/svagheter, matchningsgrad",
  "prisstrategi": "Markdown — prismodell, nivå, kostnadsdrivare",
  "anbudshjalp": "Markdown — referenser, differentiering, risker, formalia"
}
```

### Hogia-kontext i prompten

**Produkter:**
- PubTrans — realtid och trafikledning, AVL, avvikelsehantering
- Realtidsinformation — hållplatsskyltar, appar, SIRI/GTFS-RT
- Reseplanerare — multimodal, NeTEx/GTFS, ResRobot-integration
- Beordringssystem — förarbemanning, tjänsteplanering, turlistor
- Anropsstyrd trafik — serviceresor, färdtjänst, sjukresor, skolskjuts

**Standarder:** NeTEx, SIRI, GTFS/GTFS-RT, ITxPT, BoB

**Referenskunder:** Västtrafik, Skånetrafiken, Svealandstrafiken, Länstrafiken Kronoberg, Region Uppsala, Hallandstrafiken

**Konkurrenter (nämns i prompt):** Hastus, Trapeze, IVU, Remix

### Caching

Analyser sparas i `analyses`-tabellen (SQLite) med procurement_id som UNIQUE. Återanvänds vid omladdning. Force-flagga kör om.

---

## Databas (db.py)

### Tabeller

**procurements** (18 kolumner):
```
id, source, source_id, title, buyer, geography, cpv_codes,
procedure_type, published_date, deadline, estimated_value, currency,
status, url, description, score, score_rationale, created_at, updated_at
UNIQUE(source, source_id)
```

**analyses** (11 kolumner):
```
id, procurement_id (UNIQUE FK), full_notice_text,
kravsammanfattning, matchningsanalys, prisstrategi, anbudshjalp,
model, input_tokens, output_tokens, created_at
```

### API-funktioner

- `init_db()` — skapar tabeller
- `upsert_procurement(data)` — insert eller update (dedup via source+source_id)
- `update_score(id, score, rationale)`
- `get_all_procurements()` — sorterat score DESC
- `search_procurements(query, source, min_score, max_score, geography)`
- `get_stats()` — total, avg_score, high_fit, new_today, by_source
- `save_analysis(procurement_id, analysis)` — upsert
- `get_analysis(procurement_id)` — cachad analys

---

## Dashboard (app.py)

### Tema
Svart/orange/grått SaaS-stil. Inter-font. Inga emojis, inga AI-ikoner.

### 5 sidor

1. **Kanban** — Tre kolumner: Hög prioritet (score >= 60), Medel (30-59), Låg (< 30). Klickbara kort med modal. Snabbanalys-rad under kanban med dropdown + "Analysera med AI"-knapp.

2. **Sök & Filter** — Fritextsök, källa, region, score-range. Resultat i dataframe.

3. **AI Analys** — Välj upphandling ur dropdown (sorterad score desc). Grundinfo-panel. "Analysera med AI"-knapp. 4 expanderbara sektioner (kravsammanfattning, matchningsanalys, prisstrategi, anbudshjälp). Metadata-footer (modell, tokens, datum). Stödjer `?ai_id=X` query param.

4. **Detaljvy** — Fullständig info om en upphandling via ID-input.

5. **Inställningar** — Visar scoring-vikter och kända köpare.

### Kanban-implementation
Renderas som en `components.html()` iframe med fullständig HTML/CSS/JS. Varje kort bär `data-proc` JSON-attribut. Klick öppnar modal med detaljer.

---

## TED-scraper (scrapers/ted.py)

- API: `https://api.ted.europa.eu/v3/notices/search` (POST, ingen auth)
- 3 parallella sökfrågor (CPV 60*, 48*, 72*)
- Paginering: 50/sida, max 4 sidor per query
- Rate limiting: 0.5s delay, retry vid 429
- Normalisering: flerspråkiga fält (föredrar svenska), geografi från titel, deadline-hantering

### Fulltext-hämtning (för AI-analys)
`https://ted.europa.eu/en/notice/{pub_number}/xml` — parser eForms XML till ren text.

---

## Kända problem och förbättringsområden

### Scoring
- Bara 9 av 526 upphandlingar scorar > 0. Korrekt beteende (få är relevanta), men känsligt för nyckelordsmatchning. En upphandling som beskriver "trafikledning" i betydelsen "utföra trafikledning" (köra bussar) vs "trafikledningsSYSTEM" (IT) är svår att skilja automatiskt.
- Nyckelorden är statiska — ingen inlärning från användarfeedback.
- Scoring-vikterna är handtunade, inte optimerade.

### Datakällor
- Bara TED är implementerad. Mercell, KommersAnnons och e-Avrop har stub-scrapers men inget fetchande. Dessa är viktiga svenska källor som TED inte täcker (nationella upphandlingar under EU-tröskelvärdet).
- TED hämtar breda CPV-koder (all programvara, alla IT-tjänster) — de flesta är irrelevanta. Smalare CPV-filter eller bättre pre-filtrering kunde spara API-anrop.

### AI-analys
- Prompten är lång och detaljerad men inte testad mot verkliga upphandlingsdokument i stor skala.
- Ingen strukturerad validering av Geminis JSON-output.
- Fulltext från TED XML-parsning är rå (alla element, ingen filtrering) — kan innehålla mycket brus.
- Inget stöd för att ladda upp egna upphandlingsdokument (PDF).

### Dashboard
- Kanban-boardet renderas i en iframe (`components.html`) som inte kan kommunicera tillbaka med Streamlit. AI-knappen i modalen fungerar inte pga sandbox. Workaround: snabbanalys-rad under kanban.
- Ingen användarautentisering.
- Sidebar tvingas synlig med CSS-hack (`position: relative, min-width: 260px`) pga Streamlit-bugg.
- Inga notifikationer vid nya relevanta upphandlingar.
- Ingen export-funktion (PDF, Excel).

### Infrastruktur
- SQLite — fungerar för MVP men skalar inte vid flera användare.
- Ingen schemalagd körning (cron/scheduler) — manuell `run_scrapers.py`.
- Inga loggfiler — bara print-statements.
- Tester finns (24 st, alla gröna) men ingen CI/CD.

---

## Filstruktur

```
Upphandling/
├── app.py                 # Streamlit dashboard (5 sidor, ~800 rader)
├── analyzer.py            # Gemini AI-analys
├── db.py                  # SQLite schema + CRUD
├── scorer.py              # Tvåstegs lead scoring
├── run_scrapers.py        # CLI entry point
├── scrapers/
│   ├── __init__.py
│   ├── base.py            # BaseScraper ABC
│   ├── ted.py             # TED API v3
│   ├── mercell.py         # Stub
│   ├── kommers.py         # Stub
│   └── eavrop.py          # Stub
├── test_e2e.py            # 24 tester (pytest)
├── requirements.txt
├── .env                   # GEMINI_API_KEY (gitignored)
├── .env.example
├── .gitignore
├── CLAUDE.md              # AI-assistentinstruktioner
├── SYSTEM_OVERVIEW.md     # Detta dokument
└── upphandlingar.db       # SQLite databas (gitignored)
```

---

## Kommandon

```bash
# Hämta data + scora
python3 run_scrapers.py

# Bara TED
python3 run_scrapers.py --sources ted

# Omscora utan skrapning
python3 run_scrapers.py --score-only

# Starta dashboard
streamlit run app.py

# Kör tester
python3 -m pytest test_e2e.py -v
```

---

## Beroenden

```
streamlit>=1.30.0
httpx>=0.27.0
scrapling>=0.2
pandas>=2.1.0
google-genai>=1.0.0
python-dotenv>=1.0.0
```
