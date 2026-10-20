"""Deterministic validators for model output. Each returns a tuple of short, stable error
codes; an empty tuple means valid. Pure functions, no I/O."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from contracts.agents import (
    AnalystOutput,
    Claim,
    ClaimKind,
    EditorReview,
    EvidenceBundle,
    MomentCandidate,
    Persona,
    StoryOutput,
    Verdict,
)
from contracts.api import MetricValue

_TIME = re.compile(r"(?<!\d)(\d{1,3}):(\d{2})(?!\d)")
_NUM = re.compile(r"(?:(?<!\w)[-\u2212+])?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)")
_SAFE_ID = re.compile(r"[A-Za-z0-9_@/:.-]{1,32}")

ONES = ("one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
        "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety").split()
NUMBER_WORDS = tuple(w for w in ONES if w != "one") + (
    "hundred", "halves", "double", "doubled", "twice", "triple", "tripled", "third", "thirds",
    "quarter", "quarters", "fourth", "fifth", "sixth", "seventh", "eighth",
    "ninth", "tenth", "dozen", "dozens", "couple", "handful")
# "one" is common English ("no one", "one of"); it counts as a number word only before these nouns
ONE_COUNTED_NOUNS = ("goal", "pass", "passes", "shot", "shots", "chance", "press", "pressure", "minute",
                     "minutes")
_WORD = re.compile(r"\b(" + "|".join(dict.fromkeys(NUMBER_WORDS)) + r")\b|\b(\d+(?:st|nd|rd|th))\b", re.I)
_ONE = re.compile(r"\b(one)\s+(?:" + "|".join(ONE_COUNTED_NOUNS) + r")\b", re.I)


def safe_id(value: str) -> str:
    """Only plain identifiers are echoed into check codes (and so into traces)."""
    return value if _SAFE_ID.fullmatch(value) else "<invalid-id>"


def numbers_in(text: str) -> list[float]:
    return [float(m.replace(",", "").replace("\u2212", "-")) for m in _NUM.findall(text)]


_HALF = re.compile(r"\bhalf\b", re.I)
_HALF_BEFORE_FRACTION = {"a", "by", "one"}
_HALF_FOLLOW_FRACTION = {"of", "the", "as", "their", "his", "her", "its", "a", "an"}
_HALF_PITCH_BEFORE = {"first", "second", "own", "other", "opposite", "opposing", "opponent"}


def _fraction_half(text: str) -> list[str]:
    """'half' as a fraction ('half of the passes', 'a half', 'by half'); pitch/period halves are fine."""
    out = []
    for m in _HALF.finditer(text):
        prev = re.search(r"([\w']+)\s*$", text[: m.start()])
        nxt = re.match(r"\s+(\w+)", text[m.end():])
        before = prev.group(1).lower() if prev else ""
        after = nxt.group(1).lower() if nxt else ""
        if before in _HALF_BEFORE_FRACTION or (
            after in _HALF_FOLLOW_FRACTION and before not in _HALF_PITCH_BEFORE and not before.endswith("'s")
        ):
            out.append("half")
    return out


def number_words_in(text: str, allowed: frozenset[str] = frozenset()) -> list[str]:
    found = [(m.group(1) or m.group(2)).lower() for m in _WORD.finditer(text)]
    found += [m.group(1).lower() for m in _ONE.finditer(text)]
    found += _fraction_half(text)
    return [w for w in found if w not in allowed]


def card_words(candidate: MomentCandidate) -> frozenset[str]:
    """Number words the deterministic source card itself uses AS numbers are allowed in
    agent text. Words the card uses otherwise (e.g. a pitch "half") grant nothing."""
    card = candidate.source_card
    return frozenset(number_words_in(card.title + " " + card.body))


def trigger_clock(candidate: MomentCandidate) -> tuple[int, int]:
    s = candidate.trigger_clock_ms // 1000
    return (s // 60, s % 60)


def clocks_in(text: str) -> set[tuple[int, int]]:
    """Every mm:ss written in `text`."""
    return {(int(m.group(1)), int(m.group(2))) for m in _TIME.finditer(text)}


def card_clocks(candidate: MomentCandidate) -> set[tuple[int, int]]:
    """Times the deterministic card states (incl. its trigger clock). They are
    allowed as mm:ss only; their digits never become bare allowed numbers."""
    card = candidate.source_card
    return clocks_in(card.title + " " + card.body) | {trigger_clock(candidate)}


def _strip_cited_clocks(text: str, clocks: set[tuple[int, int]]) -> str:
    def repl(m: re.Match) -> str:
        return " " if (int(m.group(1)), int(m.group(2))) in clocks else m.group(0)

    return _TIME.sub(repl, text)


def _fmt(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else repr(n)


def _dedupe(codes: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(codes))


def metric_numbers(m: MetricValue) -> set[float]:
    out: set[float] = set()
    if m.value is not None:
        out.add(float(m.value))
        if m.unit == "ratio":
            out.add(float(round(m.value * 100)))
    for n in (m.numerator, m.denominator):
        if n is not None:
            out.add(float(n))
    return out


def card_numbers(candidate: MomentCandidate) -> set[float]:
    card = candidate.source_card
    clocks = card_clocks(candidate)
    out = set(numbers_in(_strip_cited_clocks(card.title, clocks)))
    out |= set(numbers_in(_strip_cited_clocks(card.body, clocks)))
    for m in card.metrics:
        out |= metric_numbers(m)
    return out


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
    by_id = {e.event_id: e for e in bundle.events}
    metrics = {(m.name, m.team_id): m for m in bundle.metrics}
    card_nums = card_numbers(candidate)
    words = card_words(candidate)
    seen: set[str] = set()
    for c in out.claims:
        cid = safe_id(c.claim_id)
        if c.claim_id in seen:
            codes.append(f"DUPLICATE_CLAIM_ID:{cid}")
        seen.add(c.claim_id)
        allowed = set(card_nums)
        clocks: set[tuple[int, int]] = card_clocks(candidate)
        for eid in c.evidence_event_ids:
            ev = by_id.get(eid)
            if ev is None:
                codes.append(f"UNKNOWN_EVIDENCE:{safe_id(eid)}")
            else:
                s = ev.event_time_ms // 1000
                clocks.add((s // 60, s % 60))
        for ref in c.metric_refs:
            m = metrics.get((ref.name, ref.team_id))
            if m is None:
                codes.append(f"UNKNOWN_METRIC_REF:{ref.name.value}/{safe_id(ref.team_id)}")
            else:
                allowed |= metric_numbers(m)
        if "<" in c.text or ">" in c.text:
            codes.append(f"MARKUP_FORBIDDEN:{cid}")
        for n in numbers_in(_strip_cited_clocks(c.text, clocks)):
            if n not in allowed:
                codes.append(f"NUMBER_NOT_ALLOWED:{_fmt(n)}")
        codes += [f"NUMBER_WORD:{w}" for w in number_words_in(c.text, words)]
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


def check_story(story: StoryOutput, approved_claims: Sequence[Claim], candidate: MomentCandidate) -> tuple[str, ...]:
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
    card_nums = card_numbers(candidate)
    words = card_words(candidate)
    bodies: dict[Persona, str] = {}
    for v in story.variants:
        bodies.setdefault(v.persona, v.body)
        allowed = set(card_nums)
        clocks = card_clocks(candidate)
        if not v.claim_ids:
            codes.append(f"NO_CLAIM_CITED:{v.persona.value}")
        for cid in v.claim_ids:
            claim = approved.get(cid)
            if claim is None:
                codes.append(f"CLAIM_NOT_APPROVED:{safe_id(cid)}")
            else:
                # times the (already checked) claim states may be repeated as mm:ss;
                # their digits are not counts
                claim_clocks = clocks_in(claim.text)
                clocks |= claim_clocks
                allowed |= set(numbers_in(_strip_cited_clocks(claim.text, claim_clocks)))
        shown = v.title + " " + v.body
        nums = numbers_in(_strip_cited_clocks(shown, clocks))
        for n in nums:
            if n not in allowed:
                codes.append(f"NUMBER_NOT_ALLOWED:{_fmt(n)}")
        codes += [f"NUMBER_WORD:{w}" for w in number_words_in(shown, words)]
        if any(ch in v.title + v.body for ch in "<>"):
            codes.append(f"MARKUP_FORBIDDEN:{v.persona.value}")
        if v.persona == Persona.casual and len(nums) > 1:
            codes.append("CASUAL_TOO_MANY_NUMBERS")
    if Persona.analyst in bodies and Persona.casual in bodies and bodies[Persona.analyst] == bodies[Persona.casual]:
        codes.append("IDENTICAL_BODIES")
    return _dedupe(codes)
