# Gemini Configuration Report

Date: 2026-06-13

Validated settings

- `GOOGLE_API_KEY`
- `GEMINI_MODEL`
- `GEMINI_MODEL_CANDIDATES`
- `GEMINI_TEMPERATURE`
- `LLM_TIMEOUT_SECONDS`

Validation behavior

- Missing `GOOGLE_API_KEY` now reports: `GOOGLE_API_KEY is not configured`.
- Invalid or unsupported Gemini models are detected by the Gemini health probe.
- Quota and network failures are surfaced through explicit messages.

Startup validation

- Environment validation runs at startup and logs warnings for missing or placeholder values.
- The app still starts locally so that non-Gemini features remain usable.
