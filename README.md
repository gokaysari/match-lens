# Match Lens (working title)

Multi-agent match intelligence for the Microsoft Premier League "Inside the Game" Developer Hackathon. Three specialist agents explain why a moment in a synthetic match mattered, show the evidence, and adapt the explanation for an analyst or a casual fan.

All match data in this repository is synthetic. This is not an official Microsoft or Premier League product.

| Path | Purpose |
|---|---|
| `apps/web` | UI |
| `services/api` | API and agent worker |
| `src/workflow` | Deterministic coordinator |
| `src/agents` | Analyst, Editor, Storyteller |
| `src/domain` | Reducer and metrics |
| `src/contracts` | Shared schemas |
| `scenarios` | Seeded synthetic matches |
| `evals` | Evaluation sets and baseline |
| `docs` | Submission materials |
| `infra` | Deployment |
| `mcp-tests` | MCP prototype and integration checks (see its README) |

## Run locally

Requirements: Python 3.12, Node 26.

```sh
/opt/homebrew/bin/python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn app:app --app-dir services/api --host 127.0.0.1 --port 8000   # API
cd apps/web && npm ci && npm run dev                                             # UI on http://127.0.0.1:5173
```

Tests: `.venv/bin/pytest -q` (backend), `npm test` / `npm run typecheck` (web, in `apps/web`), `npm run e2e` (Playwright against the real API; first run `npx playwright install chromium`).

Status: deterministic replay slice (synthetic scenario, score, window metrics, template cards, web replay). LLM agents not built yet. See `TODO.md`.
