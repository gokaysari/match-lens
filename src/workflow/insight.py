"""Shared pieces of the run state machines: call recorder and Insight/RunTrace builders."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence

from agents.model import ModelClient
from agents.prompts import PROMPT_VERSION, load_prompt
from contracts.agents import (
    Claim,
    EvidenceBundle,
    Insight,
    MomentCandidate,
    Outcome,
    Persona,
    PersonaText,
    Role,
    RunTrace,
    StepStatus,
    StoryOutput,
    TraceStep,
)
from contracts.api import MetricValue


class BudgetExceeded(Exception):
    pass


class Recorder:
    """Runs model calls under timeouts and records one TraceStep per call. The detail of a
    step is only check codes or an exception class name: never prompts, inputs or secrets."""

    def __init__(self, now: Callable[[], float], total_s: float):
        self.now, self.total_s = now, total_s
        self.t0 = now()
        self.steps: list[TraceStep] = []
        self.model_ok = False  # at least one model call returned text
        self._start = self.t0

    def _ms(self, since: float) -> int:
        return max(0, int((self.now() - since) * 1000))

    def _add(self, role: Role, attempt: int, status: StepStatus, detail: str | None) -> None:
        self.steps.append(TraceStep(role=role, attempt=attempt, status=status,
                                    latency_ms=self._ms(self._start), detail=detail))

    async def call(self, model: ModelClient, role: Role, attempt: int, input_json: str,
                   timeout_s: float) -> str | None:
        remaining = self.total_s - (self.now() - self.t0)
        if remaining <= 0:
            raise BudgetExceeded()
        self._start = self.now()
        try:
            text = await asyncio.wait_for(
                model.generate(role=role, system=load_prompt(role), input_json=input_json),
                timeout=min(timeout_s, remaining),
            )
        except asyncio.TimeoutError:
            self._add(role, attempt, StepStatus.timeout, None)
            return None
        except Exception as exc:  # noqa: BLE001 - any model failure becomes a fallback
            self._add(role, attempt, StepStatus.error, type(exc).__name__)
            return None
        self.model_ok = True
        return text

    def done(self, role: Role, attempt: int, status: StepStatus, codes: Sequence[str] = ()) -> None:
        self._add(role, attempt, status, ",".join(codes) or None)

    def trace(self, candidate: MomentCandidate, outcome: Outcome) -> RunTrace:
        return RunTrace(run_id=f"{candidate.candidate_id}/run", candidate_id=candidate.candidate_id,
                        snapshot_id=candidate.snapshot_id, steps=tuple(self.steps), outcome=outcome,
                        total_latency_ms=self._ms(self.t0))


def _metric_text(m: MetricValue) -> str:
    if m.value is None:
        shown = "n/a"
    elif m.unit == "ratio":
        shown = f"{m.numerator}/{m.denominator} ({m.value:.2f})"
    else:
        shown = str(int(m.value))
    return f"{m.name.value} [{m.team_id}] = {shown}"


def template_variants(candidate: MomentCandidate) -> tuple[PersonaText, ...]:
    card = candidate.source_card
    ref = (f"template:{card.card_id}",)  # PersonaText requires >= 1 claim id; no claims on fallback
    analyst_body = card.body
    if card.metrics:
        analyst_body += " Metrics: " + "; ".join(_metric_text(m) for m in card.metrics) + "."
    return (
        PersonaText(persona=Persona.analyst, title=card.title[:60], body=analyst_body[:320], claim_ids=ref),
        PersonaText(persona=Persona.casual, title=card.title[:60], body=card.body[:320], claim_ids=ref),
    )


def _insight(candidate: MomentCandidate, outcome: Outcome, variants, claims, evidence, model_id) -> Insight:
    return Insight(
        insight_id=candidate.candidate_id, match_id=candidate.match_id, snapshot_id=candidate.snapshot_id,
        trigger_seq=candidate.source_card.trigger_seq, trigger_clock_ms=candidate.trigger_clock_ms,
        expires_at_ms=candidate.expires_at_ms, outcome=outcome, variants=tuple(variants),
        claims=tuple(claims), evidence_event_ids=tuple(evidence), model_id=model_id,
        prompt_version=PROMPT_VERSION,
    )


def fallback_result(candidate: MomentCandidate, rec: Recorder, model: ModelClient,
                    outcome: Outcome = Outcome.fallback) -> tuple[Insight, RunTrace]:
    model_id = model.model_id if rec.model_ok else None
    insight = _insight(candidate, outcome, template_variants(candidate), (),
                       candidate.source_card.evidence_event_ids, model_id)
    return insight, rec.trace(candidate, outcome)


def published_result(candidate: MomentCandidate, bundle: EvidenceBundle, rec: Recorder, model: ModelClient,
                     story: StoryOutput, claims: Sequence[Claim]) -> tuple[Insight, RunTrace]:
    seq = {e.event_id: e.sequence for e in bundle.events}
    ids = sorted({i for c in claims for i in c.evidence_event_ids}, key=seq.__getitem__)
    order = {p: i for i, p in enumerate(Persona)}
    variants = sorted(story.variants, key=lambda v: order[v.persona])
    insight = _insight(candidate, Outcome.published, variants, claims, ids, model.model_id)
    return insight, rec.trace(candidate, Outcome.published)
