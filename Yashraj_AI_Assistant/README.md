# Yashraj AI Assistant - Complete Documentation (Beginner to Deep Dive)

<!-- Badges: replace `YOUR_GITHUB_USER` with your GitHub username -->
- Build Status: ![CI](https://github.com/YOUR_GITHUB_USER/Yashraj-AI-Assistant/actions/workflows/ci.yml/badge.svg)
- Python: ![Python](https://img.shields.io/badge/python-3.11-blue)
- License: ![License](https://img.shields.io/badge/license-MIT-green)
- Tests: ![Tests](https://img.shields.io/badge/tests-26%20passed-brightgreen)


This document explains the complete system from basics to advanced details.

Goals of this README:

- Explain frontend file by file
- Explain backend file by file
- Show real code snippets and what each snippet does
- Explain API contracts clearly
- Explain database tables and data flow
- Explain full end-to-end workflow in simple language

This documentation is written for both beginners and developers who want to maintain or extend the project.

## 1. What This System Is

Yashraj AI Assistant is a full-stack assistant platform that can:

- Chat with users (Gemini or fallback response)
- Create and manage notes
- Create and manage calendar events
- Sync events with Google Calendar
- Handle failures with retry logic

Core stack:

- Frontend: React + Vite + React Query + Axios + Framer Motion
- Backend: FastAPI + Pydantic + SQLAlchemy (async)
- Database: MySQL
- AI: Google Gemini API
- Calendar integration: Google OAuth + Google Calendar API

## 2. Big Picture Architecture

```text
User (Browser)
   |
   | 1) UI action (chat, note, calendar)
   v
Frontend (React/Vite)
   |
   | 2) Axios call to /api/*
   v
FastAPI Backend
   |
   | 3) Route -> Schema validation -> Service logic
   |
   +--> MySQL (events, notes, failed_jobs)
   |
   +--> Gemini API (chat/intent fallback path)
   |
   +--> Google Calendar API (event sync)
```

## Local Development (Windows)

These instructions assume you are on Windows and want to run the entire project locally (no Docker required).

1. Create and activate a virtual environment (PowerShell):

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .venv\Scripts\Activate.ps1
```

2. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

3. Backend (run locally using SQLite for development):

```powershell
cd backend
$env:STARTUP_VALIDATE_GOOGLE_AUTH='false'
$env:DATABASE_URL='sqlite+aiosqlite:///./dev_local.db'
python app.py
```

The backend will be available at `http://127.0.0.1:5000` and the FastAPI docs at `http://127.0.0.1:5000/docs`.

4. Frontend (in a separate terminal):

```powershell
cd frontend
npm install
npm run dev
```

The frontend dev server runs at `http://localhost:5173/` by default.

5. Running tests:

```powershell
# from repository root
$env:PYTHONPATH='backend'
python -m pytest -q
```

Notes:
- The project was intentionally cleaned to remove Docker artifacts; everything above runs locally on Windows.
- Add a file `.env` in `backend/` or set environment variables as needed; see `backend/.env.example` and top-level `.env.example` for placeholders.


## 3. Full Project Structure

```text
Yashraj_AI_Assistant/
|- README.md
|- requirements.txt
|- backend/
|  |- app.py
|  |- .env
|  |- .env.example
|  |- alembic.ini
|  |- alembic/
|  |  |- env.py
|  |  |- script.py.mako
|  |  |- versions/
|  |- app/
|  |  |- main.py
|  |  |- api/
|  |  |  |- assistant_routes.py
|  |  |  |- calendar_routes.py
|  |  |  |- notes_routes.py
|  |  |  |- auth_routes.py
|  |  |- core/
|  |  |  |- config.py
|  |  |  |- logging_config.py
|  |  |  |- responses.py
|  |  |- db/
|  |  |  |- database.py
|  |  |- models/
|  |  |  |- event_model.py
|  |  |  |- note_model.py
|  |  |  |- failed_job_model.py
|  |  |- schemas/
|  |  |  |- assistant_schema.py
|  |  |  |- calendar_schema.py
|  |  |  |- note_schema.py
|  |  |- services/
|  |     |- assistant_service.py
|  |     |- ai_service.py
|  |     |- intent_service.py
|  |     |- scheduling_service.py
|  |     |- calendar_service.py
|  |     |- notes_service.py
|  |     |- deletion_service.py
|  |     |- google_auth_service.py
|  |     |- retry_service.py
|- frontend/
   |- package.json
   |- vite.config.js
   |- .env.example
   |- src/
      |- main.jsx
      |- App.jsx
      |- services/api.js
      |- pages/
      |  |- Dashboard.jsx
      |  |- Chat.jsx
      |  |- Calendar.jsx
      |  |- Notes.jsx
      |- components/
      |- hooks/
      |- index.css
      |- App.css
```

## 4. Frontend Documentation (File by File + Code + Explanation)

## 4.1 frontend/package.json

What it does:

- Defines dependencies and scripts
- Controls dev/build/lint/preview behavior

Important scripts:

```json
"scripts": {
  "dev": "vite",
  "build": "vite build",
  "lint": "eslint .",
  "preview": "vite preview"
}
```

Meaning:

- `dev`: start local development server
- `build`: create optimized production assets
- `preview`: run built files locally like production

## 4.2 frontend/vite.config.js

What it does:

- Configures Vite
- Proxies `/api` requests to backend

Code:

```js
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET || "http://127.0.0.1:5000",
        changeOrigin: true,
      },
    },
  },
});
```

Why this is important:

- Frontend can call `/api/...` without hardcoding host/port
- Helps avoid CORS issues in local development

## 4.3 frontend/src/main.jsx

What it does:

- Entry point for React app
- Creates QueryClient for data caching and API state management

Code:

```jsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});
```

Explanation:

- `staleTime: 30000`: query data is fresh for 30 seconds
- `refetchOnWindowFocus: false`: no auto-refetch on tab focus
- `retry: 1`: retry failed query once

## 4.4 frontend/src/App.jsx

What it does:

- Main app shell
- Controls active page state
- Renders sidebar/navbar and mobile nav
- Lazy loads pages

Code:

```jsx
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Chat = lazy(() => import("./pages/Chat"));
const Calendar = lazy(() => import("./pages/Calendar"));
const Notes = lazy(() => import("./pages/Notes"));
```

Explanation:

- Pages are loaded only when needed
- Improves initial load performance

## 4.5 frontend/src/services/api.js

What it does:

- Central API layer for all frontend network requests
- Uses Axios instance with timeout and consistent error shape

Main setup:

```js
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 20000,
});
```

Main exported functions:

- `sendMessage(message, background)` -> assistant chat
- `getEvents()` -> calendar event list
- `createEvent(payload)` -> create event
- `getNotes()` -> list notes
- `createNote(content)` -> create note

Why this file matters:

- Keeps API logic in one place
- Makes UI components cleaner and easier to test

## 4.6 frontend/src/pages/Chat.jsx

What it does:

- Displays conversation UI
- Sends message to backend
- Streams assistant text visually for better UX
- Shows action status chips

Important code (typing animation):

```jsx
function streamText(target, onUpdate) {
  return new Promise((resolve) => {
    let index = 0;
    const speed = 12;
    const timer = setInterval(() => {
      index += 1;
      onUpdate(target.slice(0, index));
      if (index >= target.length) {
        clearInterval(timer);
        resolve();
      }
    }, speed);
  });
}
```

Meaning:

- Backend sends full message once
- UI reveals message character-by-character for smooth feel

Important code (API call):

```jsx
const chatMutation = useMutation({
  mutationFn: (message) => sendMessage(message),
  onSuccess: async (result) => { ... },
  onError: async (error) => { ... },
});
```

Meaning:

- Uses React Query mutation for reliable async handling
- Handles success and fallback error display paths

## 4.7 frontend/src/pages/Calendar.jsx

What it does:

- Shows events list
- Opens modal to create new event
- Sends create request to backend
- Updates cache immediately after creation

Important code (event fetch):

```jsx
const eventsQuery = useQuery({ queryKey: ["events"], queryFn: getEvents });
```

Important code (event create):

```jsx
const createEventMutation = useMutation({
  mutationFn: createEvent,
  onSuccess: (created) => {
    if (created) {
      queryClient.setQueryData(["events"], (prev = []) => [created, ...prev]);
    }
  },
});
```

Meaning:

- List stays responsive without full refetch
- Newly created event appears quickly in UI

## 4.8 frontend/src/pages/Notes.jsx

What it does:

- Create and list notes
- Shows note cards
- Local-only edit and local-only delete in UI cache

Important note:

- `Delete (Local)` button currently updates frontend cache only.
- It does not call backend delete endpoint.

Important code (create):

```jsx
await createNoteMutation.mutateAsync(content);
setDraft("");
```

Meaning:

- Save note to backend
- Clear input after successful save

## 4.9 frontend/src/pages/Dashboard.jsx

What it does:

- Dashboard statistics and latest items
- Reads notes/events via React Query
- Computes simple productivity metric

Important code:

```jsx
const aiUsage = Number(localStorage.getItem("ai_usage_count") || "0");
```

Meaning:

- Tracks local usage count from chat interactions

## 4.10 frontend/src/components and hooks

Role summary:

- `Sidebar.jsx`, `Navbar.jsx`: layout and navigation
- `ChatBubble.jsx`: role-based message bubble UI
- `Button.jsx`: reusable action button
- `GlassCard.jsx`: reusable panel styling
- `Loader.jsx`: loading state component
- `hooks/useFetch.js`: optional helper hook

## 5. Backend Documentation (File by File + Code + Explanation)

## 5.1 backend/app.py

What it does:

- Starts Uvicorn using app config values

Code:

```python
if __name__ == "__main__":
    uvicorn.run("app.main:app", host=API_HOST, port=API_PORT, reload=False)
```

## 5.2 backend/app/main.py

What it does:

- Builds FastAPI app
- Runs startup validation
- Adds middleware
- Registers exception handlers
- Registers API routers

Startup validation code:

```python
await _run_startup_validation()
```

What startup validation checks:

- Database connectivity (`SELECT 1`)
- Gemini key presence
- Google OAuth status (if enabled)

Middleware included:

- Request logging middleware
- In-memory rate limiter middleware
- CORS middleware

Health endpoint:

- `GET /health`
- Returns db and service-level availability summary

## 5.3 backend/app/core/config.py

What it does:

- Loads environment variables from `.env`
- Central settings for whole backend

Important values:

- `DATABASE_URL`
- `GOOGLE_API_KEY`
- `GEMINI_MODEL`, `GEMINI_MODEL_CANDIDATES`
- `LLM_TIMEOUT_SECONDS`
- `APP_TIMEZONE` (default `Asia/Kolkata`)
- `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`
- `STARTUP_VALIDATE_GOOGLE_AUTH`
- `CORS_ORIGINS`

## 5.4 backend/app/core/logging_config.py

What it does:

- Configures structured JSON logging
- Writes to console and rotating log files

Why it matters:

- Easier production monitoring and debugging

## 5.5 backend/app/core/responses.py

What it does:

- Standard response envelope helper functions

Code:

```python
def ok_response(data=None, message="Success", status_code=200):
    return JSONResponse(status_code=status_code, content={
        "success": True,
        "data": data if data is not None else {},
        "message": message,
    })
```

Meaning:

- Every API response stays consistent across routes

## 5.6 backend/app/db/database.py

What it does:

- SQLAlchemy async engine + session factory
- Provides `get_db()` dependency used by routes

Code:

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT_SECONDS,
)
```

Meaning:

- Stable MySQL pool management for production

## 5.7 backend/app/models

### event_model.py

Represents `events` table.

Includes:

- event timing fields
- Google sync metadata (`google_event_id`, `sync_status`, `sync_error`)
- creation timestamp

### note_model.py

Represents `notes` table.

Includes:

- `user_id`
- text `content`
- `created_at`

### failed_job_model.py

Represents `failed_jobs` table.

Includes:

- job `type`
- serialized `payload`
- `retry_count`
- `status`

## 5.8 backend/app/schemas

Purpose:

- Input validation and output shape control

Main files:

- `assistant_schema.py`: chat request/response schema
- `calendar_schema.py`: create/list/cleanup event schema
- `note_schema.py`: note create/list schema

Validation example from calendar schema:

```python
if self.end_time <= self.start_time:
    raise ValueError("end_time must be after start_time")
```

## 5.9 backend/app/api (route layer)

Routes are intentionally thin. They:

- validate payload using schema
- call service function
- return standard response format

### assistant_routes.py

- `POST /api/assistant/chat`
- supports optional background mode

### calendar_routes.py

- `POST /api/calendar/create`
- `GET /api/calendar/events`
- `DELETE /api/calendar/events`
- `POST /api/calendar/cleanup`

### notes_routes.py

- `POST /api/notes`
- `GET /api/notes`

### auth_routes.py

- `GET /api/auth/login`
- `GET /api/auth/callback`
- `GET /api/auth/status`

## 5.10 backend/app/services (business logic)

### assistant_service.py

What it does:

- orchestrates a chat request end-to-end
- saves incoming message to notes
- chooses local parser for structured command
- delegates to `action_executor` in `ai_service`

### ai_service.py

What it does:

- Gemini API integration
- intent parsing prompt construction
- chat prompt construction
- fallback behavior
- cooldown on quota errors

Important production behavior:

- single call path per request
- no quota retry loop
- after quota error, skip Gemini for next 3 requests
- returns message:
  - `AI is temporarily unavailable due to usage limits. Please try again shortly.`

### intent_service.py

What it does:

- detects schedule/delete/chat intent helpers
- extracts datetime and duration from natural language
- respects app timezone (`Asia/Kolkata` by default)

### scheduling_service.py

What it does:

- handles schedule intent execution
- validates parsed time exists
- creates event and syncs to Google Calendar

Important behavior:

- if time missing, response is:
  - `Please provide time for the meeting`

### calendar_service.py

What it does:

- DB-first event creation/list/delete/cleanup
- overlap conflict detection
- sync to Google Calendar and update sync metadata

Conflict detection code:

```python
statement = select(Event).where(
    Event.user_id == user_id,
    Event.start_time < new_end,
    Event.end_time > new_start,
)
```

Meaning:

- blocks overlapping events in same time window

### notes_service.py

What it does:

- creates notes
- lists notes
- fetches recent notes for assistant context

### deletion_service.py

What it does:

- interprets delete requests
- removes target events safely

### google_auth_service.py

What it does:

- OAuth login URL generation
- callback token exchange
- token refresh and status checks

### retry_service.py

What it does:

- retry loop for failed jobs
- backoff delays: 60s, 300s, 900s

## 5.11 backend/alembic

What it does:

- schema migration management for MySQL

Important detail:

- migration env converts async URL to sync driver for Alembic runtime

## 6. API Documentation (Simple + Exact)

Base URL:

- `http://127.0.0.1:5000`

All responses are JSON.

## 6.1 Health API

Endpoint:

- `GET /health`

Use:

- quick service check

## 6.2 Assistant API

Endpoint:

- `POST /api/assistant/chat`

Request body:

```json
{
  "message": "Schedule meeting tomorrow at 10"
}
```

Response body shape:

```json
{
  "success": true,
  "data": {
    "intent": "schedule",
    "response": "...",
    "actions": []
  },
  "message": "..."
}
```

## 6.3 Calendar API

Endpoints:

- `POST /api/calendar/create`
- `GET /api/calendar/events`
- `DELETE /api/calendar/events?date=YYYY-MM-DD`
- `POST /api/calendar/cleanup`

Create request example:

```json
{
  "title": "Client Call",
  "start_time": "2026-04-15T21:00:00",
  "end_time": "2026-04-15T22:00:00"
}
```

## 6.4 Notes API

Endpoints:

- `POST /api/notes`
- `GET /api/notes?limit=50&offset=0`

Create request:

```json
{
  "content": "Remember to prepare demo"
}
```

## 6.5 Auth API

Endpoints:

- `GET /api/auth/login`
- `GET /api/auth/callback?code=...&state=...`
- `GET /api/auth/status`

Purpose:

- connect and monitor Google account integration

## 7. Database Documentation (From Basic)

Database engine:

- MySQL

Main tables:

## 7.1 events table

Stores calendar events and sync status.

Key columns:

- `id`: primary key
- `user_id`: owner
- `title`: event title
- `start_time`, `end_time`: event window
- `google_event_id`: remote Google event id
- `sync_status`: pending/synced/retry_pending
- `sync_error`: latest sync error text

## 7.2 notes table

Stores notes and message history snippets.

Key columns:

- `id`
- `user_id`
- `content`
- `created_at`

## 7.3 failed_jobs table

Stores jobs that need retry.

Key columns:

- `id`
- `type` (example: google_sync, ai_chat)
- `payload` (JSON string)
- `retry_count`
- `status`

## 8. End-to-End Workflows (How system really works)

## 8.1 Chat workflow (normal question)

1. User writes in chat box (frontend Chat page).
2. `sendMessage()` sends POST `/api/assistant/chat`.
3. Backend route validates request.
4. `assistant_service` saves message as note.
5. `ai_service` calls Gemini.
6. If Gemini quota issue, fallback message returned quickly.
7. Frontend shows response using typing animation.

## 8.2 Schedule workflow (chat command)

1. User says: `Schedule my meeting for tomorrow at 9 pm`.
2. Structured intent path is selected.
3. `intent_service.extract_datetime()` resolves datetime in app timezone.
4. `scheduling_service` creates event.
5. `calendar_service` syncs to Google Calendar.
6. Event stored in MySQL with sync metadata.
7. Response returned to frontend with action details.

## 8.3 Multi-intent workflow

Input example:

- `Schedule meeting and save note`

Execution:

1. Parser detects `schedule` + `note` intents.
2. Schedule runs first.
3. If no time detected, schedule returns:
   - `Please provide time for the meeting`
4. Note still saves successfully.
5. Frontend receives both actions and displays both outcomes.

## 8.4 Calendar create workflow (from calendar page)

1. User opens modal and submits title/start/end.
2. Frontend calls `createEvent()`.
3. Backend route validates with `CalendarCreateRequest`.
4. `calendar_service.create_event()` checks conflict and saves.
5. Background task enqueues Google sync.
6. Retry logic captures failures when needed.

## 8.5 Retry workflow

1. Sync or AI background job fails.
2. Job inserted into `failed_jobs`.
3. `retry_service` retries with delay plan (1m, 5m, 15m).
4. Status set to completed or failed.

## 9. Frontend-to-Backend Mapping Table

| Frontend Action | API Called | Backend Route | Main Service | DB Table |
| --- | --- | --- | --- | --- |
| Send chat message | POST /api/assistant/chat | assistant_routes.chat | assistant_service + ai_service | notes, events (if schedule intent) |
| Create event in calendar page | POST /api/calendar/create | calendar_routes.create_calendar_event | calendar_service | events |
| Load events | GET /api/calendar/events | calendar_routes.list_calendar_events | calendar_service | events |
| Create note | POST /api/notes | notes_routes.create_note_entry | notes_service | notes |
| Load notes | GET /api/notes | notes_routes.list_note_entries | notes_service | notes |
| OAuth connect | GET /api/auth/login | auth_routes.google_login | google_auth_service | token file |

## 10. Environment Variables (Most Important)

Backend important variables:

- `DATABASE_URL=mysql+aiomysql://ai_user:StrongPassword123@localhost/ai_assistant`
- `GOOGLE_API_KEY=...`
- `GEMINI_MODEL=gemini-2.0-flash`
- `GEMINI_MODEL_CANDIDATES=["gemini-1.5-pro"]`
- `LLM_TIMEOUT_SECONDS=1.5`
- `APP_TIMEZONE=Asia/Kolkata`
- `STARTUP_VALIDATE_GOOGLE_AUTH=true`

Frontend important variables:

- `VITE_API_BASE_URL` (optional)
- `VITE_PROXY_TARGET` (optional)

## 11. How to Run the Full System

## 11.1 Backend

```powershell
cd F:/project/Yashraj_AI_Assistant/Yashraj_AI_Assistant/backend
f:/project/Yashraj_AI_Assistant/.venv/Scripts/python.exe -m alembic upgrade head
f:/project/Yashraj_AI_Assistant/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 5000
```

## 11.2 Frontend

```powershell
cd F:/project/Yashraj_AI_Assistant/Yashraj_AI_Assistant/frontend
npm install
npm run dev
```

Then open frontend URL shown by Vite (usually `http://localhost:5173` or `http://localhost:5174`).

## 12. Quick Testing Examples

Use these in chat page or assistant API:

- `What is AI?`
- `Schedule meeting tomorrow at 10`
- `Remember task`
- `Schedule meeting and save note`
- `Schedule my meeting for tomorrow at 9 pm`

Expected behavior:

- Chat -> Gemini or fallback
- Schedule -> event created and synced
- Notes -> saved in DB
- Multi intent -> asks for time if missing, still saves note

## 13. Production Reliability Features Implemented

- Startup validation before app serves traffic
- Structured JSON logs
- DB pool tuning
- Rate limiting middleware
- Quota-aware Gemini fallback with cooldown
- Retry jobs for failed background operations
- Alembic migration support
- CORS and standardized response handling

## 14. Final Summary

This system is a complete full-stack assistant platform with clean separation of concerns:

- Frontend handles presentation and user interaction
- Backend handles validation, orchestration, and business logic
- Database stores persistent state
- External services (Gemini + Google Calendar) are integrated safely

The architecture is practical, production-oriented, and maintainable.


how to run system
Set-Location "F:\project\Yashraj_AI_Assistant\Yashraj_AI_Assistant"

activate vitual environment =& "F:\project\Yashraj_AI_Assistant\.venv\Scripts\Activate.ps1"

Start backend (Terminal 1)
Set-Location "F:\project\Yashraj_AI_Assistant\Yashraj_AI_Assistant\backend"
$env:DATABASE_URL = "mysql+aiomysql://ai_user:StrongPassword123@localhost/ai_assistant"
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 5000

start frontend terminal 2
Set-Location "F:\project\Yashraj_AI_Assistant\Yashraj_AI_Assistant\frontend"
npm install
npm run dev