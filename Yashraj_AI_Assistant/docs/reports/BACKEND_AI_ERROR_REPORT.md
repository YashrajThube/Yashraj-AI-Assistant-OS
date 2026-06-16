# Backend AI Error Report

Date: 2026-06-13

Assistant route behavior

- Route: `POST /api/assistant/chat`
- Handler: [backend/app/api/assistant_routes.py](../../backend/app/api/assistant_routes.py)
- Request model: `ChatRequest`

Error handling path

1. The route calls `process_chat_message()`.
2. `process_chat_message()` tries to process the chat or schedule request.
3. Gemini failures are handled in [backend/app/services/ai_service.py](../../backend/app/services/ai_service.py).
4. The route now includes exception diagnostics in the structured error payload if an unexpected exception occurs.

Previously hidden errors

- Gemini quota exceeded
- Invalid or missing Google API key
- Gemini timeout
- Network failures
- Generic backend exceptions

Fixes applied

- `error_response()` now includes the `data` payload so the frontend can display the actual reason.
- Assistant errors now carry diagnostic details.
- AI fallback messages are more specific and actionable.
