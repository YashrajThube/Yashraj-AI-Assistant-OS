import os
import json
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / ".env")

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
DEBUG = ENVIRONMENT != "production"

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+aiomysql://ai_user:StrongPassword123@localhost/ai_assistant")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
_raw_gemini_candidates = os.getenv("GEMINI_MODEL_CANDIDATES", "").strip()
if _raw_gemini_candidates.startswith("["):
    try:
        GEMINI_MODEL_CANDIDATES = [
            str(model).strip()
            for model in json.loads(_raw_gemini_candidates)
            if str(model).strip()
        ]
    except Exception:
        GEMINI_MODEL_CANDIDATES = []
else:
    GEMINI_MODEL_CANDIDATES = [
        model.strip()
        for model in _raw_gemini_candidates.split(",")
        if model.strip()
    ]
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "1.5"))
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "5000"))
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kolkata").strip()
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
DB_POOL_TIMEOUT_SECONDS = int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30"))
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256").strip()
JWT_ACCESS_TOKEN_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "480"))
ENABLE_JWT_AUTH = os.getenv("ENABLE_JWT_AUTH", "false").strip().lower() in {"1", "true", "yes"}
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL).strip()
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL).strip()
ENABLE_AUDIT_LOGS = os.getenv("ENABLE_AUDIT_LOGS", "true").strip().lower() in {"1", "true", "yes"}
STARTUP_VALIDATE_GOOGLE_AUTH = os.getenv("STARTUP_VALIDATE_GOOGLE_AUTH", "true").strip().lower() in {"1", "true", "yes"}
GOOGLE_CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", str(BASE_DIR / "credentials.json")).strip()
GOOGLE_TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", str(BASE_DIR / "token.json")).strip()
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"http://{API_HOST}:{API_PORT}/api/auth/callback").strip()
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").strip()
_cors_default = FRONTEND_ORIGIN if ENVIRONMENT == "production" else "http://localhost:5173,http://127.0.0.1:5173"
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", _cors_default).split(",") if origin.strip()]
