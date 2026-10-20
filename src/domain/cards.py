"""Deterministic template cards, evaluated at every sequence up to the watermark so the
result never depends on which watermark is queried."""

from __future__ import annotations

from collections.abc import Sequence

from contracts.api import Card, CardKind, CardList, MetricName, MetricValue
from contracts.events import EventType, MatchEvent, ScenarioMeta
from domain.metrics import in_half_of_opponent, team_metrics, window_events
from domain.snapshot import is_goal, score_after, snapshot_id, visible_events

GOAL_CARD_TTL_MS = 60_000
PRESS_SURGE_TTL_MS = 45_000
PRESS_WINDOW_S = 60
PRESS_MIN_PRESSURES = 10
PRESS_MAX_OPP_PASS_COMPLETION = 0.6
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
    evidence = tuple(e.event_id for e in vis if e.possession_id == goal.possession_id)
    return Card(
        card_id=f"{CardKind.goal.value}@{goal.sequence}", kind=CardKind.goal,
        title=f"Goal - {team.name}",
        body=(f"{team.name} score at {fmt_clock(goal.event_time_ms)}. "
              f"{home.name} {score.home}-{score.away} {away.name}."),
        trigger_seq=goal.sequence, trigger_clock_ms=goal.event_time_ms,
        expires_at_ms=goal.event_time_ms + GOAL_CARD_TTL_MS,
        metrics=(), evidence_event_ids=evidence,
    )


def _press_card(meta: ScenarioMeta, vis: Sequence[MatchEvent], pressing, opp) -> Card | None:
    """vis ends at the candidate trigger event. Returns the card if the condition holds."""
    last = vis[-1]
    _, _, win = window_events(vis, PRESS_WINDOW_S)
    press = [e for e in win if e.team_id == pressing.id and e.type == EventType.pressure
             and in_half_of_opponent(pressing.side, e.x)]
    if len(press) < PRESS_MIN_PRESSURES:
        return None
    pc = next(m for m in team_metrics(opp.id, opp.side, win) if m.name == MetricName.pass_completion)
    if (pc.denominator or 0) < PRESS_MIN_OPP_PASS_ATTEMPTS or pc.value is None \
            or pc.value > PRESS_MAX_OPP_PASS_COMPLETION:
        return None
    pressures = MetricValue(name=MetricName.pressures, team_id=pressing.id, value=float(len(press)),
                            unit="count", event_ids=tuple(e.event_id for e in press))
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
    for i, e in enumerate(vis):
        prefix = vis[: i + 1]
        if is_goal(e):
            cards.append(_goal_card(meta, prefix, e))
        for pressing in meta.teams:
            prev = last_press_clock.get(pressing.id)
            if prev is not None and e.event_time_ms < prev + PRESS_COOLDOWN_MS:
                continue
            opp = next(t for t in meta.teams if t.id != pressing.id)
            card = _press_card(meta, prefix, pressing, opp)
            if card is not None:
                cards.append(card)
                last_press_clock[pressing.id] = e.event_time_ms
    return CardList(match_id=meta.match_id, snapshot_id=snapshot_id(meta, watermark_seq),
                    cards=tuple(cards))
