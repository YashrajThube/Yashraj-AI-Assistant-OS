**Timezone Convention**

- **APP_TIMEZONE**: Asia/Kolkata (IST, UTC+05:30)

Rules:
- All user-facing times are expressed using `APP_TIMEZONE` where appropriate.
- At the application layer, treat incoming naive datetimes as local to `Asia/Kolkata` and normalize to timezone-aware datetimes before processing.
- Do NOT force Google Calendar updates during timezone normalization; preserve existing `google_event_id` mappings.

Google Calendar expectations:
- Google events are stored with explicit timezone info in event payloads. When syncing, compare UTC-equivalent instants to avoid offset mismatches.
- Do not create new Google events for normalized DB rows; perform in-place `events.update()` only when explicitly approved.

Recommendation:
- Migrate storage to a canonical UTC representation (see docs/UTC_MIGRATION_ROADMAP.md) to avoid driver/DB timezone limitations.
