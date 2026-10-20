"""Snapshot: match state after the event at the watermark sequence. Pure functions."""

from __future__ import annotations

from collections.abc import Sequence

from contracts.api import Snapshot
from contracts.events import MatchEvent, Outcome, ScenarioMeta, Score, EventType
from domain.errors import DomainError


def snapshot_id(meta: ScenarioMeta, watermark_seq: int) -> str:
    return f"{meta.match_id}@{watermark_seq}"


def visible_events(events: Sequence[MatchEvent], watermark_seq: int) -> list[MatchEvent]:
    """Events with sequence <= watermark. The watermark must be an existing sequence."""
    if not any(e.sequence == watermark_seq for e in events):
        raise DomainError("UNKNOWN_SEQUENCE", f"no event with sequence {watermark_seq}")
    return [e for e in events if e.sequence <= watermark_seq]


def require_visible(events: Sequence[MatchEvent], event_id: str, watermark_seq: int) -> MatchEvent:
    """Read one event by id; refuses anything after the watermark."""
    found = next((e for e in events if e.event_id == event_id), None)
    if found is None:
        raise DomainError("UNKNOWN_EVENT", f"no event {event_id}")
    if found.sequence > watermark_seq:
        raise DomainError("FUTURE_EVENT_FORBIDDEN", f"{event_id} is after watermark {watermark_seq}")
    return found


def is_goal(e: MatchEvent) -> bool:
    return e.type == EventType.shot and e.outcome == Outcome.goal


def score_after(meta: ScenarioMeta, visible: Sequence[MatchEvent]) -> tuple[Score, tuple[str, ...]]:
    home_id = next(t.id for t in meta.teams if t.side == "home")
    goals = [e for e in visible if is_goal(e)]
    home = meta.initial_score.home + sum(1 for g in goals if g.team_id == home_id)
    away = meta.initial_score.away + sum(1 for g in goals if g.team_id != home_id)
    return Score(home=home, away=away), tuple(g.event_id for g in goals)


def build_snapshot(meta: ScenarioMeta, events: Sequence[MatchEvent], watermark_seq: int) -> Snapshot:
    vis = visible_events(events, watermark_seq)
    last = vis[-1]
    score, goal_ids = score_after(meta, vis)
    return Snapshot(
        match_id=meta.match_id,
        snapshot_id=snapshot_id(meta, watermark_seq),
        watermark_seq=watermark_seq,
        watermark_event_id=last.event_id,
        clock_ms=last.event_time_ms,
        period=last.period,
        score=score,
        goal_event_ids=goal_ids,
        last_event=last,
    )
