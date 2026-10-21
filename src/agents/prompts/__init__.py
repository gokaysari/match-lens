"""System prompts, one markdown file per role. Constant text: no match data is ever
interpolated; the JSON Schema of the expected output is appended at load time."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from agents.single_output import SingleAgentOutput
from contracts.agents import AnalystOutput, EditorReview, Role, StoryOutput, StoryReview

PROMPT_VERSION = "p4"

_DIR = Path(__file__).parent
_FILES = {
    Role.analyst: "tactical_analyst.md",
    Role.editor: "evidence_editor.md",
    Role.storyteller: "audience_storyteller.md",
    Role.story_editor: "evidence_editor_story.md",
    Role.single: "single_agent_baseline.md",
}


def _output_model(role: Role):
    if role == Role.analyst:
        return AnalystOutput
    if role == Role.editor:
        return EditorReview
    if role == Role.storyteller:
        return StoryOutput
    if role == Role.story_editor:
        return StoryReview
    return SingleAgentOutput


_NUMBERS_ROLES = frozenset({Role.analyst, Role.storyteller, Role.single})  # roles that write text


def _read(name: str) -> str:
    return (_DIR / name).read_text(encoding="utf-8").rstrip()


@lru_cache(maxsize=None)
def load_prompt(role: Role) -> str:
    parts = [_read(_FILES[role])]
    if role in _NUMBERS_ROLES:
        parts.append(_read("_numbers.md"))
    parts.append(_read("_rules.md"))
    text = "\n\n".join(parts)
    schema = json.dumps(_output_model(role).model_json_schema(), sort_keys=True, indent=1)
    return f"{text}\n\n## Output JSON Schema\n\n```json\n{schema}\n```\n"
