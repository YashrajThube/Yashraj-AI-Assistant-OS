**Developer Notes: Timezone & DB behavior**

MySQL / driver behavior:
- MySQL `DATETIME` columns do not store timezone offsets. Many drivers (including `aiomysql`) return naive `datetime` objects when reading `DATETIME` columns.
- This means writing timezone-aware `datetime` values may not round-trip the tzinfo; application-level conventions are required.

Why audits can still show "naive" timestamps:
- The audit reads values back from the DB via the driver which may drop tzinfo. The normalization performed at the application layer still improved semantics (we wrote tz-aware values), but the DB/driver may present them as naive.

App-level normalization logic (what we implemented):
- Detect naive datetimes (tzinfo is None).
- For naive values, assign `ZoneInfo(APP_TIMEZONE)` (Asia/Kolkata) and write back to the DB.
- Preserve `google_event_id` and `sync_status` and never trigger Google API calls during this normalization.

Notes for developers:
- Treat the DB as a storage layer that may not preserve tzinfo; prefer storing UTC in the DB and converting to `APP_TIMEZONE` at the API or UI boundary.
- When comparing DB timestamps to Google events, always convert both sides to UTC and compare instants (not formatted strings).