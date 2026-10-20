"""Single-agent baseline for evaluation: one call, same checks, same fallback rules."""

from __future__ import annotations

import time
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from agents.checks import check_analyst, check_story
from agents.model import ModelClient
from contracts.agents import (
    AnalystOutput,
    EvidenceBundle,
    Insight,
    MomentCandidate,
    Outcome,
    Role,
    RunTrace,
    StepStatus,
    StoryOutput,
)
from workflow.coordinator import dumps, parse
from workflow.insight import Recorder, fallback_result, published_result


class SingleAgentOutput(BaseModel):
    """Local to the baseline (not a contract change): analysis and story in one reply."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    analysis: AnalystOutput
    story: StoryOutput


async def run_single(
    candidate: MomentCandidate, bundle: EvidenceBundle, model: ModelClient, *,
    timeout_s: float = 30, now: Callable[[], float] = time.monotonic,
) -> tuple[Insight, RunTrace]:
    rec = Recorder(now, timeout_s)
    try:
        payload = {"candidate": candidate.model_dump(mode="json"), "bundle": bundle.model_dump(mode="json")}
        text = await rec.call(model, Role.single, 1, dumps(payload), timeout_s)
        if text is None:
            return fallback_result(candidate, rec, model)
        out = parse(SingleAgentOutput, text)
        if out is None:
            codes: tuple[str, ...] = ("SCHEMA_INVALID",)
        else:
            codes = check_analyst(out.analysis, candidate, bundle)
            if not codes and not out.analysis.abstain:
                codes = check_story(out.story, out.analysis.claims, candidate)  # no editor: all claims count
        if codes:
            rec.done(Role.single, 1, StepStatus.invalid, codes)
            return fallback_result(candidate, rec, model)
        rec.done(Role.single, 1, StepStatus.ok)
        if out.analysis.abstain:
            return fallback_result(candidate, rec, model, Outcome.abstained)
        return published_result(candidate, bundle, rec, model, out.story, out.analysis.claims)
    except Exception:  # noqa: BLE001
        return fallback_result(candidate, rec, model)
