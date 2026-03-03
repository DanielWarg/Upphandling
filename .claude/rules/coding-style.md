---
paths:
  - "**/*.py"
---
# Python kodstil

- Följ PEP 8
- Typhintar på alla funktionssignaturer
- Engelska identifierare, svensk UI-text
- Använd `from __future__ import annotations` bara i models.py
- Föredra `dict` och `list` framför `Dict`/`List` (Python 3.10+)
- Använd `|` för union types: `str | None` inte `Optional[str]`

## Immutabilitet

Föredra Pydantic BaseModel (redan i projektet) framför frozen dataclasses.
TenderRecord i models.py är projektets centrala datamodell.

## Formatering

- Indentering: 4 spaces
- Max radlängd: mjukt 100, hårt 120
- Importordning: stdlib → tredjepartsbibliotek → projektmoduler
