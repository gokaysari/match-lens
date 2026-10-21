# evals

Planned, not built yet: fixed evaluation windows, a single-agent baseline and recorded results (seed, model, prompt version, budget). This directory is currently empty apart from this file; the single-agent comparison path lives in `src/workflow/single_agent.py`.

## What each path gets (this is what the evaluation compares)

| | pipeline | single-agent baseline |
|---|---|---|
| Model calls | analyst, claim editor, storyteller, story editor | one call (analysis + story) |
| Review by the Evidence Editor | claims, then the story | none |
| Repair rounds | one analyst repair (after a claim rejection or check failure) and one storyteller repair (after a story rejection or check failure) | one repair of its single output (after a check failure) |
| Max model calls per moment | 8 (4 on the happy path) | 2 |
| Deterministic checks, fallback | same | same |
| Total budget | 60 s | 60 s |

The baseline keeps its one repair round because it covers its single output; it does not get a second round for the story.
