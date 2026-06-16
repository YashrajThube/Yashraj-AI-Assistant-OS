# Release Notes — v1.0

Date: 2026-06-13

# Version 1.0

## Features

- AI Assistant (Gemini integration)
- FastAPI backend with async SQLAlchemy
- React + Vite frontend
- Analytics dashboard
- Local SQLite support for development
- Google OAuth / Calendar integration (optional)
- Automated tests (PyTest)

## Verification

- Tests: 26 / 26 passed
- Backend startup verified locally
- Frontend dev and production build verified
- CI workflow added for tests and frontend build

## Known Limitations

- Production deployment configuration (cloud infra) is not included.
- Secrets were removed from the working tree; history rewrite may be needed if secrets leaked earlier.

## Future Improvements

- Cloud deployment templates and automation
- Expanded user management and roles
- Improved analytics and dashboards
- Enhanced LLM integration and model tuning
