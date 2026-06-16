# AI Request Flow Report

Date: 2026-06-13

Execution trace

1. User enters a message in [frontend/src/pages/Chat.jsx](../../frontend/src/pages/Chat.jsx).
2. `handleSend()` calls `sendMessage()` from [frontend/src/services/api.js](../../frontend/src/services/api.js).
3. Axios posts to `POST /api/assistant/chat`.
4. Backend route [backend/app/api/assistant_routes.py](../../backend/app/api/assistant_routes.py) validates the request using `ChatRequest`.
5. The route calls `process_chat_message()` from [backend/app/services/assistant_service.py](../../backend/app/services/assistant_service.py).
6. `process_chat_message()` decides whether the request is structured (`schedule`, `note`, etc.) or free-form chat.
7. Structured requests are sent to `action_executor()` in [backend/app/services/ai_service.py](../../backend/app/services/ai_service.py).
8. Schedule requests call `handle_schedule_intent()` in [backend/app/services/scheduling_service.py](../../backend/app/services/scheduling_service.py).
9. `handle_schedule_intent()` calls `generate_schedule_metadata()` in [backend/app/services/ai_service.py](../../backend/app/services/ai_service.py).
10. If Gemini is unavailable or quota-limited, the backend now falls back to local formatting and returns a specific message.
11. The backend responds with `ok_response()` or `error_response()` from [backend/app/core/responses.py](../../backend/app/core/responses.py).
12. The frontend renders the response and action chips, or shows a detailed fallback via `describeError()`.

Environment variables used

- `DATABASE_URL`
- `GOOGLE_API_KEY`
- `GEMINI_MODEL`
- `GEMINI_MODEL_CANDIDATES`
- `GEMINI_TEMPERATURE`
- `LLM_TIMEOUT_SECONDS`
- `STARTUP_VALIDATE_GOOGLE_AUTH`
- `ENABLE_JWT_AUTH`
- `SECRET_KEY` / `JWT_SECRET_KEY`
- `VITE_API_BASE_URL` (frontend only)

Service dependencies

- Frontend chat depends on Axios and the backend `/api/assistant/chat` endpoint.
- Assistant service depends on:
  - AI service
  - scheduling service
  - notes service
  - retry/audit helpers
- AI service depends on Gemini REST, fallback parsers, and scheduling helpers.
- Schedule flow depends on calendar persistence and optional Google Calendar sync.
