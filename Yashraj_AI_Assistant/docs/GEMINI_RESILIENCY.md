**Gemini Resiliency Improvements**

Short-term improvements:
- Add exponential backoff and jitter for LLM calls (already supported in retry patterns). Increase retries for transient rate limits.
- Detect 429/5xx from Gemini and fall back to local parser with structured response.
- Log quota usage and expose a `/metrics` endpoint for Prometheus.

Monitoring:
- Alert on sustained fallback usage (e.g., >10% of assistant calls fall back in 15m window).

Long term:
- Add multi-model fanout (primary/secondary) and cost-aware routing.