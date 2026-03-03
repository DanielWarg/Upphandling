---
paths:
  - "tests/**/*.py"
  - "**/*test*.py"
---
# Testning

## Framework

pytest med `tmp_db` fixture (monkeypatchar `DB_PATH` → isolerad temp-databas per test).

## Konventioner

- Testfiler: `tests/test_<modul>.py`
- Testklasser: `class Test<Feature>:`
- Hjälpfunktioner: `_make_proc()`, `_insert_proc()` etc — prefix med underscore
- Alltid `tmp_db` fixture för allt som rör databasen
- Mock externa HTTP-anrop (scrapers, LLM) — testa aldrig mot riktiga servrar

## Körning

```bash
python3 -m pytest tests/ -v              # alla
python3 -m pytest tests/test_X.py -v     # en fil
python3 -m pytest tests/test_X.py::Klass::test_metod -v  # ett test
```

## Vad ska testas

- db.py: CRUD, upsert, pipeline, scoring, purge
- scorer.py: gate-logik, nyckelordspoäng, breakdown-struktur
- analyzer.py: JSON-parsning, prefilter, mock LLM-svar
- scrapers: HTML-parsning med fixtures (inte live HTTP)
- pdf_export.py: giltig PDF, batch ZIP, lokal sparning
