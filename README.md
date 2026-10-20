# Match Lens (working title)

Match intelligence for the Microsoft Premier League "Inside the Game" Developer Hackathon. Deterministic code replays a synthetic match and computes every number; three specialist agents (Analyst, Editor, Storyteller) are meant to explain why a moment mattered, cite the evidence, and adapt the explanation for an analyst or a casual fan.

Today: deterministic replay, template cards, and the three-agent pipeline running against a scripted fake model. No real LLM is connected, there is no persona UI yet, and nothing is deployed.

All match data in this repository is synthetic. This is not an official Microsoft or Premier League product.

| Path | Purpose |
|---|---|
| `apps/web` | UI |
| `services/api` | Read-only replay API (FastAPI) |
| `src/workflow` | Deterministic coordinator |
| `src/agents` | Analyst, Editor, Storyteller |
| `src/domain` | Ingest, snapshots, metrics, template cards |
| `src/contracts` | Shared schemas |
| `scenarios` | Seeded synthetic matches |
| `evals` | Evaluation sets and baseline (planned) |
| `docs` | Submission materials (planned) |
| `infra` | Deployment (planned) |
| `mcp-tests` | MCP prototype and integration checks (see its README) |

Development tooling (local agent definitions and skills) is kept outside this repository; it is not part of the product's runtime agents.

## Run locally

Requirements: Python 3.12, Node 26. The API and the UI run in two separate terminals.

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.lock && .venv/bin/pip install --no-deps -e .

# terminal 1: API
.venv/bin/uvicorn app:app --app-dir services/api --host 127.0.0.1 --port 8000

# terminal 2: UI on http://127.0.0.1:5173
cd apps/web && npm ci && npm run dev
```

Runtime-only pins are in `requirements.lock`; `requirements-dev.lock` adds the test tools.

Regenerate derived files (both leave the working tree unchanged when nothing changed):

```sh
.venv/bin/python src/contracts/export_schemas.py        # JSON schemas from the contracts
.venv/bin/python scenarios/synthetic-01/generate.py     # synthetic scenario
```

Fake-model demo (three-agent pipeline against a scripted model, no network): `PYTHONPATH=src .venv/bin/python -m workflow.run_fake`.

Tests: `.venv/bin/pytest -q` (backend), `npm test` / `npm run typecheck` (web, in `apps/web`), `npm run e2e` (Playwright against the real API; first run `npx playwright install chromium`).

See `TODO.md` for the plan.
