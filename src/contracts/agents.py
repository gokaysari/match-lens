"""Match Lens agent pipeline contract, schema_version 1.0.

Three LLM roles exchange typed, versioned artifacts (never a shared chat log):

  MomentCandidate + EvidenceBundle  (built by deterministic code)
      -> Tactical Analyst      -> AnalystOutput   (claims citing evidence)
      -> Evidence Editor       -> EditorReview    (approve / reject + repair hint)
      -> (one repair round max: Analyst again with the review)
      -> Audience Storyteller  -> StoryOutput     (persona variants of approved claims)
      -> deterministic checks  -> Insight         (published, or a template fallback)

Every artifact carries `candidate_id` + `snapshot_id`; a role can only write its
own artifact and can never change events, metrics or scores. Every model output
is validated by code (schema, evidence IDs inside the bundle, numbers taken
from the bundle's metrics) before the next step sees it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.api import Card, MetricValue
from contracts.events import SCHEMA_VERSION, MatchEvent, SInt, SStr

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class Persona(StrEnum):
    analyst = "analyst"  # data-hungry: windows, zones, rates, evidence
    casual = "casual"  # plain-language meaning, terms explained


class Role(StrEnum):
    analyst = "tactical_analyst"
    editor = "evidence_editor"
    storyteller = "audience_storyteller"
    single = "single_agent_baseline"  # same inputs/outputs, one call (evaluation only)


# ---------------------------------------------------------------- inputs (code)


class MomentCandidate(BaseModel):
    """A moment worth explaining, chosen by deterministic code (today: one per
    template Card). Agents never choose moments and never see the future."""

    model_config = _FROZEN
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    candidate_id: SStr  # "<match_id>/<card_id>"
    match_id: SStr
    snapshot_id: SStr  # watermark = trigger_seq of the source card
    watermark_seq: SInt
    trigger_clock_ms: SInt
    expires_at_ms: SInt
    source_card: Card  # the deterministic fact the moment is anchored on
    synthetic: Literal[True] = True


class EvidenceBundle(BaseModel):
    """Everything an agent may cite. Built by code from the snapshot; frozen."""

    model_config = _FROZEN
    candidate_id: SStr
    snapshot_id: SStr
    events: tuple[MatchEvent, ...]  # all with sequence <= watermark
    metrics: tuple[MetricValue, ...]  # window metrics at the watermark (metrics-v1)
    team_names: dict[str, str]  # team_id -> display name
    player_names: dict[str, str]  # player_id -> display name


# ---------------------------------------------------------------- analyst


class ClaimKind(StrEnum):
    observation = "observation"  # directly visible in events/metrics
    interpretation = "interpretation"  # a football reading of observations; hedged


class Claim(BaseModel):
    model_config = _FROZEN
    claim_id: SStr  # unique within one AnalystOutput, e.g. "c1"
    kind: ClaimKind
    text: str = Field(min_length=1, max_length=280)
    evidence_event_ids: tuple[str, ...] = Field(min_length=1)
    # metrics whose values the text quotes; every number in `text` must come
    # from these (value, numerator, denominator, or value as a whole percent)
    metric_refs: tuple[MetricValue, ...] = ()


class AnalystOutput(BaseModel):
    model_config = _FROZEN
    candidate_id: SStr
    snapshot_id: SStr
    claims: tuple[Claim, ...]  # empty only when abstaining
    alternative_explanations: tuple[str, ...] = ()
    abstain: bool = False
    abstain_reason: str | None = None


# ---------------------------------------------------------------- editor


class Verdict(StrEnum):
    approved = "approved"
    rejected = "rejected"


class ClaimReview(BaseModel):
    model_config = _FROZEN
    claim_id: SStr
    verdict: Verdict
    reason: str = Field(min_length=1, max_length=280)


class EditorReview(BaseModel):
    model_config = _FROZEN
    candidate_id: SStr
    snapshot_id: SStr
    reviews: tuple[ClaimReview, ...]  # exactly one per analyst claim
    repair_hint: str | None = None  # what the analyst should change (on any rejection)


# ---------------------------------------------------------------- storyteller


class PersonaText(BaseModel):
    model_config = _FROZEN
    persona: Persona
    language: Literal["en"] = "en"
    title: str = Field(min_length=1, max_length=60)
    body: str = Field(min_length=1, max_length=320)
    claim_ids: tuple[str, ...] = Field(min_length=1)  # approved claims it renders


class StoryOutput(BaseModel):
    model_config = _FROZEN
    candidate_id: SStr
    snapshot_id: SStr
    variants: tuple[PersonaText, ...]  # exactly one per Persona


# ---------------------------------------------------------------- result + trace


class StepStatus(StrEnum):
    ok = "ok"
    invalid = "invalid"  # output failed schema or deterministic checks
    rejected = "rejected"  # editor rejected at least one claim
    timeout = "timeout"
    error = "error"


class TraceStep(BaseModel):
    model_config = _FROZEN
    role: Role
    attempt: SInt  # 1, or 2 for the single analyst repair
    status: StepStatus
    latency_ms: SInt
    detail: str | None = None  # validation codes / error class; never secrets or prompts


class Outcome(StrEnum):
    published = "published"  # agent text passed every check
    fallback = "fallback"  # template text from source_card shown instead
    abstained = "abstained"  # analyst found nothing supportable; template shown


class Insight(BaseModel):
    """What the UI renders for one moment. Always renderable: on any failure the
    variants are built from the deterministic source_card."""

    model_config = _FROZEN
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    insight_id: SStr  # = candidate_id
    match_id: SStr
    snapshot_id: SStr
    trigger_seq: SInt
    trigger_clock_ms: SInt
    expires_at_ms: SInt
    outcome: Outcome
    variants: tuple[PersonaText, ...]  # one per Persona
    claims: tuple[Claim, ...]  # approved claims behind the variants (empty on fallback)
    evidence_event_ids: tuple[str, ...]  # union of cited events (source_card's on fallback)
    model_id: str | None = None  # deployment name used; None for fallback-only runs
    prompt_version: SStr
    synthetic: Literal[True] = True


class RunTrace(BaseModel):
    model_config = _FROZEN
    run_id: SStr
    candidate_id: SStr
    snapshot_id: SStr
    steps: tuple[TraceStep, ...]
    outcome: Outcome
    total_latency_ms: SInt
