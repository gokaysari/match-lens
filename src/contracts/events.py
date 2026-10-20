"""Match Lens event contract, schema_version 1.0.

Coordinate system (all events, all teams):
  * units are metres on a 105 x 68 pitch (x in [0, 105], y in [0, 68]);
  * origin is the bottom-left corner of the pitch;
  * a single fixed frame is used for the whole match: the HOME team always
    attacks toward x=105 and the AWAY team always attacks toward x=0, in both
    periods (there is no side switch at half time, nothing is mirrored per team).

Time: `event_time_ms` is the match clock in milliseconds (it keeps counting
across periods, so period 2 starts at 2_700_000), `sequence` is a strictly
increasing ordering key (gaps allowed). Missing values stay `None`.
All data is synthetic (`synthetic` is always True).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0


class EventType(StrEnum):
    kick_off = "kick_off"
    pass_ = "pass"
    carry = "carry"
    dribble = "dribble"
    pressure = "pressure"
    tackle = "tackle"
    interception = "interception"
    ball_recovery = "ball_recovery"
    clearance = "clearance"
    shot = "shot"
    foul = "foul"
    out_of_play = "out_of_play"
    substitution = "substitution"


class Outcome(StrEnum):
    complete = "complete"
    incomplete = "incomplete"
    won = "won"
    lost = "lost"
    saved = "saved"
    blocked = "blocked"
    off_target = "off_target"
    goal = "goal"


# Outcomes valid per event type. Types not listed take no outcome.
VALID_OUTCOMES: dict[EventType, frozenset[Outcome]] = {
    EventType.pass_: frozenset({Outcome.complete, Outcome.incomplete}),
    EventType.carry: frozenset({Outcome.complete, Outcome.incomplete}),
    EventType.dribble: frozenset({Outcome.won, Outcome.lost}),
    EventType.tackle: frozenset({Outcome.won, Outcome.lost}),
    EventType.shot: frozenset(
        {Outcome.saved, Outcome.blocked, Outcome.off_target, Outcome.goal}
    ),
}

END_COORD_TYPES = frozenset({EventType.pass_, EventType.carry, EventType.shot})

# Strict scalar types: no str->number coercion, no float->int, no bool->int.
SInt = Annotated[int, Field(strict=True)]
SStr = Annotated[str, Field(strict=True, min_length=1)]
XCoord = Annotated[float, Field(strict=True, ge=0.0, le=PITCH_LENGTH_M)]
YCoord = Annotated[float, Field(strict=True, ge=0.0, le=PITCH_WIDTH_M)]

ON_BALL_TYPES = frozenset({
    EventType.pass_, EventType.carry, EventType.dribble, EventType.shot, EventType.kick_off,
    EventType.clearance, EventType.interception, EventType.ball_recovery, EventType.tackle,
})


class MatchEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    match_id: SStr
    event_id: SStr
    sequence: Annotated[int, Field(strict=True, ge=1)]
    period: Annotated[int, Field(strict=True, ge=1, le=2)]
    event_time_ms: Annotated[int, Field(strict=True, ge=0)]
    team_id: SStr
    player_id: SStr | None = None
    # Required for on-ball types; a new id each time possession changes or play restarts.
    possession_id: SStr | None = None
    # Pass only: intended receiver (required when complete; a teammate, never the passer).
    recipient_player_id: SStr | None = None
    # Pressure only: the opponent being pressured.
    pressured_player_id: SStr | None = None
    type: EventType
    outcome: Outcome | None = None
    # x/y are required except for substitution, which has no coordinates at all.
    x: XCoord | None = None
    y: YCoord | None = None
    end_x: XCoord | None = None
    end_y: YCoord | None = None
    scenario_seed: SInt
    synthetic: Literal[True]

    @field_validator("synthetic", mode="before")
    @classmethod
    def _strict_bool(cls, v: object) -> object:
        if type(v) is not bool:
            raise ValueError("synthetic must be the boolean true")
        return v

    @model_validator(mode="after")
    def _check_type_rules(self) -> MatchEvent:
        t = self.type
        if t == EventType.substitution:
            if any(v is not None for v in (self.x, self.y, self.end_x, self.end_y)):
                raise ValueError("substitution has no coordinates")
        elif self.x is None or self.y is None:
            raise ValueError(f"x and y are required for type '{t.value}'")
        if (self.end_x is None) != (self.end_y is None):
            raise ValueError("end_x and end_y must be both set or both None")
        if (self.end_x is not None or self.end_y is not None) and t not in END_COORD_TYPES:
            raise ValueError(f"end coordinates are not allowed for type '{t.value}'")
        if self.outcome is not None and self.outcome not in VALID_OUTCOMES.get(t, frozenset()):
            raise ValueError(f"outcome '{self.outcome.value}' is not valid for type '{t.value}'")
        if t in ON_BALL_TYPES and self.possession_id is None:
            raise ValueError(f"possession_id is required for type '{t.value}'")
        if self.recipient_player_id is not None:
            if t != EventType.pass_:
                raise ValueError("recipient_player_id is only allowed on pass")
            if self.recipient_player_id == self.player_id:
                raise ValueError("recipient_player_id must differ from player_id")
        elif t == EventType.pass_ and self.outcome == Outcome.complete:
            raise ValueError("recipient_player_id is required for a complete pass")
        if self.pressured_player_id is not None and t != EventType.pressure:
            raise ValueError("pressured_player_id is only allowed on pressure")
        return self


class Team(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: SStr
    name: SStr
    side: Literal["home", "away"]


class Player(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: SStr
    team_id: SStr
    name: SStr
    shirt_number: Annotated[int, Field(strict=True, ge=1, le=99)]


class KeyMoment(BaseModel):
    """A scripted key moment, addressed by an inclusive event_id range."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: SStr
    description: SStr
    first_event_id: SStr
    last_event_id: SStr


class Score(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    home: Annotated[int, Field(strict=True, ge=0)]
    away: Annotated[int, Field(strict=True, ge=0)]


class ScenarioMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    match_id: SStr
    scenario_seed: SInt
    title: SStr
    teams: list[Team]
    players: list[Player]
    moments: list[KeyMoment]
    initial_score: Score
    segment_start_ms: Annotated[int, Field(strict=True, ge=0)]
    segment_end_ms: Annotated[int, Field(strict=True, ge=0)]
    synthetic: Literal[True]

    @field_validator("synthetic", mode="before")
    @classmethod
    def _strict_bool(cls, v: object) -> object:
        if type(v) is not bool:
            raise ValueError("synthetic must be the boolean true")
        return v

    @model_validator(mode="after")
    def _check_segment(self) -> ScenarioMeta:
        if self.segment_end_ms <= self.segment_start_ms:
            raise ValueError("segment_end_ms must be greater than segment_start_ms")
        return self
