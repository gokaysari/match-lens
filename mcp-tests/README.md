# MCP integration checks

Run from this directory with Node.js (tested v26.3.0) and npm (11.16.0):

```sh
npm ci
node node_modules/@playwright/mcp/cli.js install-browser chrome-for-testing
npm test
npm run smoke
```

Dependencies are pinned in package-lock.json. Azure MCP is invoked through npx with pinned version 3.0.0; its native binary may be downloaded into npm's cache. Browser binaries are downloaded into Playwright's user cache. Remote services are not version-pinned by a client lockfile.

`smoke.mjs` connects using the actual MCP client protocol, discovers tools, and executes read-only sample calls. GitHub credentials are read in memory through `gh auth token` and are never written into result files. GitHub remote tools are requested in read-only mode. Azure is launched read-only with proxy tools disabled; its sample is credential-free best practices, not an authenticated subscription operation. Foundry is an unauthenticated connection probe only. Learn and Context7 receive public documentation queries. Playwright uses an isolated headless browser against a localhost test fixture, never the user's browsing profile.

`football-server.mjs` is a tiny fixture with three hardcoded events and two published snapshots (`s2` at e2, `s3` at e3), not a production match service. Access limits are enforced from the snapshot watermark, not from schema constants. The eleven tests in `football.test.mjs` exercise real stdio MCP communication and validation, including multi-metric computation, injected delay and a SIGKILLed server process. They do not validate LLM reasoning, semantic prompt injection resistance, a production authorization layer, Microsoft Agent Framework integration, or real football API rights.

Evidence:

- `results.json` (local only, gitignored): discovered schemas and redacted/truncated sample responses from the latest remote run.
- `football-results.tap`: eleven fixture test results.
- `audit.json`: npm vulnerability database response for this installed test dependency tree.
- `azure-tools.json` (local only, gitignored): Azure CLI tool catalog, not evidence of Azure account access.

SportMonks/API-Football need provider tokens and licensed data; they were not installed or called. DBHub/AntV/Qdrant were not selected for this MVP and remain untested. No Azure resources, GitHub issues/PRs, or external messages are created by these checks.
