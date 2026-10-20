"""Deterministic validators for model output. Each returns a tuple of short, stable error
codes; an empty tuple means valid. Pure functions, no I/O."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from contracts.agents import (
    AnalystOutput,
    Claim,
    EditorReview,
    EvidenceBundle,
    MomentCandidate,
    Persona,
    StoryOutput,
    Verdict,
)
from contracts.api import MetricValue

_NUM = re.compile(r"\d+(?:\.\d+)?")


def numbers_in(text: str) -> list[float]:
    return [float(m) for m in _NUM.findall(text)]


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
    out = set(numbers_in(card.title)) | set(numbers_in(card.body))
    for m in card.metrics:
        out |= metric_numbers(m)
    return out


def _time_numbers(event_time_ms: int) -> set[float]:
    s = event_time_ms // 1000
    mm, ss = s // 60, s % 60
    return {float(mm), float(ss), float(mm + 1)}  # mm:ss and minute-of-match


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
    by_id = {e.event_id: e for e in bundle.events}
    card_nums = card_numbers(candidate)
    seen: set[str] = set()
    for c in out.claims:
        if c.claim_id in seen:
            codes.append(f"DUPLICATE_CLAIM_ID:{c.claim_id}")
        seen.add(c.claim_id)
        allowed = set(card_nums)
        for eid in c.evidence_event_ids:
            ev = by_id.get(eid)
            if ev is None:
                codes.append(f"UNKNOWN_EVIDENCE:{eid}")
            else:
                allowed |= _time_numbers(ev.event_time_ms)
        for ref in c.metric_refs:
            if ref in bundle.metrics:
                allowed |= metric_numbers(ref)
            else:
                codes.append(f"UNKNOWN_METRIC_REF:{ref.name.value}/{ref.team_id}")
        for n in numbers_in(c.text):
            if n not in allowed:
                codes.append(f"NUMBER_NOT_ALLOWED:{_fmt(n)}")
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
            codes.append(f"UNKNOWN_CLAIM:{r.claim_id}")
        elif r.claim_id in seen:
            codes.append(f"DUPLICATE_REVIEW:{r.claim_id}")
        seen.add(r.claim_id)
    for c in analyst_out.claims:
        if c.claim_id not in seen:
            codes.append(f"MISSING_REVIEW:{c.claim_id}")
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
    bodies: dict[Persona, str] = {}
    for v in story.variants:
        bodies.setdefault(v.persona, v.body)
        allowed = set(card_nums)
        for cid in v.claim_ids:
            claim = approved.get(cid)
            if claim is None:
                codes.append(f"CLAIM_NOT_APPROVED:{cid}")
            else:
                allowed |= set(numbers_in(claim.text))
        for n in numbers_in(v.title) + numbers_in(v.body):
            if n not in allowed:
                codes.append(f"NUMBER_NOT_ALLOWED:{_fmt(n)}")
        if any(ch in v.title + v.body for ch in "<>"):
            codes.append(f"MARKUP_FORBIDDEN:{v.persona.value}")
        if v.persona == Persona.casual and len(numbers_in(v.body)) > 1:
            codes.append("CASUAL_TOO_MANY_NUMBERS")
    if Persona.analyst in bodies and Persona.casual in bodies and bodies[Persona.analyst] == bodies[Persona.casual]:
        codes.append("IDENTICAL_BODIES")
    return _dedupe(codes)
