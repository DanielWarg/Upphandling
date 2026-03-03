---
paths:
  - "**/*.py"
---
# Projektmönster

## Callback-pattern

Alla pipeline-funktioner tar `on_progress: Callable[[str], None] | None = None` för att streama status till Streamlit UI.

## Dataflöde

```
Scraper.fetch() → list[TenderRecord]
  → db.upsert_procurement()
  → scorer.score_procurement() → (score, rationale, breakdown)
  → analyzer.ollama_prefilter_all()
  → analyzer.analyze_all_relevant()
  → db.ensure_pipeline_entry()
  → db.auto_link_procurements_to_accounts()
```

## Databas

- `db.py` äger ALL databasåtkomst
- `upsert_procurement()` accepterar både dict och TenderRecord
- WAL-mode, UNIQUE(source, source_id) för dedup
- `purge_expired()` raderar utgångna + alla child-tabeller

## Scrapers

- Ärver `BaseScraper(ABC)` med `fetch() → list[TenderRecord]`
- Registrerade i `ALL_SCRAPERS` dict
- `with_backoff()` decorator för exponentiell retry vid 429/5xx

## Sidor

- Exporterar `render_X()` utan parametrar
- Hämtar `current_user` från `st.session_state`
- Pipeline-steg: bevakad → kvalificerad → anbud_pagaende → inskickad → vunnen/forlorad

## AI

- ENDA modell: Ministral 3 14B via llama-server
- Använd ALDRIG andra modeller eller API:er
- Tvåfas: prefilter (snabb) + djupanalys (function calling)
