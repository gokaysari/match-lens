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

Status: scaffolding only. See `TODO.md` for the plan.
