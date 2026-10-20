"""Match Lens read API contract, schema_version 1.0.

Every response is scoped to one snapshot: the state of the match after the
event with sequence `watermark_seq`. Nothing after the watermark is ever
included. `snapshot_id` is "<match_id>@<watermark_seq>".

Endpoints (all GET, JSON, served under /api):
  /matches/{match_id}/meta                         -> MatchInfo (public; no scripted moments)
  /matches/{match_id}/snapshot?at_seq=N             -> Snapshot
  /matches/{match_id}/events?at_seq=N&from_seq=M     -> EventPage (events with M <= seq <= N;
                                                       at_seq defaults to the last event,
                                                       from_seq to the first: the replay
                                                       client loads the full timeline once)
  /matches/{match_id}/metrics?at_seq=N&window_s=60  -> WindowMetrics
  /matches/{match_id}/cards?at_seq=N                -> CardList
`at_seq` is REQUIRED on snapshot, metrics and cards (missing -> 422
INVALID_QUERY; only /events defaults it) and must be the sequence of an
existing event; otherwise 404 with code UNKNOWN_SEQUENCE.
Windows never cross periods: a window covers events of the watermark's period only. Unknown match -> 404 UNKNOWN_MATCH. Errors use ApiError.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from contracts.events import SCHEMA_VERSION, MatchEvent, Player, Score, SInt, SStr, Team

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class ApiError(BaseModel):
    model_config = _FROZEN
    code: SStr
    message: SStr


class MatchInfo(BaseModel):
    """What a client may know before the replay starts. ScenarioMeta's `moments`
    and `title` describe the scripted future (test oracle) and are never served."""

    model_config = _FROZEN
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    match_id: SStr
    teams: tuple[Team, ...]
    players: tuple[Player, ...]
    initial_score: Score
    segment_start_ms: SInt
    segment_end_ms: SInt
    synthetic: Literal[True] = True


class Snapshot(BaseModel):
    model_config = _FROZEN
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    match_id: SStr
    snapshot_id: SStr
    watermark_seq: SInt
    watermark_event_id: SStr
    clock_ms: SInt
    period: Literal[1, 2]
    score: Score
    # event_ids of goals counted in `score` (initial_score goals have none)
    goal_event_ids: tuple[str, ...]
    last_event: MatchEvent
    synthetic: Literal[True] = True


class EventPage(BaseModel):
    model_config = _FROZEN
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    match_id: SStr
    snapshot_id: SStr
    events: tuple[MatchEvent, ...]
    synthetic: Literal[True] = True


class MetricName(StrEnum):
    passes_attempted = "passes_attempted"
    passes_completed = "passes_completed"
    pass_completion = "pass_completion"  # ratio 0..1; None when no attempts
    pressures = "pressures"
    pressures_opp_half = "pressures_opp_half"  # pressures located in the opponent's half
    ball_wins = "ball_wins"  # tackle won + interception + ball_recovery
    high_ball_wins = "high_ball_wins"  # ball wins in the opponent half
    shots = "shots"
    goals = "goals"


class MetricValue(BaseModel):
    model_config = _FROZEN
    name: MetricName
    team_id: SStr
    value: float | None  # None = undefined (e.g. ratio with zero denominator), never 0
    unit: Literal["count", "ratio"]
    numerator: SInt | None = None  # set for ratios
    denominator: SInt | None = None  # set for ratios
    definition_version: Literal["metrics-v1"] = "metrics-v1"
    event_ids: tuple[str, ...]  # events the value was computed from


class WindowMetrics(BaseModel):
    model_config = _FROZEN
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    match_id: SStr
    snapshot_id: SStr
    window_start_ms: SInt  # exclusive
    window_end_ms: SInt  # inclusive, = clock of the watermark event
    metrics: tuple[MetricValue, ...]  # every MetricName for every team
    synthetic: Literal[True] = True


class CardKind(StrEnum):
    goal = "goal"
    press_surge = "press_surge"


class Card(BaseModel):
    """A deterministic template card. Later the agent pipeline produces cards of
    the same shape; until then text comes only from fixed templates + metrics."""

    model_config = _FROZEN
    card_id: SStr  # stable: "<kind>@<trigger_seq>"
    kind: CardKind
    template_id: Literal["fact-card"] = "fact-card"
    title: SStr
    body: SStr
    trigger_seq: SInt  # watermark at which the card became true
    trigger_clock_ms: SInt
    expires_at_ms: SInt  # hide the card once the replay clock passes this
    metrics: tuple[MetricValue, ...]  # values quoted in body, verbatim
    evidence_event_ids: tuple[str, ...]  # every event the card relies on
    origin: Literal["template"] = "template"


class CardList(BaseModel):
    model_config = _FROZEN
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    match_id: SStr
    snapshot_id: SStr
    cards: tuple[Card, ...]  # trigger_seq <= watermark, ordered by trigger_seq
    synthetic: Literal[True] = True
