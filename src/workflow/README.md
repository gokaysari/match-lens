# src/workflow

Deterministic coordinator (state machine): moment selection, Analyst -> Editor (claims) -> Storyteller -> Editor (story) order, one analyst repair and one storyteller repair, timeouts (60 s total), checks after every step, fallback templates. A story is published only after the editor approved it.
