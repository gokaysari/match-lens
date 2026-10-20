"""Window metrics, definition metrics-v1. Pure functions."""

from __future__ import annotations

from collections.abc import Sequence

from contracts.api import MetricName, MetricValue, WindowMetrics
from contracts.events import EventType, MatchEvent, Outcome, ScenarioMeta
from domain.errors import DomainError
from domain.snapshot import snapshot_id, visible_events

HALFWAY_X = 52.5
WINDOW_S_MIN, WINDOW_S_MAX, WINDOW_S_DEFAULT = 10, 600, 60


def in_half_of_opponent(side: str, x: float | None) -> bool:
    """True if x is in the half the team attacks into (home: x > 52.5, away: x < 52.5)."""
    if x is None:
        return False
    return x > HALFWAY_X if side == "home" else x < HALFWAY_X


def is_ball_win(e: MatchEvent) -> bool:
    return e.type in (EventType.interception, EventType.ball_recovery) or (
        e.type == EventType.tackle and e.outcome == Outcome.won
    )


def _count(name: MetricName, team_id: str, evs: Sequence[MatchEvent]) -> MetricValue:
    return MetricValue(name=name, team_id=team_id, value=float(len(evs)), unit="count",
                       event_ids=tuple(e.event_id for e in evs))


def window_events(visible: Sequence[MatchEvent], window_s: int) -> tuple[int, int, list[MatchEvent]]:
    end = visible[-1].event_time_ms
    start = end - window_s * 1000
    return start, end, [e for e in visible
                 if e.period == visible[-1].period and start < e.event_time_ms <= end]


def team_metrics(team_id: str, side: str, win: Sequence[MatchEvent]) -> list[MetricValue]:
    mine = [e for e in win if e.team_id == team_id]
    passes = [e for e in mine if e.type == EventType.pass_]
    done = [e for e in passes if e.outcome == Outcome.complete]
    wins = [e for e in mine if is_ball_win(e)]
    ratio = MetricValue(
        name=MetricName.pass_completion, team_id=team_id,
        value=(len(done) / len(passes)) if passes else None, unit="ratio",
        numerator=len(done), denominator=len(passes),
        event_ids=tuple(e.event_id for e in passes),
    )
    return [
        _count(MetricName.passes_attempted, team_id, passes),
        _count(MetricName.passes_completed, team_id, done),
        ratio,
        _count(MetricName.pressures, team_id, [e for e in mine if e.type == EventType.pressure]),
        _count(MetricName.pressures_opp_half, team_id,
               [e for e in mine if e.type == EventType.pressure and in_half_of_opponent(side, e.x)]),
        _count(MetricName.ball_wins, team_id, wins),
        _count(MetricName.high_ball_wins, team_id,
               [e for e in wins if in_half_of_opponent(side, e.x)]),
        _count(MetricName.shots, team_id, [e for e in mine if e.type == EventType.shot]),
        _count(MetricName.goals, team_id,
               [e for e in mine if e.type == EventType.shot and e.outcome == Outcome.goal]),
    ]


def compute_window_metrics(
    meta: ScenarioMeta, events: Sequence[MatchEvent], watermark_seq: int,
    window_s: int = WINDOW_S_DEFAULT,
) -> WindowMetrics:
    if isinstance(window_s, bool) or not isinstance(window_s, int) or not (
        WINDOW_S_MIN <= window_s <= WINDOW_S_MAX
    ):
        raise DomainError("INVALID_WINDOW", f"window_s must be an int in {WINDOW_S_MIN}..{WINDOW_S_MAX}")
    vis = visible_events(events, watermark_seq)
    start, end, win = window_events(vis, window_s)
    out: list[MetricValue] = []
    for t in meta.teams:
        out.extend(team_metrics(t.id, t.side, win))
    return WindowMetrics(match_id=meta.match_id, snapshot_id=snapshot_id(meta, watermark_seq),
                         window_start_ms=start, window_end_ms=end, metrics=tuple(out))
