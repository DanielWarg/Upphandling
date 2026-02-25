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

## Kommande features (v2)

### Historisk analys av avslutade upphandlingar
- Scrapa avslutade/tilldelade upphandlingar från TED (resultat-notices)
- Lagra vinnare, tilldelat värde, antal anbud
- Analysvy: Varför vann vinnaren? Pris vs kvalitet? Tidigare erfarenhet?
- Mönsterigenkänning: Vilka leverantörer vinner i vilka regioner/segment?
- Insikter inför kommande liknande upphandlingar

### AI-drivet upphandlingsstöd
- **Kravanalys:** AI läser kravställningen och sammanfattar nyckelkrav
- **Matchningsanalys:** Hur matchar Hogias produkter mot kraven? Gap-analys
- **Prisstrategi:** AI-stöd för prissättning baserat på historiska tilldelningar
- **Anbudshjälp:** Förslag på win themes, differentiering, compliance-checklista
- LLM-integration (Claude API) för analys av upphandlingsdokument

### Djuplänkar och referensinformation
- Klickbara länkar direkt till TED/Mercell/KommersAnnons-originalet
- PDF-nedladdning av upphandlingsdokument där tillgängligt
- Koppling till leverantörsregister och tidigare tilldelningar
- Tidslinje per upphandling: publicerad → Q&A → deadline → tilldelning

## Verifiering

1. Kor `python run_scrapers.py` - ska hamta upphandlingar fran alla kallor
2. Kor `streamlit run app.py` - dashboard ska visa data med scores
3. Verifiera att TED-data matchar manuell sokning pa ted.europa.eu
4. Verifiera att scoring rankar trafiklednings-upphandlingar hogst
5. Testa dedup: kora scrapers 2 ganger, ska inte skapa dubletter


Ja — för att få den här till toppnivå handlar det om två saker:

Coverage (att ni inte missar relevanta upphandlingar)

Precision (att rätt saker hamnar högt och fel saker sjunker direkt)

I dag har ni bra “MVP-precision” med keywords + gates, men ni saknar två proffsbitar: produkt-till-krav-matchning och inlärning från feedback.

1) Ja: definiera “produkter” som maskinläsbara objekt (annars blir matchning fluff)

Ni behöver inte “produktblad”, men ni behöver en produktkatalog i JSON som systemet kan räkna på.

Gör så här (minsta version som ger stor effekt):

Skapa products som en lista där varje produkt har:

name

synonyms (ord upphandlingar faktiskt använder)

standards (NeTEx, SIRI, GTFS-RT, ITxPT…)

capabilities (t.ex. AVL, realtidsutrop, DRT/serviceresor, planering, dispatch)

negative_signals (ord som betyder “trafikdrift”, “operatör”, “bussar körs”, “fordonsleverans” osv)

must_have_signals (minst 1–2 signaler som måste finnas för att produkten ens ska vara kandidat)

Sedan gör ni matchning som ett extra lager:

system_relevance_score (er nuvarande)

product_fit[] (per produkt: 0–100 + “why” + hittade evidensrader)

overall_fit = max eller viktad summa

Det här gör två saker:

Ni kan säga “Den här upphandlingen passar Anropsstyrd trafik 82/100 men PubTrans 25/100”.

Sälj får en faktisk “vart ska vi trycka?”-indikator, inte bara “relevant/inte relevant”.

2) Nej: ni behöver inte scrapa “mer” först — ni behöver scrapa “smartare”

Att bara lägga till Mercell/Kommers/e-Avrop är viktigt för coverage, men om ni gör det innan ni har bättre ranking får ni bara mer brus.

Rätt ordning för toppnivå:

Förbättra ranking/klassning + feedback-loop på TED-data (billig träningsyta)

Lägg till fler källor när ni kan hålla precisionen

3) Byt ut keyword-score till “hybrid”: regler + liten klassificerare

Behåll era gates (de är guld), men lägg till en klassificerare som löser era svåraste fall:

“trafikledning” som verksamhet (drift) vs “trafikledningssystem” (IT)

“uppföljningssystem”, “plattform”, “stöd” där keywords missar

“bussoperatör upphandlar IT under drift” (kan vara relevant ändå)

Minimal proffslösning:

Labela 200–400 notices: irrelevant, maybe, relevant

Träna en enkel modell på textfeatures (titel + beskrivning + buyer + CPV + utdrag ur fulltext)

Output: p(relevant) som multiplicerar/justerar er rules-score

Ni får då:

Färre falska positiva

Färre missar som “låter rätt men saknar exact keyword”

4) Gör feedback till en första-klass-feature (annars blir det aldrig bättre)

I UI: varje kort ska ha två knappar:

Relevant ✅ / Inte relevant ❌

(valfritt) “Fel anledning” dropdown: drift / fel bransch / fel IT / annat

Spara till tabell labels:

procurement_id, label, reason, user, timestamp

Och använd den datan till:

justera vikter

förbättra buyer-lista

träna klassificeraren

Det här är den största skillnaden mellan “coolt demo” och “system som blir bättre varje vecka”.

5) AI-analysen: gör den verifierbar och mer “säljbar”

Ni har rätt JSON-struktur, men två saker saknas:

A) Strikt JSON-validering + auto-retry

Validera JSON mot schema

Om fel: re-prompt med “returnera endast korrekt JSON”

Logga “failed parses” så ni ser när prompten drifter

B) “Evidence-first”

Kräv att modellen alltid ger:

evidence_quotes[]: 3–8 korta textsnuttar (max ~200 tecken) + var de hittades (titel/beskrivning/fulltext)
Det gör analysen trovärdig internt.

6) Fulltext: rena bort brus innan LLM

TED XML-text är ofta “soppa”. Ni vill extrahera sektioner:

scope/description

krav/shall

standards/data formats

integration/API

SLA/support

security/GDPR

timeline & option years

Bara detta kan halvera tokens och dubbla kvalitet.

7) När ni väl går multi-source: dedup + “tender identity”

Samma upphandling kan dyka upp på flera ställen (TED + nationell portal). Ni behöver:

tender_fingerprint = hash(title normalized + buyer normalized + deadline + cpv major)

dedup på fingerprint (inte bara source_id)

Min rekommenderade “topnivå”-ordning (utan att bygga om allt)

Steg 1 (snabb effekt): produktkatalog + per-produkt matchning + feedbackknappar
Steg 2: hybrid-ranker (regelsystem + liten klassificerare)
Steg 3: bättre fulltext-extraktion + evidence-first AI
Steg 4: fler källor + dedup + notifieringar

Två konkreta uppgifter (så ni faktiskt kommer framåt)

Uppgift 1: Skapa products.json med 5 produkter (era), inklusive synonyms, must_have_signals, negative_signals, standards, capabilities.
Uppgift 2: Lägg till UI-feedback (✅/❌) + tabell labels + enkel vy “Lärdomar” (top 20 ord som korrelerar med ❌ vs ✅).

PROMPT (klistra in i ert byggflöde)

Bygg en “Top Level”-uppgradering av vårt upphandlingsbevakningssystem (Python + Streamlit + SQLite) utan att göra om allt. Leverera en konkret plan + kodändringar. Krav: 1) Inför en produktkatalog (products.json) med Hogias fem produktområden. Varje produkt ska ha synonyms, must_have_signals, negative_signals, standards, capabilities. 2) Implementera per-produkt matchning: för varje procurement ska systemet returnera product_fit[] med score 0–100, kort motivering och 3–8 evidenssnuttar (från titel/beskrivning/fulltext). 3) Lägg till feedback i UI: “Relevant ✅ / Inte relevant ❌” på varje kort och spara till ny SQLite-tabell labels(procurement_id, label, reason, user, created_at). 4) Skapa en enkel “Learning”-sida som visar statistik: hur många ✅/❌, toppköpare med ❌, samt de 20 vanligaste token/ord som skiljer ✅ från ❌ (enkel TF/IDF eller frekvensbaserad diff räcker). 5) Lägg till strikt JSON-validering för Gemini-output (schema + auto-retry vid fel) och logga parse-fel. Begränsa förändringar: håll nuvarande filstruktur, behåll nuvarande regler/gates, men bygg detta som ett nytt lager ovanpå. Leverera: exakt filförslag, databas-migration, uppdaterade funktioner och UI-komponenter.

för att få den här appen till “toppnivå” behöver ni (1) bättre träffsäker matchning mot Hogias faktiska produkter och (2) bredare + renare datainhämtning än bara TED.

Här är en konkret “till toppnivå”-plan, byggd på hur svensk kollektivtrafik faktiskt är organiserad och upphandlas.

1) Gör matchningen produktstyrd (annars blir scoring alltid skört)

Just nu försöker ni hitta “relevans” via nyckelord + transportkontext. Det funkar, men blir lätt för snävt (missar upphandlingar) eller för brett (brus).

Gör så här istället: bygg ett Product→Capability→Signal-lager.

A. Definiera Hogias “produktkarta” som maskinläsbar (MVP: YAML/JSON)

Exempel på kapabiliteter (inte bara produktnamn):

Trafikledning/AVL: realtid, avvikelsehantering, depå, fordonsposition, integrationer

Passagerarinformation: hållplatsskyltar, SIRI/GTFS-RT, informationskanaler

Reseplanering & data: NeTEx/GTFS, linjedata, störningsinfo, integration Samtrafiken

Anropsstyrt/serviceresor: beställningscentral, bokning, planering/optimering, ersättning/uppföljning (färdtjänst/sjukresor/skolskjuts)

Planering & beordring: turlistor, bemanning, rosters, driftuppföljning

Sedan mappar ni varje capability till:

positiva signaler (ord/fraser + CPV + standarder)

negativa signaler (driftupphandling, rena transporttjänster, fordon, drivmedel)

dokument-snitt (vilka bilagor/sektioner brukar bära kraven)

Det här gör att AI-analysen kan svara “matchar vilka av våra kapabiliteter och varför”, och sälj får en riktig kvalificering.

Svar på din fråga: Ja, ni behöver definiera era produkter/kapabiliteter och matcha mot upphandlingar. Annars kommer ni alltid jaga nyckelord.

2) Bredda datakällorna (TED räcker inte i Sverige)

TED fångar en del EU-tröskel-annonsering, men mycket av svensk kollektivtrafik-IT + särskilt serviceresor hamnar ofta i svenska annonsdatabaser och plattformar.

Ni bör ha minst 3 “källnivåer”:

EU/TED (behåll)

Svenska annonsplattformar (för under tröskel + nationella)

Kompletterande index/aggregatorer (för att hitta sådant ni missar)

Ni har redan stubbar för Mercell/Kommers/e-Avrop: det är helt rätt riktning.

Viktigt: Där det finns API/RSS/export — använd det hellre än tung scraping. Scraping (t.ex. Scrapling) är bra som fallback, men portalsidor ändras ofta och kan ha anti-bot.

3) Serviceresor (taxi, skolskjuts, sjukresor, färdtjänst) måste bli en egen “domän”

Det du bad om: ja, ni ska absolut täcka detta.

Serviceresor är ett jättespår (volymmässigt) och har egen logik. Svensk Kollektivtrafik beskriver att kommuner ansvarar för skolskjuts och färdtjänst, men att ansvaret ofta överlåts till regional nivå, så det varierar — vilket påverkar vem som är köpare.

Så: bygg en separat klassificering:

Transporttjänst (drift) = oftast inte Hogia (men kan vara intressant om det är “beställningscentral/plattform/system”)

Beställningscentral/systemstöd = högintressant

Uppföljning/ersättning/kvalitet/planeringsoptimering = intressant

Och lägg in typiska serviceresor-signaler:

“beställningscentral”, “bokningssystem”, “planeringssystem”, “trafikplanering”, “fordons-/resursoptimering”, “ersättningsmodell”, “samordning”, “kundtjänstsystem”, “integrationer”, “API”, “SLA”

plus nyckelord för skolskjuts/färdtjänst/sjukresor

Ni kan även använda att serviceresor ofta upphandlas i paket (sjukresor + färdtjänst + skolskjuts), t.ex. syns det i praktiken hos flera regioner/bolag.

4) Gör scoringen “lärande” med feedback (utan att bygga ML-cirkus)

Ni behöver inte gå full ML direkt. Men ni behöver en loop:

A. Säljfeedback som förstaklassdata

I UI:

“Relevant / Inte relevant”

“Vilken produktkapabilitet?”

“Varför?” (kort tagg)

Spara detta och använd för:

justera vikter

lägga till/ta bort signaler

träna en enkel klassificerare senare (om ni vill)

B. Tvåstegsmodell som blir mycket vassare

Regelbaserad gate (som ni har) men kopplad till capability-matris

Semantisk matchning på “kravtext + bilagor” mot “produktkapabiliteter” (embeddings)

Det är ofta här ni går från 9/526 till “få men rätt + missar nästan inget”.

5) Nyckel: bättre “buyer resolution” (köpare/huvudman/enhet)

Säljavdelningen bryr sig mindre om titeln och mer om:

Vem är köparen egentligen? (RKM, regionförvaltning, kommun, bolag, samverkansbolag)

Är det en organisation i “branschfamiljen” (RKM/länstrafikbolag m.fl.)?

Ni kan ta en stabil “grundlista” från Svensk Kollektivtrafiks medlemslista (alla RKM/länstrafikbolag).
Och komplettera med ekosystemaktörer som Samtrafiken (ägs av RKM m.fl.).

Det här ger er:

normaliserade namn (t.ex. “Trafikförvaltningen/SL”, “Västtrafik AB”, “Region X / Länstrafiken”)

bättre matchning även när upphandlingen har “konstig” avsändare i annonsdata

6) AI-analysen: gör den till “säljpaket” (inte bara analys)

Geminis output är bra, men för sälj behöver ni standardiserade leverabler per upphandling:

Executive summary (30 sek): “Varför nu, vad köps, matchgrad, nästa steg”

Kravmatris light: Ska/Bör + vilken Hogia-modul möter vad

Risker: integrationskrav, standarder, ansvar, avtalstid, dataägarskap

Frågor att ställa på anbudskonferens (supervärdefullt i praktiken)

Bonus: Lägg in tröskel-/process-stöd i analysen (så sälj ser “hur” detta spelas). Tröskelvärden uppdateras t.ex. 1 jan 2026.

Vad jag hade gjort direkt (för maximal precision per utvecklingstimme)

Inför Product→Capability→Signal-matrisen och byt scoring till att räkna “capability coverage” + “IT-signal” + “transportkontext”.

Gör serviceresor till en egen domän med separata regler och AI-template.

Bredda datakällor (Mercell/Kommers/e-Avrop) med API/RSS först, Scrapling som fallback.

Bygg feedback-loop i UI (relevant/taggar) och börja “trimma på riktigt”.

Prompt

Du är senior systemarkitekt + upphandlingsspecialist (LOU/LUF/LUK + kollektivtrafik). Läs SYSTEM_OVERVIEW.md nedan och föreslå en toppnivå-förbättring av appen med fokus på: 1) produktdefinitioner (Hogia) och hur de ska modelleras som “capabilities” för matchning, 2) hur scoringen ska byggas om till capability-baserad ranking, 3) hur serviceresor (taxi, skolskjuts, sjukresor, färdtjänst) ska bli en separat klassificeringsdomän, 4) vilka nya datakällor i Sverige som ska prioriteras och hur man ska föredra API/RSS över scraping, 5) exakt vilka nya UI-actions som behövs för säljfeedback och hur feedbacken används för att förbättra matchningen, 6) hur AI-analysen ska paketeras till sälj (30 sek summary, kravmatris light, risks, frågor). Output ska vara: A) en prioriterad backlog i 10 punkter, B) ett nytt dataschema (fält + tabeller) för capability-matching och feedback, C) en reviderad scoring-spec med viktning och exempel, D) en kort plan för hur vi testar träffsäkerhet (precision/recall) utan att bygga tung ML.



Lexis del i projeket

Ja. Det där är exakt rätt arkitektur.

Men du måste vara hård i designen:

**Lexi = tänkpartner och researcher.**
**Upphandlingssystemet = Single Source of Truth (SSOT).**

Inte tvärtom.

---

# Så här ska det se ut mentalt

### 🔹 SSOT (Upphandlingsmotorn)

Detta är:

* Scrapers (TED + svenska källor)
* Capability-baserad scoring
* Evidence extraction
* Fulltext
* Produkt-fit
* Labels / feedback
* Audit

Den får:

* Hämta
* Klassificera
* Räkna
* Spara

Den får INTE:

* Resonera strategiskt
* Göra go/no-go
* Tänka kreativt

---

### 🔹 Lexi

Hon får:

* Resonera
* Prioritera
* Identifiera risker
* Föreslå strategi
* Formulera frågor
* Utmana antaganden

Men:

* Hon får ALDRIG hitta på fakta
* Hon får ALDRIG referera till något som inte finns i SSOT
* Hon får ALDRIG ändra data utan tool call

---

# Exakt hur du kopplar ihop det

Lexi får bara tillgång till 4 typer av verktyg:

### 1️⃣ Läs-verktyg (default safe)

* list_high_fit()
* get_procurement(id)
* get_product_fit(id)
* get_evidence(id)

→ Dessa kräver ingen approval.

---

### 2️⃣ Analys-verktyg (semisafe)

* generate_brief(id)
* generate_go_nogo(id)
* generate_risk_matrix(id)
* generate_questions(id)

→ Dessa får skriva i DB men markeras som “draft”.

---

### 3️⃣ Beslutsverktyg (approval required)

* mark_go()
* mark_no_go()
* assign_owner()
* push_to_crm()

---

### 4️⃣ Externa verktyg (always approval)

* send_email()
* create_calendar_event()
* notify_sales_team()

---

# Hur realtid faktiskt fungerar

Det är inte “Lexi övervakar allt”.

Det är:

1. Cron/scheduler kör scraper.
2. Ny upphandling > fit 70 triggar event.
3. Event skickas till Lexi.
4. Lexi:

   * Hämtar SSOT-data
   * Skapar ett 30-sekunders-brief
   * Ställer EN fråga: “Vill du att jag gör go/no-go?”

Det är proaktivitet utan kaos.

---

# Det viktigaste: evidence-first

När Lexi svarar måste hon alltid visa:

* Matchgrad
* 3–6 evidenscitat
* Vilken capability matchar
* Vilken saknas

Annars tappar du förtroende.

---

# Den riktiga vinsten här

Det här gör att Lexi inte bara “är AI”.

Hon blir:

* Säljchefens research-assistent
* KAM-stöd
* Upphandlingscoach
* Riskdetektor

Och hon jobbar på er strukturerade data, inte internet.

---

# Nu kommer den strategiska frågan

Vill du att:

A) Lexi ska vara reaktiv (du frågar henne)
eller
B) Lexi ska vara proaktiv (hon driver pipeline, pushar, ifrågasätter)?

B är kraftfullare – men kräver strikt verktygskontroll och audit.

---

# Två uppgifter (rätt ordning)

**Uppgift 1:** Definiera exakt vilka datafält i SSOT som är “trusted” och vilka som är “derived”.
**Uppgift 2:** Skriv en kort Lexi-systemprompt som tvingar henne att alltid arbeta evidence-first och aldrig spekulera.

---

# Prompt

Du är systemarkitekt för en AI-assistent (Lexi) som ska fungera som tänkpartner och researcher inom offentlig upphandling. Systemet har en Single Source of Truth (SSOT) som innehåller strukturerad upphandlingsdata, produktmatchning och evidens. Designa en arkitektur där Lexi endast får använda data från SSOT via definierade read/write tools. Krav: 1) Lexi får aldrig generera fakta som inte kan härledas till SSOT-evidence, 2) alla write-actions ska vara draft tills människa godkänner, 3) proaktiva notifieringar ska triggas av events (t.ex. new_high_fit), 4) varje svar från Lexi ska innehålla matchgrad + evidenscitat. Leverera: systemprompt, tool-interfaces, approval-policy och event-flöde.

Vill du att vi nu:

1. Definierar Lexis exakta systemprompt
   eller
2. Designar det tekniska event-flödet mellan scraper → SSOT → Lexi?
