"""Single-agent baseline for evaluation. What each path gets (this is what the evaluation compares):

- pipeline (`workflow.coordinator`): editor review of the claims + one analyst repair round, then
  editor review of the story + one storyteller repair round (up to 8 model calls, 4 on the happy path).
- baseline (this module): one call producing analysis and story together, and one repair round of
  that single output when the deterministic checks fail (up to 2 model calls). No editor review.
- both: the same inputs, the same deterministic checks, the same template fallback and the same
  60 s total budget."""

from __future__ import annotations

import time
from collections.abc import Callable

from agents.checks import check_analyst, check_story
from agents.model import ModelClient
from agents.single_output import SingleAgentOutput
from contracts.agents import (
    EvidenceBundle,
    Insight,
    InsightOutcome,
    MomentCandidate,
    Role,
    RunTrace,
    StepStatus,
)
from workflow.coordinator import base_payload, dumps, parse, repair_request
from workflow.insight import BudgetExceeded, Recorder, fallback_result, published_result


def _check(out: SingleAgentOutput, candidate: MomentCandidate, bundle: EvidenceBundle) -> tuple[str, ...]:
    codes = check_analyst(out.analysis, candidate, bundle)
    if codes or out.analysis.abstain:
        return codes
    if out.story is None:
        return ("NO_STORY",)
    return check_story(out.story, out.analysis.claims, candidate, bundle)  # no editor: all claims count


async def run_single(
    candidate: MomentCandidate, bundle: EvidenceBundle, model: ModelClient, *,
    timeout_s: float = 30, total_s: float = 60, now: Callable[[], float] = time.monotonic,
) -> tuple[Insight, RunTrace]:
    """timeout_s limits one call; total_s is the budget for the call and its single repair.
    Never raises except asyncio.CancelledError (see run_moment)."""
    rec = Recorder(now, total_s)
    try:
        base = base_payload(candidate, bundle)
        payload, attempt = base, 1
        while True:
            text = await rec.call(model, Role.single, attempt, dumps(payload), timeout_s)
            if text is None:
                return fallback_result(candidate, rec, model)
            out = parse(SingleAgentOutput, text)
            codes = ("SCHEMA_INVALID",) if out is None else _check(out, candidate, bundle)
            if not codes:
                break
            rec.done(Role.single, attempt, StepStatus.invalid, codes)
            if attempt == 2:
                return fallback_result(candidate, rec, model)
            attempt = 2
            payload = {**base, "repair": repair_request(codes, text, out)}
        rec.done(Role.single, attempt, StepStatus.ok)
        if out.analysis.abstain:
            return fallback_result(candidate, rec, model, InsightOutcome.abstained)
        return published_result(candidate, bundle, rec, model, out.story, out.analysis.claims)
    except BudgetExceeded:
        return fallback_result(candidate, rec, model)
    except Exception as exc:  # noqa: BLE001
        rec.unexpected(exc)
        return fallback_result(candidate, rec, model)
