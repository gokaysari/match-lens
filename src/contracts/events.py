"""Match Lens event contract, schema_version 1.0.

Coordinate system (all events, all teams):
  * units are metres on a 105 x 68 pitch (x in [0, 105], y in [0, 68]);
  * origin is the bottom-left corner of the pitch;
  * coordinates are normalised per team: the HOME team always attacks toward
    x=105 and the AWAY team always attacks toward x=0, in both periods
    (there is no side switch at half time).

Time: `event_time_ms` is the match clock in milliseconds (it keeps counting
across periods, so period 2 starts at 2_700_000), `sequence` is a strictly
increasing ordering key (gaps allowed). Missing values stay `None`.
All data is synthetic (`synthetic` is always True).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

_X = Field(default=None, ge=0.0, le=PITCH_LENGTH_M)
_Y = Field(default=None, ge=0.0, le=PITCH_WIDTH_M)


class MatchEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    match_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    period: Literal[1, 2]
    event_time_ms: int = Field(ge=0)
    team_id: str = Field(min_length=1)
    player_id: str | None = None
    type: EventType
    outcome: Outcome | None = None
    x: float = Field(ge=0.0, le=PITCH_LENGTH_M)
    y: float = Field(ge=0.0, le=PITCH_WIDTH_M)
    end_x: float | None = _X
    end_y: float | None = _Y
    scenario_seed: int
    synthetic: Literal[True]

    @model_validator(mode="after")
    def _check_type_rules(self) -> MatchEvent:
        if (self.end_x is not None or self.end_y is not None) and self.type not in END_COORD_TYPES:
            raise ValueError(f"end coordinates are not allowed for type '{self.type.value}'")
        if self.outcome is not None and self.outcome not in VALID_OUTCOMES.get(self.type, frozenset()):
            raise ValueError(
                f"outcome '{self.outcome.value}' is not valid for type '{self.type.value}'"
            )
        return self


class Team(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    side: Literal["home", "away"]


class Player(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    shirt_number: int = Field(ge=1, le=99)


class KeyMoment(BaseModel):
    """A scripted key moment, addressed by an inclusive event_id range."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    description: str = Field(min_length=1)
    first_event_id: str = Field(min_length=1)
    last_event_id: str = Field(min_length=1)


class ScenarioMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    match_id: str = Field(min_length=1)
    scenario_seed: int
    title: str = Field(min_length=1)
    teams: list[Team]
    players: list[Player]
    moments: list[KeyMoment]
    synthetic: Literal[True]
