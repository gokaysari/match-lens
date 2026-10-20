# src/agents

The three LLM roles: Tactical Analyst, Evidence Editor, Audience Storyteller. No role can modify events or scores.

Model text carries no digits or number words: numbers are `{fact_key}` placeholders naming deterministic Facts (`workflow/facts.py`); `agents/checks.py` enforces it and `agents/render.py` renders the values.
