# services/api

Read-only replay API (FastAPI, `app.py`): GET endpoints for match info, snapshots, events, window metrics and template cards of the synthetic scenarios in `scenarios/`. Contract: `src/contracts/api.py`. Scenarios are validated strictly at startup (`domain.ingest`); a broken scenario or a duplicate `match_id` stops the server.

Planned, not built: an agent worker endpoint that runs the workflow, and read-only football tools for agents.
