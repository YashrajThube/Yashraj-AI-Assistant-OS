"""Wrapper to run nightly audits and collect reports.

This script is safe and non-destructive — runs dry-runs and saves JSON reports.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

async def main():
    base = Path(__file__).parent
    reports = {}
    # Run DB audit
    from db_integrity_audit import run_audit
    rpt = await run_audit(False)
    reports['db'] = rpt

    # Run normalization dry-run
    from normalize_timezones import normalize
    nr = await normalize(False)
    reports['normalize'] = nr

    out = base / 'nightly_audit_summary.json'
    out.write_text(json.dumps(reports, indent=2), encoding='utf-8')
    print('Wrote', out)

if __name__ == '__main__':
    asyncio.run(main())
