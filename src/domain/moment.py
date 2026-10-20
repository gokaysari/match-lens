"""Deterministic computations about the moment a card is anchored on (windows,
possession of the trigger event). Pure functions; callers pass events already
restricted to the snapshot."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from contracts.events import ON_BALL_TYPES, PITCH_LENGTH_M, PITCH_WIDTH_M, MatchEvent


def events_in_window(vis: Sequence[MatchEvent], period: int, start_ms: int, end_ms: int) -> list[MatchEvent]:
    """Events of `period` with start_ms < event_time_ms <= end_ms (same rule as window metrics)."""
    return [e for e in vis if e.period == period and start_ms < e.event_time_ms <= end_ms]


def period_start_ms(vis: Sequence[MatchEvent], period: int) -> int | None:
    times = [e.event_time_ms for e in vis if e.period == period]
    return min(times) if times else None


def round_half_up(numerator: int, denominator: int) -> int:
    """round(numerator / denominator) for non-negative ints, halves up (no float error)."""
    return (2 * numerator + denominator) // (2 * denominator)


@dataclass(frozen=True)
class PossessionSummary:
    team_id: str
    event_ids: tuple[str, ...]  # on-ball events of the possession up to the trigger
    duration_ms: int  # first on-ball event -> trigger event
    start_dist_m: int  # metres from the goal the team attacks to where the possession began


def goal_distance_m(side: str, x: float, y: float) -> float:
    """Distance to the centre of the goal the team of `side` attacks (home -> x=105, away -> x=0)."""
    goal_x = PITCH_LENGTH_M if side == "home" else 0.0
    return math.hypot(x - goal_x, y - PITCH_WIDTH_M / 2)


def possession_summary(vis: Sequence[MatchEvent], trigger: MatchEvent,
                       side_of: dict[str, str]) -> PossessionSummary | None:
    """The possession of the trigger event (None when it has none or no on-ball event is known)."""
    pid = trigger.possession_id
    if pid is None:
        return None
    on_ball = [e for e in vis if e.possession_id == pid and e.type in ON_BALL_TYPES
               and e.sequence <= trigger.sequence]
    if not on_ball:
        return None
    first = on_ball[0]
    side = side_of.get(first.team_id)
    if side is None or first.x is None or first.y is None:
        return None
    dist = goal_distance_m(side, first.x, first.y)
    return PossessionSummary(
        team_id=first.team_id, event_ids=tuple(e.event_id for e in on_ball),
        duration_ms=trigger.event_time_ms - first.event_time_ms,
        start_dist_m=int(math.floor(dist + 0.5)),
    )
