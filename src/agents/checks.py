"""Deterministic validators for model output. Each returns a tuple of short, stable error
codes; an empty tuple means valid. Pure functions, no I/O.

Model-written text (claims, story) is a template: it has no digits and no number words;
numbers are `{fact_key}` placeholders naming a Fact of the evidence bundle."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from agents.render import BRACED, KEY, has_stray_braces, placeholder_keys, raw_placeholders, render
from contracts.agents import (
    AnalystOutput,
    Claim,
    ClaimKind,
    EditorReview,
    EvidenceBundle,
    MomentCandidate,
    Persona,
    StoryOutput,
    StoryReview,
    Verdict,
)

_SAFE_ID = re.compile(r"[A-Za-z0-9_@/:.-]{1,32}")

TITLE_MAX, BODY_MAX = 60, 320

ONES = ("one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
        "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety").split()
NUMBER_WORDS = tuple(w for w in ONES if w != "one") + (
    "zero", "nil", "hundred", "halves", "double", "doubled", "twice", "triple", "tripled",
    "third", "thirds", "quarter", "quarters", "fourth", "fifth", "sixth", "seventh", "eighth",
    "ninth", "tenth", "dozen", "dozens", "couple", "handful")
# "one" / "single" are common English ("no one", "a single moment"); they count as number
# words only before these nouns
COUNTED_NOUNS = (r"goals?|cards?|corners?|saves?|passes|pass|shots?|chances?|press(?:es)?|pressures?|minutes?|seconds?|tackles?|"
                 r"interceptions?|duels?|fouls?|touch(?:es)?|attempts?|turnovers?|recover(?:y|ies)|wins?")
# fixed football phrases whose words would otherwise look like numbers (case-insensitive)
EXEMPT_PHRASES = ("final third", "middle third", "attacking third", "defensive third", "one-two",
                  "half-space", "half-time", "half time", "back four", "back three", "back five", "front three",
                  "front two", "third-man run", "double pivot", "double press")

_EXEMPT = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(p) for p in EXEMPT_PHRASES) + r")(?![\w-])", re.I)
_WORD = re.compile(r"\b(" + "|".join(dict.fromkeys(NUMBER_WORDS)) + r")\b", re.I)
_PLURAL_NOUNS = (r"goals|cards|corners|saves|passes|shots|chances|pressures|presses|minutes|seconds|tackles|"
                 r"interceptions|duels|fouls|touches|attempts|turnovers|recoveries|wins")
_COUNT_WORD = re.compile(r"\b(one|single|both)\s+(?:" + COUNTED_NOUNS + r")\b", re.I)
_NO_PLURAL = re.compile(r"\b(no)\s+(?:" + _PLURAL_NOUNS + r")\b", re.I)  # "no pressure", "no chance" are idioms
_ONE_DIRECTION = re.compile(r"\b(one)(?:\s+|-)(?:up|down|ahead|behind|nil)\b", re.I)
_ONE_AT_END = re.compile(r"\b(?:just|only)\s+(one)\b(?=\s*(?:[.,;:!?)—]|$))", re.I)
_ONE_OF_THEIR = re.compile(r"\b(one)\s+of\s+(?:the|their|his|her|its|our|those|these)\s+(?:\w+\s+)?(?:"
                           + COUNTED_NOUNS + r")\b", re.I)
_LONE = re.compile(r"\b(lone)\s+(?:" + COUNTED_NOUNS + r")\b", re.I)
_NONE_PAIR = re.compile(r"\b(none)\s+of\b|\ba\s+(pair)\s+of\b", re.I)
_ORDINAL_NOUNS = (r"goals?|cards?|shots?|passes|pass|chances?|corners?|saves?|tackles?|press(?:es)?|"
                  r"pressures?|minutes?")
_ORDINAL = re.compile(r"\b(first|second)\s+(?:" + _ORDINAL_NOUNS + r")\b", re.I)
_ALWAYS = re.compile(r"(?<![\w-])(brace|hat[- ]trick)(?![\w-])", re.I)
_ONCE = re.compile(r"\bonce\b", re.I)
_ONCE_FREQUENCY_NEXT = {"more", "again"}
_HALF = re.compile(r"\bhalf\b", re.I)
_HALF_BEFORE_FRACTION = {"a", "by", "one", "in"}
_HALF_PITCH_BEFORE = {"their", "our", "his", "her", "its", "own", "opposition", "opponent", "opponents",
                      "opposing", "opposite", "other", "attacking", "defensive", "home", "away",
                      "first", "second"}
_HALF_PITCH_AFTER = re.compile(r"\s+of\s+the\s+(?:pitch|field|park)\b", re.I)
_HALF_FRACTION_AFTER = re.compile(
    r"\s+(?:(?:of\s+)?(?:the|their|his|her|its|our|those|these)\s+(?:\w+\s+)?(?:" + COUNTED_NOUNS + r")\b"
    r"|of\s+(?:" + COUNTED_NOUNS + r")\b|as\s+(?:many|much|often|likely)\b)", re.I)


def safe_id(value: str) -> str:
    """Only plain identifiers are echoed into check codes (and so into traces)."""
    return value if _SAFE_ID.fullmatch(value) else "<invalid-id>"


def _fraction_half(text: str, team_tokens: frozenset[str]) -> list[str]:
    """'half' as a fraction ('half of the passes', 'a half', 'by half', 'in half'); pitch/period
    halves and hyphenated compounds ('half-volley') are fine."""
    out = []
    for m in _HALF.finditer(text):
        if text[m.end(): m.end() + 1] == "-" or text[max(0, m.start() - 1): m.start()] == "-":
            continue
        prev = re.search(r"([\w'’]+)\s*$", text[: m.start()])
        before = prev.group(1).lower().replace("’", "'") if prev else ""
        rest = text[m.end():]
        if (before in _HALF_PITCH_BEFORE or before in team_tokens or before.endswith(("'s", "s'"))
                or _HALF_PITCH_AFTER.match(rest)):
            continue
        if before in _HALF_BEFORE_FRACTION or _HALF_FRACTION_AFTER.match(rest):
            out.append("half")
    return out


def _once(text: str) -> list[str]:
    """'once' as a frequency adverb ('scored once.', 'once more', 'once again'); the conjunction
    ('once the ball went wide') and 'at once' are fine."""
    out = []
    for m in _ONCE.finditer(text):
        prev = re.search(r"(\w+)\s*$", text[: m.start()])
        if prev and prev.group(1).lower() == "at":
            continue
        rest = text[m.end():]
        nxt = re.match(r"\s+(\w+)", rest)
        after = nxt.group(1).lower() if nxt else ""
        at_end = re.match(r"\s*(?:[.,;:!?)—]|$)", rest) is not None
        if after in _ONCE_FREQUENCY_NEXT or re.match(r"\s+in\s+a\s+while\b", rest, re.I) or (
                at_end and prev is not None):
            out.append("once")
    return out


def number_words_in(text: str, team_tokens: frozenset[str] = frozenset()) -> list[str]:
    text = _EXEMPT.sub(" ", text)
    found = [m.group(1).lower() for m in _WORD.finditer(text)]
    for rx in (_COUNT_WORD, _NO_PLURAL, _ONE_DIRECTION, _ONE_AT_END, _ONE_OF_THEIR, _LONE, _ORDINAL, _ALWAYS):
        found += [re.sub(r"[ ]", "-", m.group(1).lower()) for m in rx.finditer(text)]
    found += [(m.group(1) or m.group(2)).lower() for m in _NONE_PAIR.finditer(text)]
    found += _once(text)
    found += _fraction_half(text, team_tokens)
    return found


def has_digit(text: str) -> bool:
    """Any numeric character (ASCII or other scripts, superscripts, vulgar fractions)."""
    return any(ch.isnumeric() for ch in text)


def _dedupe(codes: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(codes))


def scan_template(text: str, label: str, fact_keys: frozenset[str],
                  team_tokens: frozenset[str] = frozenset()) -> tuple[list[str], bool]:
    """Checks every rule on one model-written text. Returns (codes, placeholders_ok) where
    placeholders_ok means every placeholder is well-formed and names a bundle fact."""
    codes: list[str] = []
    ok = True
    if has_stray_braces(text):
        codes.append(f"BAD_PLACEHOLDER:{label}")
        ok = False
    for raw in raw_placeholders(text):
        if not KEY.fullmatch(raw):
            codes.append(f"BAD_PLACEHOLDER:{label}")
            ok = False
        elif raw not in fact_keys:
            codes.append(f"UNKNOWN_FACT:{label}:{raw[:64]}")
            ok = False
    rest = BRACED.sub(" ", text)
    if has_digit(rest):
        codes.append(f"DIGIT_FORBIDDEN:{label}")
    codes += [f"NUMBER_WORD:{label}:{w}" for w in number_words_in(rest, team_tokens)]
    if "<" in text or ">" in text:
        codes.append(f"MARKUP_FORBIDDEN:{label}")
    return codes, ok


def team_tokens(bundle: EvidenceBundle) -> frozenset[str]:
    """Lower-case words of the team display names ('northbridge', 'fc', ...)."""
    return frozenset(w.lower() for n in bundle.team_names.values() for w in re.findall(r"[\w]+", n))


def check_analyst(out: AnalystOutput, candidate: MomentCandidate, bundle: EvidenceBundle) -> tuple[str, ...]:
    codes: list[str] = []
    if out.candidate_id != candidate.candidate_id:
        codes.append("ID_MISMATCH:candidate_id")
    if out.snapshot_id != candidate.snapshot_id:
        codes.append("ID_MISMATCH:snapshot_id")
    if out.abstain and out.claims:
        codes.append("ABSTAIN_WITH_CLAIMS")
    if not out.abstain and not out.claims:
        codes.append("NO_CLAIMS")
    if not out.abstain and len(out.claims) > 3:
        codes.append("TOO_MANY_CLAIMS")
    if not out.abstain and out.claims and not any(c.kind == ClaimKind.observation for c in out.claims):
        codes.append("NO_OBSERVATION")
    known_events = {e.event_id for e in bundle.events}
    fact_keys = frozenset(f.key for f in bundle.facts)
    seen: set[str] = set()
    for c in out.claims:
        cid = safe_id(c.claim_id)
        if c.claim_id in seen:
            codes.append(f"DUPLICATE_CLAIM_ID:{cid}")
        seen.add(c.claim_id)
        for eid in c.evidence_event_ids:
            if eid not in known_events:
                codes.append(f"UNKNOWN_EVIDENCE:{safe_id(eid)}")
        text_codes, _ = scan_template(c.text, cid, fact_keys, team_tokens(bundle))
        codes += text_codes
    return _dedupe(codes)


def check_review(review: EditorReview, analyst_out: AnalystOutput, candidate: MomentCandidate) -> tuple[str, ...]:
    codes: list[str] = []
    if review.candidate_id != candidate.candidate_id:
        codes.append("ID_MISMATCH:candidate_id")
    if review.snapshot_id != candidate.snapshot_id:
        codes.append("ID_MISMATCH:snapshot_id")
    known = {c.claim_id for c in analyst_out.claims}
    seen: set[str] = set()
    for r in review.reviews:
        if r.claim_id not in known:
            codes.append(f"UNKNOWN_CLAIM:{safe_id(r.claim_id)}")
        elif r.claim_id in seen:
            codes.append(f"DUPLICATE_REVIEW:{safe_id(r.claim_id)}")
        seen.add(r.claim_id)
    for c in analyst_out.claims:
        if c.claim_id not in seen:
            codes.append(f"MISSING_REVIEW:{safe_id(c.claim_id)}")
    rejected = any(r.verdict == Verdict.rejected for r in review.reviews)
    hint = bool(review.repair_hint and review.repair_hint.strip())
    if rejected and not hint:
        codes.append("REPAIR_HINT_MISSING")
    if hint and not rejected:
        codes.append("REPAIR_HINT_UNEXPECTED")
    return _dedupe(codes)


def check_story(story: StoryOutput, approved_claims: Sequence[Claim], candidate: MomentCandidate,
                bundle: EvidenceBundle) -> tuple[str, ...]:
    codes: list[str] = []
    if story.candidate_id != candidate.candidate_id:
        codes.append("ID_MISMATCH:candidate_id")
    if story.snapshot_id != candidate.snapshot_id:
        codes.append("ID_MISMATCH:snapshot_id")
    approved = {c.claim_id: c for c in approved_claims}
    counts: dict[Persona, int] = {}
    for v in story.variants:
        counts[v.persona] = counts.get(v.persona, 0) + 1
    for p in Persona:
        if counts.get(p, 0) == 0:
            codes.append(f"MISSING_PERSONA:{p.value}")
        elif counts[p] > 1:
            codes.append(f"DUPLICATE_PERSONA:{p.value}")
    fact_keys = frozenset(f.key for f in bundle.facts)
    bodies: dict[Persona, str] = {}
    for v in story.variants:
        label = v.persona.value
        bodies.setdefault(v.persona, v.body)
        if not v.claim_ids:
            codes.append(f"NO_CLAIM_CITED:{label}")
        allowed: set[str] = set()
        for cid in v.claim_ids:
            claim = approved.get(cid)
            if claim is None:
                codes.append(f"CLAIM_NOT_APPROVED:{safe_id(cid)}")
            else:
                allowed |= set(placeholder_keys(claim.text))
        shown = v.title + "\n" + v.body
        text_codes, ok = scan_template(shown, label, fact_keys, team_tokens(bundle))
        codes += text_codes
        used = placeholder_keys(shown)
        codes += [f"FACT_NOT_IN_CLAIMS:{k[:64]}" for k in used if k in fact_keys and k not in allowed]
        if v.persona == Persona.casual and len(used) > 1:
            codes.append("CASUAL_TOO_MANY_NUMBERS")
        if ok:  # lengths are limits on what users see: check the rendered text
            if len(render(v.title, bundle.facts)) > TITLE_MAX or len(render(v.body, bundle.facts)) > BODY_MAX:
                codes.append(f"TOO_LONG:{label}")
    if Persona.analyst in bodies and Persona.casual in bodies and bodies[Persona.analyst] == bodies[Persona.casual]:
        codes.append("IDENTICAL_BODIES")
    return _dedupe(codes)


def check_story_review(review: StoryReview, candidate: MomentCandidate) -> tuple[str, ...]:
    codes: list[str] = []
    if review.candidate_id != candidate.candidate_id:
        codes.append("ID_MISMATCH:candidate_id")
    if review.snapshot_id != candidate.snapshot_id:
        codes.append("ID_MISMATCH:snapshot_id")
    counts: dict[Persona, int] = {}
    for r in review.reviews:
        counts[r.persona] = counts.get(r.persona, 0) + 1
    for p in Persona:
        if counts.get(p, 0) == 0:
            codes.append(f"MISSING_REVIEW:{p.value}")
        elif counts[p] > 1:
            codes.append(f"DUPLICATE_REVIEW:{p.value}")
    rejected = any(r.verdict == Verdict.rejected for r in review.reviews)
    hint = bool(review.repair_hint and review.repair_hint.strip())
    if rejected and not hint:
        codes.append("REPAIR_HINT_MISSING")
    if hint and not rejected:
        codes.append("REPAIR_HINT_UNEXPECTED")
    return _dedupe(codes)
