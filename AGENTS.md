# Match Lens — project rules

Hackathon entry: Microsoft Premier League "Inside the Game". Deadline 2026-10-28 09:59 Istanbul. Plan in `TODO.md`, design rationale in local, unpublished `reports/` (Turkish; gitignored).

## Non-negotiable product rules

- All match data is synthetic (`synthetic=true`). No real Premier League data, names, logos or footage.
- Every number shown to a user is computed by deterministic code in `src/domain`. LLMs never compute counts, rates or scores.
- Every claim carries evidence IDs that resolve to immutable events inside its snapshot. Agents never read events after the snapshot watermark.
- No role (agent or code path) can modify events or scores. Tools exposed to match agents are read-only and bounded.
- The UI renders only allow-listed card templates. Never render model output as HTML (`dangerouslySetInnerHTML`, `innerHTML`, `eval`).
- No secrets in the repo, prompts, traces or test output.
- The repo will be public: never commit personal data, private links (chat shares, docs), verbatim third-party content (e.g. the official rules) or raw outputs fetched from remote services. Keep such files local and gitignored.
- Stage files explicitly by path; never `git add -A` / `git add .` / `git commit -a` without reading what gets added.

## Engineering rules

- Contracts first: shared schemas live in `src/contracts`; change them before changing producers/consumers.
- Write a failing test before implementation code (see the `test-driven-development` skill).
- Do not claim done, fixed or passing without running the command and reading its output (`verification-before-completion`).
- Pin dependency versions; no `latest`. Verify Microsoft SDK APIs against current Microsoft Learn docs (the `microsoft-learn` MCP server), not memory.
- YAGNI: no auth, queues, vector DB, A2A or extra services unless `TODO.md` lists them.
- Never report metrics, coverage or performance numbers you did not measure.

## Agent team

The main session is the lead developer: it plans, splits work into small tasks with file ownership and a done criterion, and integrates. Specialist development agents (kept locally, not in this repository) are called only when a task needs them:

| Agent | Owns |
|---|---|
| `backend-engineer` | `services/api`, `src/domain`, `src/agents`, `src/workflow`, `scenarios`, `evals`, `mcp-tests/` (contracts in `src/contracts` are lead-owned) |
| `frontend-engineer` | `apps/web` |
| `e2e-tester` | browser tests for user flows |
| `reviewer` | read-only review of a finished task's diff |

Order per task: implement → reviewer → fix (max 2 rounds) → e2e-tester when a user flow changed.
