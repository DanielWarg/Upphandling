---
paths:
  - "**/*.py"
---
# Säkerhet

## Secrets

- Alla API-nycklar och URLs via `os.environ` eller `python-dotenv`
- `.env` är gitignorerad — committa aldrig secrets
- LLM_BASE_URL och andra endpoints ska alltid komma från .env

## SQL

- ALL databasåtkomst via db.py — aldrig rå SQL i andra filer
- Använd alltid parameteriserade queries (`?` placeholders)
- Bygg aldrig SQL med f-strings eller string concatenation

## Auth

- Lösenord hanteras av streamlit-authenticator med auto_hash=True
- Admin-lösenord är hårdkodat i auth.py (accepterat för lokalt verktyg)
- Validera alltid current_user["role"] innan känsliga operationer
