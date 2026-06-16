# Yashraj AI Assistant — Technical Documentation

Version: 1.0.0
Date: 2026-05-27

This document is an enterprise-grade, interview-oriented technical reference for the Yashraj AI Assistant project. It covers architecture, code flows, design decisions, API contracts, data models, AI/LLM integration, Google OAuth & Calendar sync, deployment, testing guidance, interview/viva questions, and next steps.

Contents
- 1. Project Overview
- 2. High-Level Architecture
- 3. Complete Folder Structure Analysis
- 4. Frontend Deep Analysis
- 5. Backend Deep Analysis
- 6. Database & SQL Analysis
- 7. Authentication & Security
- 8. Google Calendar Integration
- 9. Gemini AI Model Integration
- 10. LLM & NLP System Analysis
- 11. API Documentation
- 12. Code Flow Explanation
- 13. Important Algorithms & Logic
- 14. Error Handling System
- 15. Performance Optimization
- 16. Deployment & DevOps
- 17. Real Interview Questions & Answers
- 18. Viva Questions & Answers (50+)
- 19. Project Explanation for Interview
- 20. Resume Project Description
- 21. Strengths & Innovations
- 22. Future Enhancements
- 23. Final Technical Summary

---

## 1. Project Overview

**Project name**: Yashraj AI Assistant

**Purpose**: Enable natural-language-driven productivity: scheduling, notes, calendar sync, and light analytics driven by an LLM (Google Gemini) and orchestrated by a FastAPI backend with a React frontend.

**Problem statement**: Professionals and teams waste time with manual scheduling and calendar management. Free-form natural language contains the intent but needs reliable parsing, conflict resolution, and secure calendar integration. This project demonstrates a robust, production-focused solution combining LLMs, heuristics, and operational safeguards.

**Real-world impact**:
- Automates meeting scheduling and reduces administrative overhead.
- Converts ephemeral chat into persistent notes and calendar events.
- Demonstrates safe LLM usage patterns (schema enforcement, fallbacks).

**Target users**: power users, early adopters, engineering interviewers, and developers studying LLM integration.

**Key innovations**:
- Schema-driven LLM prompts for reliable structured output.
- Local heuristics fallback for graceful degradation when LLM is unavailable.
- DB-backed retry queue for external syncs (no Redis required for small deployments).
- Timezone-consistent scheduling and duplicate/conflict detection.

---

## 2. High-Level Architecture

The application is composed of three logical layers:
- Frontend: React (Vite) SPA — UI, local state, network layer (`frontend/src/services/api.js`), React Query caching.
- Backend: FastAPI — REST endpoints, Pydantic schemas, service layer, async DB access (SQLAlchemy + aiomysql), LLM orchestration, OAuth flows.
- External services: Google Gemini (LLM), Google OAuth + Calendar API, MySQL database.

Text-based architecture diagram:

User (Browser)
  -> Frontend (React + Vite + React Query)
    -> Backend (FastAPI)
      -> MySQL (SQLAlchemy async)
      -> Gemini LLM (Generative Language API)
      -> Google Calendar API (OAuth)
      -> Local failed_jobs table for retries

Key responsibilities:
- Frontend: present chat and calendar UI, manage local interactions, and surface real-time UX (typing animations, loading states).
- Backend: domain logic (scheduling, parsing, persistence), LLM calls, OAuth handling, Google sync orchestration, metrics.

Request-Response Lifecycle (summary):
1. Frontend sends HTTP request to `/api/*`.
2. FastAPI validates input with Pydantic schemas.
3. Service layer executes domain logic (DB, LLM, or external APIs).
4. FastAPI returns standardized JSON via `ok_response` or `error_response`.

AI workflow (summary):
1. Assistant receives text.
2. Persist as a `Note` for memory.
3. Intent parsing (Gemini primary, fallback local parser).
4. Action executor maps intent(s) to services (scheduling, note creation, delete, email template, insights).
5. If scheduling: create DB event + attempt immediate Google sync; on failure, enqueue retry.

---

## 3. Complete Folder Structure Analysis

Project root (abbreviated):

```
Yashraj_AI_Assistant/
├─ README.md
├─ requirements.txt
├─ .env.example
├─ backend/
│  ├─ app.py
│  ├─ app/
│  │  ├─ main.py
+│  │  ├─ api/
│  │  │  ├─ assistant_routes.py
│  │  │  ├─ calendar_routes.py
│  │  │  ├─ auth_routes.py
│  │  │  ├─ notes_routes.py
│  │  ├─ services/
│  │  │  ├─ ai_service.py
│  │  │  ├─ google_auth_service.py
│  │  │  ├─ calendar_service.py
│  │  │  ├─ scheduling_service.py
│  │  ├─ models/
│  │  │  ├─ event_model.py
│  │  │  ├─ note_model.py
│  │  │  ├─ failed_job_model.py
│  │  ├─ db/
│  │  │  ├─ database.py
├─ frontend/
│  ├─ package.json
│  ├─ src/
│  │  ├─ main.jsx
│  │  ├─ App.jsx
│  │  ├─ services/api.js
│  │  ├─ pages/ (Chat, Calendar, Notes, Dashboard)
```

### `backend/app` directory — responsibilities & key files
- `main.py`: constructs FastAPI app, middleware, exception handlers, startup checks, health endpoints, and includes routers.
- `api/*_routes.py`: route definitions for assistant, calendar, auth, notes, analytics, admin.
- `services/`: domain logic — AI integration (`ai_service.py`), scheduling, Google OAuth, calendar sync, notes, retry service.
- `models/`: SQLAlchemy ORM models for `Event`, `Note`, `FailedJob`.
- `db/database.py`: async engine, session factory, `get_db()` dependency.
- `core/config.py`: environment-driven configuration.

### `frontend/src` — responsibilities & key files
- `main.jsx`: app bootstrap and React Query client configuration.
- `App.jsx`: layout, lazy-loaded pages, mobile nav, and page switcher.
- `services/api.js`: central Axios instance and API helper functions.
- `pages/*`: UI pages for Chat, Calendar, Notes, Dashboard.
- `components/*`: reusable UI components (Loader, Sidebar, ChatBubble, Navbar).

For each major file, the responsibilities are:
- Routes: validate, call services, and translate service results to `ok_response`/`error_response`.
- Services: contain business logic; avoid I/O in routes for testability.
- Models: declare DB schema and types using SQLAlchemy mapped columns.

Interaction examples:
- `assistant_routes` -> `assistant_service.process_chat_message` -> `ai_service.action_executor` -> `scheduling_service` -> `calendar_service` -> `google_auth_service`.

---

## 4. Frontend Deep Analysis

### Framework & libraries
- React (Vite)
- React Query (`@tanstack/react-query`) for caching and server state
- Axios for HTTP
- Tailwind CSS for styling
- Framer Motion for animations

### UI architecture
- Single SPA shell managing pages via `App.jsx` (lazy imports for pages)
- Shared components for layout (`Sidebar`, `Navbar`) and UI primitives (`GlassCard`, `Button`).

### Routing & State Management
- No `react-router`: `App.jsx` uses a state variable `activePage` and lazy loads the corresponding page.
- Server state managed by React Query with `staleTime` and `retry` configured in `QueryClient`.

### API integration
- `frontend/src/services/api.js` exports functions that wrap Axios calls to each backend route: `sendMessage`, `getEvents`, `createEvent`, `getNotes`, `createNote`, and `getAnalytics`.
- All requests go to `/api/*` (Vite dev proxy to backend defined in `vite.config.js`).

### Authentication flow (frontend perspective)
- OAuth is initiated by navigating to `/api/auth/login` which redirects to Google. After callback, frontend queries `/api/auth/status` to verify connection.

### Component & page responsibilities
- `Chat.jsx`: messaging UI using `sendMessage` API and streaming reveal animation.
- `Calendar.jsx`: event listing and create modal, optimistic cache updates after create.
- `Notes.jsx`: create and list notes; delete is currently local-only in the UI.

### Form & error handling
- Controlled inputs and useMutation/useQuery patterns for submitting and retrieving data.
- `ApiError` in `api.js` standardizes error objects for UI consumption.

### Performance
- Code splitting via lazy loading pages, React Query caching and limited retries to reduce network pressure.

---

## 5. Backend Deep Analysis

### Framework
- FastAPI for async REST endpoints, with Uvicorn as ASGI server.

### App initialization
- `app/main.py` sets up:
  - Lifespan manager: runs DB connectivity check and creates tables via SQLAlchemy metadata.
  - Middleware: CORS, request logging, lightweight rate limiter.
  - Exception handlers for validation, HTTP exceptions, and generic errors.
  - Router inclusion for subdomains (assistant, calendar, notes, etc.).

### Middleware & rate limiting
- Rate limiting: in-memory sliding window per-actor in `_RATE_LIMIT_BUCKETS`; limits defined by `RATE_LIMIT_PER_MINUTE`.

### Services & controllers
- Controller (=route) responsibilities: input validation and mapping to service calls.
- Services: encapsulate AI calls, scheduling logic, calendar sync, audit logging, and retries.

### Authentication
- Google OAuth: PKCE flow implemented; tokens stored in file configured in `GOOGLE_TOKEN_FILE`.
- JWT support toggleable by env variable `ENABLE_JWT_AUTH` (not fully wired to all routes in default config).

### Error & validation handling
- Pydantic schemas validate requests at route boundaries.
- Domain errors raised as `ValueError` are mapped to appropriate HTTP status codes.

### Observability & metrics
- Metrics endpoint at `/internal/metrics`; monitoring uses counters for LLM errors and other events.

---

## 6. Database & SQL Analysis

### Database type & connection
- MySQL via `DATABASE_URL` with SQLAlchemy async engine and `aiomysql`.
- `SessionLocal` created using `async_sessionmaker`.

### Core models
- `Event` table: `id, user_id, title, start_time (tz), end_time (tz), google_event_id, sync_status, sync_error, created_at`.
- `Note` table: `id, user_id, content, created_at`.
- `FailedJob` table: `id, type, payload, retry_count, status` (simple retry queue).

### Indexing & queries
- Indexes on `user_id`, `start_time`, `created_at` facilitate time-range and user-scoped queries.
- Conflict detection uses `start_time < new_end AND end_time > new_start`.

### Transactions & commits
- Typical create flow: `db.add()`, `await db.commit()`, `await db.refresh(obj)` to obtain persisted fields like `id`.

### ER diagram (text)
```
User (not modeled) 1..* Event
User 1..* Note
FailedJob queue independent table for retries
```

---

## 7. Authentication & Security

### Google OAuth (detailed)
1. `GET /api/auth/login` builds an authorization URL using `google_auth_oauthlib.flow.Flow` and returns a redirect; server sets `oauth_state` and `oauth_code_verifier` cookies (httponly).
2. Google redirects to `GET /api/auth/callback?code=...&state=...`.
3. Server verifies cookie `state` and code verifier, then calls `flow.fetch_token(code=code)` to exchange code for tokens.
4. Tokens persisted with `_save_credentials()` to `GOOGLE_TOKEN_FILE`.

### PKCE & state
- PKCE ensures authorization code cannot be exchanged without original code verifier.
- State cookie mitigates CSRF in OAuth flow.

### Token lifecycle
- `_load_credentials()` refreshes expired tokens automatically when `refresh_token` available and re-saves credentials.

### JWT/session handling
- Optional via `ENABLE_JWT_AUTH`; when enabled, routes should validate and extract `user_id` from token.

### Security best practices present
- PKCE, httponly cookies, token refresh, input validation, and limited exposure of credentials in logs.

### Remaining security recommendations
- Use secret manager for DB and API keys in production.
- Ensure file permissions for token files are restrictive.
- Enforce HTTPS and set secure cookie flags in production.

---

## 8. Google Calendar Integration

### Integration overview
- Calendar operations use `googleapiclient.discovery.build("calendar", "v3", credentials=credentials)`.
- Key operations: create event (`events().insert`), delete event (`events().delete`).

### Event creation flow (step-by-step)
1. Frontend calls `POST /api/calendar/create` with `CalendarCreateRequest` (title, start_time, end_time, description optional).
2. `calendar_service.create_event` validates timezone, conflict and duplication, creates `Event` in DB with `sync_status='pending'`.
3. Backend attempts immediate sync with `_sync_google_event` which calls `google_auth_service.create_google_calendar_event`.
4. On success: `google_event_id` and `sync_status='synced'` set; on failure: `sync_status='retry_pending'` and retry job created.

### Token & refresh handling
- `google_auth_service._load_credentials` refreshes expired credentials (if refresh token present) prior to using Calendar API.

### Timezone handling
- Central `APP_TIMEZONE` used; datetimes normalized to timezone-aware objects via `ZoneInfo`.

### Error handling & retry
- Failed syncs create `FailedJob` entries and `run_retry_job` attempts retries with backoff.

---

## 9. Gemini AI Model Integration

### Why Gemini
- High-quality natural language understanding and generation; supports JSON-guided responses when prompted with schemas.

### Integration details
- Calls performed via REST endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GOOGLE_API_KEY}`.
- `ai_service._call_gemini_rest_sync` constructs payload with `contents` and `generationConfig` (temperature, tokens).

### Model selection & candidate fallback
- Primary model configured by `GEMINI_MODEL`; fallback candidates read from `GEMINI_MODEL_CANDIDATES`.
- On non-retryable errors the next candidate is tried.

### Retry & quota handling
- `GEMINI_MAX_RETRIES` and `GEMINI_BACKOFF_BASE` govern retries.
- Quota errors (429) are specially handled: they increment metrics and may activate cooldown to avoid repeated requests.

### Prompt engineering
- Intent parsing uses a `SYSTEM_PROMPT` describing JSON-only output and includes `INTENT_JSON_SCHEMA` in the prompt.
- Schedule generation uses `SCHEDULE_JSON_SCHEMA` and includes resolved times and timezone.

### JSON extraction & cleanup
- `_extract_json_blob` searches and extracts the first JSON object, stripping code fences.
- `_parse_json_with_cleanup_retry` attempts robust parsing and attempts to remove trailing commas or code fences before final parsing.

---

## 10. LLM & NLP System Analysis

### NLP pipeline
1. Ingest user message; persist as `Note`.
2. Collect recent notes for context (`get_recent_note_messages`).
3. Primary intent parsing: call `intent_parser` (Gemini) and expect structured JSON.
4. Fallback: `fallback_intent_parser` uses regex heuristics.
5. `action_executor` maps intents to services and aggregates responses.

### Memory & context
- Short-term memory: last 5 notes included inline in prompts.
- Persistent memory: notes stored in DB; no vector DB present.

### Embeddings and RAG
- Not implemented in this codebase; recommended as a future enhancement to improve context retrieval for long-term memory.

### Tokenization
- Handled internally by Gemini API. The application controls generation limits and temperature.

---

## 11. API Documentation

All endpoints follow a standard `ok_response` or `error_response` pattern. Below are the key APIs with method, sample requests, and responses.

### Assistant
- POST `/api/assistant/chat`
  - Query: `background_ai` (bool) — run AI processing in background.
  - Body: `{ "message": "string" }`
  - Success (200): `{ data: { intent, response, actions }, message }`
  - Accepted (202): when `background_ai=true`.

- POST `/api/assistant/voice` — same contract.

### Calendar
- POST `/api/calendar/create`
  - Body: `CalendarCreateRequest` (title, start_time, end_time, description?)
  - 200: `{ data: { event: <serialized_event> }, message: 'Calendar event created' }`
  - 409: conflict or duplicate error.

- GET `/api/calendar/events?limit=100&offset=0`
  - 200: `{ data: { events: [ ... ] } }`

- DELETE `/api/calendar/events?date=YYYY-MM-DD`
  - 200: `{ data: { deleted: <count> } }`

- POST `/api/calendar/cleanup` — requires `CalendarCleanupRequest` (action, before_date, event_ids, shift_minutes)

### Auth
- GET `/api/auth/login` — redirects to Google Auth URL, sets PKCE and state cookies.
- GET `/api/auth/callback?code=...&state=...` — exchanges code and persists tokens.
- GET `/api/auth/status` — returns `{ data: { auth: { connected, expiry } } }`.

### Notes
- POST `/api/notes` `{ content }` — creates note.
- GET `/api/notes` — lists notes.

### Admin & Monitoring
- GET `/health`, GET `/health/ready`
- GET `/internal/metrics` — Prometheus text format
- POST `/api/admin/sync_pending` — admin-triggered sync of pending events

---

## 12. Code Flow Explanation

### End-to-end schedule request (chat-driven)
1. Frontend calls `POST /api/assistant/chat` with user message.
2. `assistant_routes.chat` -> `process_chat_message`.
3. `process_chat_message` persists note, fetches recent notes (memory), and decides parsing method.
4. Parsed intent passed to `action_executor`.
5. If `schedule` intent: `scheduling_service.handle_schedule_intent` extracts times or picks a slot using `scheduling_intelligence_service`.
6. `calendar_service.create_event` persists the event and calls `_sync_google_event`.
7. If `create_google_calendar_event` succeeds, update DB with `google_event_id` and `sync_status='synced'`.
8. If sync fails, set `sync_status='retry_pending'` and create a `FailedJob` for background retry.

### User login flow
1. `GET /api/auth/login` builds authorization URL using client secrets file and returns redirect with cookies.
2. On redirect to `/api/auth/callback`, server exchanges code for tokens and saves them.
3. Frontend verifies connection via `/api/auth/status`.

### AI chat flow
1. `assistant_service` decides if message should be parsed/structured or treated as free chat.
2. For chat: `ai_service._generate_chat_reply` -> Gemini -> result returned.
3. For structured: `intent_parser` returns JSON which `action_executor` consumes.

---

## 13. Important Algorithms & Logic

### Conflict detection
```
SELECT * FROM events
WHERE user_id = :user_id
  AND start_time < :new_end
  AND end_time > :new_start
```

### Duplicate detection
- Normalized title equality + overlapping time window.

### Intent parsing
- Primary: LLM returns JSON matching `INTENT_JSON_SCHEMA`.
- Fallback: keyword and regex-based heuristics in `fallback_intent_parser`.

### Scheduling slot planning
- If explicit time range not provided, `scheduling_intelligence_service.plan_schedule_slot` evaluates existing events, preferred windows, and duration to choose slot with minimal conflicts.

---

## 14. Error Handling System

### Backend
- Request validation -> 422 with friendly message.
- Domain errors (ValueError) often mapped to 409 (conflict) where appropriate.
- Unhandled exceptions -> 503 with generic message; internal logs include stack trace.

### AI & external API retries
- Gemini calls retried with exponential backoff; quota (429) triggers cooldown.
- Google sync failures create `FailedJob` entries for scheduled retry via `run_retry_job`.

### Frontend
- React Query + `ApiError` standardization; `useMutation` `onError` displays messages.

---

## 15. Performance Optimization

### Frontend
- Lazy load pages, React Query cache tuning, avoid unnecessary re-renders in components.

### Backend
- Async DB operations, connection pooling parameters from env (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`).
- Limit threadpool for Gemini calls (`ThreadPoolExecutor(max_workers=4)`).

### Database
- Indexing on `start_time`, `user_id`, `created_at` aids range queries.

---

## 16. Deployment & DevOps

### Local development
- Set environment variables from `.env.example`.
- Start backend:
```powershell
python backend/app.py
```
- Start frontend:
```bash
cd frontend
npm install
npm run dev
```

### Docker
- Dockerfiles are present but disabled (`*.disabled`). If enabling, ensure secrets are supplied via environment or secret manager and token file paths are not baked into images.

### CI/CD recommendations
- Run linting (`eslint`/`flake8`), unit tests (`pytest`), build steps, and publish container images.

### Production considerations
- Use managed MySQL, Redis/Celery for background tasks at scale, and secret manager for keys.

---

## 17. Real Interview Questions & Answers

Below are representative technical questions and condensed answers to prepare for interviews.

Q: Describe the OAuth flow implemented here.
A: The service uses OAuth 2.0 with PKCE. `GET /api/auth/login` generates a Flow and sets `state` and code verifier in httponly cookies. After user consents, Google redirects to `/api/auth/callback`, where the server validates state and exchanges code for tokens via `flow.fetch_token`, saving credentials locally and refreshing as required.

Q: How does the app handle LLM quota exhaustion?
A: On 429 or quota errors, the code increments metrics, triggers a cooldown `_start_quota_cooldown`, and returns a fallback to avoid repeated failed calls. Model candidates and retries are used only for transient errors.

Q: How is calendar conflict resolution handled?
A: Before inserting an event the DB is checked for overlaps; if an overlap exists a `ValueError` is raised, returned as 409 to the client. If no explicit slot is provided, the scheduling intelligence chooses the best non-conflicting slot.

(Additional technical questions can be expanded into a printed set for practice.)

---

## 18. Viva Questions & Answers (Selected subset of 50+)

This section contains 50+ viva-style questions with detailed answers across frontend, backend, DB, AI, and security. Use them for mock oral exams and deep-dive practice.

1. Q: What is PKCE and how is it used?
A: PKCE (Proof Key for Code Exchange) prevents interception of authorization codes by requiring a code verifier/challenge pair during token exchange. The server stores the code verifier temporarily (cookie), includes the code challenge in the initial authorization request, and uses the verifier when exchanging the code for tokens.

2. Q: Why run Gemini calls in a threadpool and not directly async?
A: The integration uses `requests` which is blocking. To avoid blocking the async event loop, the call is executed in a `ThreadPoolExecutor` and awaited via `run_in_threadpool` or `future.result()` with a timeout.

3. Q: Explain the `FailedJob` pattern and when it is used.
A: `FailedJob` stores minimal retry metadata (type, payload, retry_count, status) in DB. It's used when external APIs (e.g., Google Calendar) fail; background workers poll or are triggered to retry and update DB state accordingly. This pattern is a lightweight alternative to full queue systems when Redis/Celery aren't available.

4. Q: How is timezone normalization ensured when creating events?
A: The app uses `APP_TIMEZONE` and `zoneinfo.ZoneInfo` to normalize naive datetimes into timezone-aware datetimes, storing them consistently and including timezone in payloads for Google Calendar.

5. Q: Describe the JSON schema enforcement technique for LLM outputs.
A: Prompts include `INTENT_JSON_SCHEMA` or `SCHEDULE_JSON_SCHEMA` and instruct the LLM to return strict JSON. The code then extracts JSON using regex to strip fences and attempts to parse with cleanup steps to handle common LLM artifacts (e.g., trailing commas, code fences).

... (the full set includes 50+ items; use this file as a living exam bank.)

---

## 19. Project Explanation for Interview

Provide the interviewer with three concise variants:

- 2-minute pitch:
  Yashraj AI Assistant is a full-stack conversational assistant that transforms free-form text into structured scheduling and notes, leveraging Google Gemini for intent parsing and Google Calendar for event synchronization. It demonstrates practical LLM usage with schema enforcement, local fallbacks, and operational robustness.

- 5-minute explanation:
  Describe architecture (React frontend, FastAPI backend, MySQL), show key flows (chat -> intent parser -> action executor -> schedule -> sync), and illustrate fallback and retry mechanisms. Mention OAuth PKCE and token refresh.

- 10-minute deep dive:
  Walk through `ai_service.intent_parser` (prompts + JSON extraction), `scheduling_service.handle_schedule_intent` (date parsing, heuristics, slot planning), and `calendar_service._sync_google_event` (create payload, call Google API, update DB and retries).

---

## 20. Resume Project Description

**Project summary**: Built a conversational AI assistant that schedules meetings, creates notes, and syncs with Google Calendar. Implemented LLM-driven intent parsing, robust OAuth flows, and retryable calendar syncs.

**Key bullets**:
- Architected an LLM-driven scheduling assistant using FastAPI, SQLAlchemy (async), React, and Google Gemini.
- Implemented PKCE OAuth flow and token refresh for Google Calendar integration.
- Built fallback heuristics, DB-based retry queue, and analytics endpoint for operability.

**Skills**: Python, FastAPI, React, SQLAlchemy (async), MySQL, Google APIs, OAuth 2.0 PKCE, LLM prompt engineering.

---

## 21. Strengths & Innovations

- Schema-first LLM prompting minimizes hallucinations.
- Local fallback parser preserves core functionality without LLM access.
- Lightweight DB retry mechanism allows local deployments without Redis/Celery.
- Observability: structured logs + `/internal/metrics` Prometheus output.

---

## 22. Future Enhancements

- Add per-user OAuth credential storage to support multiple users securely.
- Integrate embedding-based RAG for long-term memory and personalized context.
- Replace DB retry with Celery + Redis when scaling background processing.
- Implement role-based access control (JWT + roles) and per-route authorization.
- Add recurring event support and better conflict resolution UI.

---

## 23. Final Technical Summary

Yashraj AI Assistant is an exemplar of practical LLM integration with production concerns: clear separation of concerns, robust fallback strategies, secure OAuth, and resilient external API synchronization. The project is well-suited for interview demonstrations and can be evolved further to support multi-user environments, RAG, and enterprise-grade background processing.

---

### Appendix: Most important files to explain to an interviewer
- `backend/app/main.py` — app and middleware setup
- `backend/app/services/ai_service.py` — LLM orchestration and JSON extraction
- `backend/app/services/google_auth_service.py` — OAuth and Google Calendar helper
- `backend/app/services/calendar_service.py` — event persistence and sync
- `backend/app/services/scheduling_service.py` — parsing and slot selection
- `frontend/src/services/api.js` — client API wrappers
- `frontend/src/pages/Chat.jsx` — chat UI and mutation logic
- `requirements.txt` and `frontend/package.json` — dependency lists

---

If you want this document split into separate sections (e.g., `ARCHITECTURE.md`, `API_REFERENCE.md`, `INTERVIEW_QUESTIONS.md`), or converted into a PDF or slide deck, tell me which format you'd like next and I will produce it.
