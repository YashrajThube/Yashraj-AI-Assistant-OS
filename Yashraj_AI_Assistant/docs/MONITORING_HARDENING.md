**Monitoring & Alerting Recommendations**

Structured logging:
- Use JSON structured logs (existing `app.main` logs JSON). Include `event`, `module`, `level`, `timestamp`.

Alerting hooks:
- Integrate with PagerDuty/Slack for critical alerts: `implausible_year`, `start_after_end`, `failed_jobs` growth.

Sync anomaly detection:
- Trigger if Google consistency report shows >0 mismatches for synced events.

OAuth expiry warnings:
- Alert 24h before stored refresh token expiry (check `token.json` expiry field).
