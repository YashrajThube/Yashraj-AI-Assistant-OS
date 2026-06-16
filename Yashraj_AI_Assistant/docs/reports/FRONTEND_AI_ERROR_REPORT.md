# Frontend AI Error Report

Date: 2026-06-13

What the chat UI does

- `Chat.jsx` sends user text through `sendMessage()` in [frontend/src/services/api.js](../../frontend/src/services/api.js).
- On success, it renders the assistant response.
- On error, it previously showed a generic fallback: `Gemini is temporarily unavailable. Please try again.`

Why the generic fallback appeared

- A network failure or a 503 from the backend caused Axios to reject the request.
- The UI did not surface the backend payload detail when the backend returned a structured error.
- The backend `error_response()` originally dropped the `data` payload entirely, so the UI could not read diagnostic details.

What changed

- The UI now inspects backend error payloads and displays the real message when available.
- Network errors are differentiated from backend errors.
- Debug logging was added to the browser console for failed chat requests.

Common displayed messages

- `Backend unreachable. Check whether the FastAPI server is running on the configured port.`
- `Rate limited. Please try again shortly.`
- `Backend service unavailable. Check API key, Gemini quota, and server logs.`
- `Authentication or API key rejected by the backend.`
