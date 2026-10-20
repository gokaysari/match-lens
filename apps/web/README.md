# apps/web

Match Lens replay UI: Vite + React + TypeScript SPA. Synthetic pitch replay, score, insight cards with evidence, 60 s metrics.
The client never computes score, metrics or card content; it drives the replay locally and asks the API (`/api`, contract in `src/contracts`) for the snapshot, metrics and cards of the current watermark. Model text is rendered as plain text only.

- `npm run dev`: Vite on http://127.0.0.1:5173, proxies `/api` to http://127.0.0.1:8000
- `npm test`, `npm run typecheck`, `npm run build`
