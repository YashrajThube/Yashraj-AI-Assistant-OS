# Dependency Report

Date: 2026-06-13

`requirements.txt` (current)

```
fastapi>=0.110,<1.0
uvicorn>=0.29,<1.0
sqlalchemy>=2.0,<3.0
aiomysql>=0.2,<1.0
pymysql>=1.1,<2.0
alembic>=1.13,<2.0
dateparser>=1.2,<2.0
python-dotenv>=1.0,<2.0
langchain-google-genai>=1.0,<3.0
requests>=2.31,<3.0
pydantic>=2.0,<3.0
google-auth-oauthlib>=1.2,<2.0
google-api-python-client>=2.140,<3.0
google-auth-httplib2>=0.2,<1.0
pytest>=8.0,<9.0
```

Observations & recommendations
- `aiomysql` and `pymysql` are only required when using MySQL in production. For local development we use SQLite (`sqlite+aiosqlite`) — consider splitting `requirements.txt` into `requirements.txt` (core) and `requirements-prod.txt` (including MySQL adapters and heavy deps).
- `langchain-google-genai` may be optional depending on LLM usage — keep if you integrate Gemini/LLMs.
- No immediate changes were made to `requirements.txt` to avoid breaking reproducibility. If you want, I can produce a trimmed development `requirements-dev.txt` that excludes heavy production-only packages.
