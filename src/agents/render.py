"""Placeholder grammar and rendering. Model text is a template: numbers appear only as
`{fact_key}` (grammar: `{` + FACT_KEY_PATTERN + `}`); code replaces them with Fact.text."""

from __future__ import annotations

import re
from collections.abc import Iterable

from contracts.agents import FACT_KEY_PATTERN, Fact

BRACED = re.compile(r"\{([^{}]*)\}")
KEY = re.compile(FACT_KEY_PATTERN)


def raw_placeholders(text: str) -> list[str]:
    """Contents of every well-nested `{...}` in order (may be malformed keys)."""
    return BRACED.findall(text)


def has_stray_braces(text: str) -> bool:
    rest = BRACED.sub(" ", text)
    return "{" in rest or "}" in rest


def placeholder_keys(text: str) -> list[str]:
    """Only the well-formed keys, in order, repeats kept."""
    return [k for k in raw_placeholders(text) if KEY.fullmatch(k)]


def render(template: str, facts: Iterable[Fact]) -> str:
    """Replace each `{key}` by the text of the fact with that key. Raises KeyError for a key
    that is not among `facts` (callers validate templates first)."""
    by_key = {f.key: f.text for f in facts}
    return BRACED.sub(lambda m: by_key[m.group(1)], template)


def used_facts(templates: Iterable[str], facts: Iterable[Fact]) -> tuple[Fact, ...]:
    """The facts quoted by `templates`, in order of first use."""
    by_key = {f.key: f for f in facts}
    keys = dict.fromkeys(k for t in templates for k in placeholder_keys(t))
    return tuple(by_key[k] for k in keys if k in by_key)


def fact_view(facts: Iterable[Fact]) -> list[dict[str, str]]:
    """What a model sees of a fact: key, text, meaning (never event ids)."""
    return [{"key": f.key, "text": f.text, "meaning": f.meaning} for f in facts]
