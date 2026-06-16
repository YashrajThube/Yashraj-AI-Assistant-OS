# Deployment Notes

This repository is prepared for local development and GitHub publication. Docker has been removed from the working tree by project policy — the project runs locally on Windows using the steps in `README.md`.

Recommended production deployment checklist:

- Use a production-grade database: MySQL or managed cloud database.
- Supply secrets with an environment/secret manager (do not commit credentials).
- Host the backend behind an ASGI server (Uvicorn / Gunicorn workers) and an HTTPS reverse proxy.
- Configure logging, monitoring, and backups.

Mermaid deployment diagram:

```mermaid
graph LR
  FE[Frontend (Static)] --> CDN
  CDN --> LB[Load Balancer]
  LB --> BE[Backend (ASGI)]
  BE --> DB[Managed SQL]
  BE --> AI[AI Provider]
  BE --> Google[Google APIs]
```
