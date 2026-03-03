---
paths:
  - "pages/**/*.py"
  - "app.py"
  - "auth.py"
---
# Streamlit UI

## Tema

- Svart/orange/grått SaaS-tema
- Inga emojis, inga AI-ikoner
- CSS-variabler: `--orange`, `--bg-1`, `--bg-2`, `--text-0` till `--text-3`, `--border`

## Navigation

- `st.navigation()` med `st.Page()` — INTE `st.sidebar.radio`
- Varje sida i `pages/` exporterar en `render_X()` funktion

## Prestanda

- `@st.cache_data(ttl=60)` på dyra queries (get_stats, get_all_procurements)
- Lazy imports av tunga moduler (analyzer, pdf_export) inuti funktioner

## Dialog

- `@st.dialog("Titel", width="large")` för detaljvisning
- `st.toast()` för snabb feedback
- `st.status()` med `expanded=True` för långkörande operationer
