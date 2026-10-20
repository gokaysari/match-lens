"""Deterministic template cards, evaluated at every sequence up to the watermark so the
result never depends on which watermark is queried."""

from __future__ import annotations

from collections.abc import Sequence

from contracts.api import Card, CardKind, CardList, MetricName
from contracts.events import EventType, MatchEvent, ScenarioMeta
from domain.metrics import team_metrics, window_events
from domain.snapshot import is_goal, score_after, snapshot_id, visible_events

GOAL_CARD_TTL_MS = 60_000
PRESS_SURGE_TTL_MS = 45_000
PRESS_WINDOW_S = 60
PRESS_MIN_PRESSURES = 10
# opponent pass completion <= 3/5 (0.6), compared with integers: n * DEN <= d * NUM
PRESS_MAX_OPP_COMPLETION_NUM, PRESS_MAX_OPP_COMPLETION_DEN = 3, 5
PRESS_MIN_OPP_PASS_ATTEMPTS = 5
PRESS_COOLDOWN_MS = 120_000


def fmt_clock(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def _goal_card(meta: ScenarioMeta, vis: Sequence[MatchEvent], goal: MatchEvent) -> Card:
    team = next(t for t in meta.teams if t.id == goal.team_id)
    home = next(t for t in meta.teams if t.side == "home")
    away = next(t for t in meta.teams if t.side == "away")
    score, _ = score_after(meta, vis)
    earlier = {e.event_id for e in vis if is_goal(e) and e.sequence < goal.sequence}
    evidence = tuple(e.event_id for e in vis
                     if e.possession_id == goal.possession_id or e.event_id in earlier)
    return Card(
        card_id=f"{CardKind.goal.value}@{goal.sequence}", kind=CardKind.goal,
        title=f"Goal - {team.name}",
        body=(f"{team.name} score at {fmt_clock(goal.event_time_ms)}. "
              f"{home.name} {score.home}-{score.away} {away.name}."),
        trigger_seq=goal.sequence, trigger_clock_ms=goal.event_time_ms,
        expires_at_ms=goal.event_time_ms + GOAL_CARD_TTL_MS,
        metrics=(), evidence_event_ids=evidence,
    )


def _press_card(vis: Sequence[MatchEvent], pressing, opp) -> Card | None:
    """vis ends at the candidate trigger event. Returns the card if the condition holds."""
    last = vis[-1]
    _, _, win = window_events(vis, PRESS_WINDOW_S)
    pressures = next(m for m in team_metrics(pressing.id, pressing.side, win)
                     if m.name == MetricName.pressures_opp_half)
    if pressures.value < PRESS_MIN_PRESSURES:
        return None
    pc = next(m for m in team_metrics(opp.id, opp.side, win) if m.name == MetricName.pass_completion)
    if pc.denominator < PRESS_MIN_OPP_PASS_ATTEMPTS or (
        pc.numerator * PRESS_MAX_OPP_COMPLETION_DEN > pc.denominator * PRESS_MAX_OPP_COMPLETION_NUM
    ):
        return None
    seq_of = {e.event_id: e.sequence for e in vis}
    evidence = tuple(sorted(set(pressures.event_ids) | set(pc.event_ids), key=seq_of.__getitem__))
    return Card(
        card_id=f"{CardKind.press_surge.value}@{last.sequence}", kind=CardKind.press_surge,
        title=f"{pressing.name} press high",
        body=(f"{pressing.name} pressed {int(pressures.value)} times in {opp.name}'s half in the "
              f"last {PRESS_WINDOW_S} s. {opp.name} completed {pc.numerator} of {pc.denominator} passes."),
        trigger_seq=last.sequence, trigger_clock_ms=last.event_time_ms,
        expires_at_ms=last.event_time_ms + PRESS_SURGE_TTL_MS,
        metrics=(pressures, pc), evidence_event_ids=evidence,
    )


def compute_cards(meta: ScenarioMeta, events: Sequence[MatchEvent], watermark_seq: int) -> CardList:
    vis = visible_events(events, watermark_seq)
    cards: list[Card] = []
    last_press_clock: dict[str, int] = {}
    armed: dict[str, bool] = {}  # False after a trigger until the condition was seen false
    for i, e in enumerate(vis):
        prefix = vis[: i + 1]
        if is_goal(e):
            cards.append(_goal_card(meta, prefix, e))
        for pressing in meta.teams:
            opp = next(t for t in meta.teams if t.id != pressing.id)
            card = _press_card(prefix, pressing, opp)
            if card is None:
                armed[pressing.id] = True
                continue
            prev = last_press_clock.get(pressing.id)
            if prev is not None and (
                not armed.get(pressing.id, True) or e.event_time_ms < prev + PRESS_COOLDOWN_MS
            ):
                continue
            cards.append(card)
            last_press_clock[pressing.id] = e.event_time_ms
            armed[pressing.id] = False
    return CardList(match_id=meta.match_id, snapshot_id=snapshot_id(meta, watermark_seq),
                    cards=tuple(cards))
