"""Deterministic coordinator: Analyst -> Editor (claims) -> Storyteller -> Editor (story). One analyst
repair round and one storyteller repair round, deterministic checks after every model step,
template fallback on any failure (an unreviewed story is never published)."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from agents.checks import check_analyst, check_review, check_story, check_story_review
from agents.model import ModelClient
from agents.render import fact_view, render, used_facts
from contracts.agents import (
    AnalystOutput,
    ClaimKind,
    EditorReview,
    EvidenceBundle,
    Insight,
    InsightOutcome,
    MomentCandidate,
    Persona,
    Role,
    RunTrace,
    StepStatus,
    StoryOutput,
    StoryReview,
    Verdict,
)
from workflow.insight import BudgetExceeded, Recorder, fallback_result, published_result


@dataclass(frozen=True)
class Timeouts:
    analyst_s: float = 20
    editor_s: float = 15
    storyteller_s: float = 15
    story_editor_s: float = 15
    total_s: float = 60


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


_FENCE = re.compile(r"\A\s*```json[ \t]*\r?\n(.*?)\r?\n?[ \t]*```\s*\Z", re.S | re.I)


def strip_fence(text: str) -> str:
    """A reply wrapped in exactly one ```json ... ``` fence is unwrapped; anything else is untouched."""
    m = _FENCE.match(text)
    return m.group(1) if m else text


def parse(model_cls: type[BaseModel], text: str):
    try:
        return model_cls.model_validate_json(strip_fence(text))
    except ValidationError:
        return None


def previous_output(text: str, parsed: BaseModel | None):
    """What the model wrote last time, for its repair round: the validated output, or the JSON
    object it wrote when that failed the schema; None when the reply was not a JSON object."""
    if parsed is not None:
        return parsed.model_dump(mode="json")
    try:
        obj = json.loads(strip_fence(text))
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def repair_request(codes, text: str, parsed: BaseModel | None) -> dict:
    repair: dict = {"check_codes": list(codes)}
    prev = previous_output(text, parsed)
    if prev is not None:
        repair["previous_output"] = prev
    return repair


def base_payload(candidate: MomentCandidate, bundle: EvidenceBundle) -> dict:
    """Analyst/editor/baseline input. Facts are shown as key/text/meaning only."""
    return {"candidate": candidate.model_dump(mode="json"),
            "bundle": bundle.model_dump(mode="json", exclude={"facts"}),
            "facts": fact_view(bundle.facts)}


async def run_moment(
    candidate: MomentCandidate, bundle: EvidenceBundle, model: ModelClient, *,
    timeouts: Timeouts = Timeouts(), now: Callable[[], float] = time.monotonic,
) -> tuple[Insight, RunTrace]:
    """Run one moment through the pipeline. Never raises for model, timeout or check failures
    (they become a traced template fallback); asyncio.CancelledError is a BaseException and is
    deliberately not caught: it propagates so the caller can cancel a run."""
    rec = Recorder(now, timeouts.total_s)
    try:
        return await _run(candidate, bundle, model, timeouts, rec)
    except BudgetExceeded:  # already traced
        return fallback_result(candidate, rec, model)
    except Exception as exc:  # noqa: BLE001 - run_moment never raises; anything unexpected is a fallback
        rec.unexpected(exc)
        return fallback_result(candidate, rec, model)


async def _run(candidate, bundle, model, timeouts: Timeouts, rec: Recorder):
    base = base_payload(candidate, bundle)
    fail = lambda: fallback_result(candidate, rec, model)  # noqa: E731
    payload, attempt, repaired, editor_n = base, 1, False, 0

    while True:
        text = await rec.call(model, Role.analyst, attempt, dumps(payload), timeouts.analyst_s)
        if text is None:
            return fail()
        out = parse(AnalystOutput, text)
        codes = ("SCHEMA_INVALID",) if out is None else check_analyst(out, candidate, bundle)
        if codes:
            rec.done(Role.analyst, attempt, StepStatus.invalid, codes)
            if repaired:
                return fail()
            repaired, attempt = True, 2
            payload = {**base, "repair": repair_request(codes, text, out)}
            continue
        rec.done(Role.analyst, attempt, StepStatus.ok)
        if out.abstain:
            return fallback_result(candidate, rec, model, InsightOutcome.abstained)

        editor_n += 1
        ed_payload = {**base, "analyst_output": out.model_dump(mode="json"),
                      "rendered_claims": {c.claim_id: render(c.text, bundle.facts) for c in out.claims}}
        text = await rec.call(model, Role.editor, editor_n, dumps(ed_payload), timeouts.editor_s)
        if text is None:
            return fail()
        review = parse(EditorReview, text)
        codes = ("SCHEMA_INVALID",) if review is None else check_review(review, out, candidate)
        if codes:
            rec.done(Role.editor, editor_n, StepStatus.invalid, codes)
            return fail()
        rejected = any(r.verdict == Verdict.rejected for r in review.reviews)
        rec.done(Role.editor, editor_n, StepStatus.rejected if rejected else StepStatus.ok)
        if rejected and not repaired:
            repaired, attempt = True, 2
            payload = {**base, "repair": {"review": review.model_dump(mode="json"),
                                          "previous_output": out.model_dump(mode="json")}}
            continue
        break

    ok_ids = {r.claim_id for r in review.reviews if r.verdict == Verdict.approved}
    approved = tuple(c for c in out.claims if c.claim_id in ok_ids)
    if not any(c.kind == ClaimKind.observation for c in approved):
        return fail()

    story_payload = {
        "candidate_id": candidate.candidate_id, "snapshot_id": candidate.snapshot_id,
        "source_fact": {"title": candidate.source_card.title, "body": candidate.source_card.body},
        "team_names": bundle.team_names, "personas": [p.value for p in Persona],
        "approved_claims": [{"claim_id": c.claim_id, "kind": c.kind.value, "text": c.text} for c in approved],
        "facts": fact_view(used_facts([c.text for c in approved], bundle.facts)),
    }
    return await _story_phase(candidate, bundle, model, timeouts, rec, approved, story_payload)


async def _story_phase(candidate, bundle, model, timeouts: Timeouts, rec: Recorder, approved, story_payload):
    """Storyteller -> story checks -> Evidence Editor (story) review, with ONE storyteller repair
    round for any check failure or rejection. A story is published only after the editor approved it."""
    fail = lambda: fallback_result(candidate, rec, model)  # noqa: E731
    payload, attempt, review_n = story_payload, 1, 0
    while True:
        text = await rec.call(model, Role.storyteller, attempt, dumps(payload), timeouts.storyteller_s)
        if text is None:
            return fail()
        story = parse(StoryOutput, text)
        codes = ("SCHEMA_INVALID",) if story is None else check_story(story, approved, candidate, bundle)
        review, rtext = None, None
        if not codes:
            rec.done(Role.storyteller, attempt, StepStatus.ok)
            review_n += 1
            ed_payload = {
                "candidate_id": candidate.candidate_id, "snapshot_id": candidate.snapshot_id,
                "team_names": bundle.team_names,
                "approved_claims": [{"claim_id": c.claim_id, "kind": c.kind.value, "template": c.text,
                                     "rendered": render(c.text, bundle.facts)} for c in approved],
                "facts": story_payload["facts"],
                "variants": [{"persona": v.persona.value, "claim_ids": list(v.claim_ids),
                              "title_template": v.title, "body_template": v.body,
                              "title": render(v.title, bundle.facts), "body": render(v.body, bundle.facts)}
                             for v in story.variants],
            }
            rtext = await rec.call(model, Role.story_editor, review_n, dumps(ed_payload),
                                   timeouts.story_editor_s)
            if rtext is None:
                return fail()
            review = parse(StoryReview, rtext)
            rcodes = ("SCHEMA_INVALID",) if review is None else check_story_review(review, candidate)
            if rcodes:
                rec.done(Role.story_editor, review_n, StepStatus.invalid, rcodes)
                return fail()  # never publish an unreviewed story
            rejected = [r.persona.value for r in review.reviews if r.verdict == Verdict.rejected]
            if not rejected:
                rec.done(Role.story_editor, review_n, StepStatus.ok)
                return published_result(candidate, bundle, rec, model, story, approved)
            rec.done(Role.story_editor, review_n, StepStatus.rejected, [f"STORY_REJECTED:{p}" for p in rejected])
            codes = tuple(f"STORY_REJECTED:{p}" for p in rejected)
        else:
            rec.done(Role.storyteller, attempt, StepStatus.invalid, codes)
        if attempt == 2:
            return fail()
        attempt = 2
        repair = repair_request(codes, text, story)
        if review is not None:
            repair["review"] = review.model_dump(mode="json")
        payload = {**story_payload, "repair": repair}
