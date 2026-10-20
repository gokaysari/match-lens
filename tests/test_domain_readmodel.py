"""Snapshot, window metrics and template cards (pure, deterministic)."""

import pytest
from conftest import SCENARIO_DIR, base_event, base_meta

from contracts.api import CardKind, MetricName
from contracts.events import MatchEvent, ScenarioMeta
from domain.cards import (
    GOAL_CARD_TTL_MS,
    PRESS_COOLDOWN_MS,
    PRESS_MIN_PRESSURES,
    PRESS_SURGE_TTL_MS,
    compute_cards,
)
from domain.errors import DomainError
from domain.ingest import load_scenario
from domain.metrics import compute_window_metrics
from domain.snapshot import build_snapshot, require_visible


@pytest.fixture(scope="module")
def synth():
    return load_scenario(SCENARIO_DIR)


def seq_of(events, eid):
    return next(e.sequence for e in events if e.event_id == eid)


def ev(n, clock, team="nbr", type_="pass", outcome="complete", x=50.0, **kw):
    over = dict(event_id=f"e{n}", sequence=n, event_time_ms=clock, team_id=team, type=type_,
                outcome=outcome, x=x, y=30.0, end_x=None, end_y=None, recipient_player_id=None,
                possession_id=f"p{n}")
    if team == "nbr":
        over["player_id"] = "nbr-07"
        if type_ == "pass" and outcome == "complete":
            over["recipient_player_id"] = "nbr-04"
    else:
        over["player_id"] = "hba-04"
        if type_ == "pass" and outcome == "complete":
            over["recipient_player_id"] = "hba-09"
    over.update(kw)
    return MatchEvent.model_validate(base_event(**over))


META = ScenarioMeta.model_validate(base_meta(initial_score={"home": 1, "away": 0}))


def metric(wm, name, team):
    return next(m for m in wm.metrics if m.name == name and m.team_id == team)


# ---- snapshot -------------------------------------------------------------

def test_snapshot_score_before_and_after_goal(synth):
    meta, events = synth
    goal_seq = seq_of(events, "e066")
    before = build_snapshot(meta, events, goal_seq - 1)
    after = build_snapshot(meta, events, goal_seq)
    assert (before.score.home, before.score.away) == (0, 0)
    assert before.goal_event_ids == ()
    assert (after.score.home, after.score.away) == (0, 1)
    assert after.goal_event_ids == ("e066",)
    assert after.snapshot_id == f"synthetic-01@{goal_seq}"
    assert after.watermark_event_id == "e066"
    assert after.last_event.event_id == "e066"
    assert after.clock_ms == 3608460 and after.period == 2
    assert after.synthetic is True


def test_snapshot_initial_score_added():
    snap = build_snapshot(META, [ev(1, 0)], 1)
    assert (snap.score.home, snap.score.away) == (1, 0)
    assert snap.goal_event_ids == ()


def test_snapshot_goal_credited_to_shooter_team():
    g = ev(2, 1000, team="hba", type_="shot", outcome="goal")
    snap = build_snapshot(META, [ev(1, 0), g], 2)
    assert (snap.score.home, snap.score.away) == (1, 1)


def test_unknown_sequence():
    with pytest.raises(DomainError) as ei:
        build_snapshot(META, [ev(1, 0), ev(3, 10)], 2)
    assert ei.value.code == "UNKNOWN_SEQUENCE"


def test_require_visible_forbids_future_event():
    events = [ev(1, 0), ev(2, 10)]
    assert require_visible(events, "e1", 1).event_id == "e1"
    with pytest.raises(DomainError) as ei:
        require_visible(events, "e2", 1)
    assert ei.value.code == "FUTURE_EVENT_FORBIDDEN"
    with pytest.raises(DomainError) as ei:
        require_visible(events, "nope", 2)
    assert ei.value.code == "UNKNOWN_EVENT"


def test_watermark_exclusion_everywhere(synth):
    meta, events = synth
    w = seq_of(events, "e066") - 1
    future = {e.event_id for e in events if e.sequence > w}
    snap = build_snapshot(meta, events, w)
    assert snap.last_event.sequence <= w
    wm = compute_window_metrics(meta, events, w)
    cards = compute_cards(meta, events, w)
    used = {i for m in wm.metrics for i in m.event_ids}
    for c in cards.cards:
        assert c.trigger_seq <= w
        used |= set(c.evidence_event_ids)
        for m in c.metrics:
            used |= set(m.event_ids)
    assert not used & future
    assert not any(c.kind == CardKind.goal for c in cards.cards)


# ---- metrics --------------------------------------------------------------

def test_metrics_tiny_hand_built():
    events = [
        ev(1, 1000),                                   # nbr pass complete
        ev(2, 2000, outcome="incomplete"),              # nbr pass incomplete
        ev(3, 3000, team="hba", type_="pressure", x=60.0, player_id="hba-04",
           pressured_player_id="nbr-07", outcome=None, possession_id=None),
        ev(4, 4000, type_="tackle", outcome="won", x=60.0),        # nbr high win
        ev(5, 5000, type_="interception", outcome=None, x=40.0),    # nbr, own half
        ev(6, 6000, team="hba", type_="ball_recovery", outcome=None, x=40.0),  # hba high
        ev(7, 7000, team="hba", type_="tackle", outcome="won", x=60.0),        # hba not high
        ev(8, 8000, team="hba", type_="ball_recovery", outcome=None, x=52.5),  # boundary no
        ev(9, 9000, type_="tackle", outcome="lost", x=70.0),                    # not a win
        ev(10, 10000, type_="shot", outcome="goal", x=90.0),
    ]
    wm = compute_window_metrics(META, events, 10)
    assert [m.team_id for m in wm.metrics] == ["nbr"] * 8 + ["hba"] * 8
    assert [m.name for m in wm.metrics[:8]] == list(MetricName)
    n = lambda name, t="nbr": metric(wm, name, t)  # noqa: E731
    assert n(MetricName.passes_attempted).value == 2
    assert n(MetricName.passes_attempted).event_ids == ("e1", "e2")
    assert n(MetricName.passes_completed).event_ids == ("e1",)
    pc = n(MetricName.pass_completion)
    assert pc.value == 0.5 and (pc.numerator, pc.denominator) == (1, 2) and pc.unit == "ratio"
    assert pc.event_ids == ("e1", "e2")
    assert n(MetricName.ball_wins).event_ids == ("e4", "e5")
    assert n(MetricName.high_ball_wins).event_ids == ("e4",)
    assert n(MetricName.shots).value == 1 and n(MetricName.goals).event_ids == ("e10",)
    assert n(MetricName.pressures).value == 0 and n(MetricName.pressures).unit == "count"
    assert n(MetricName.pressures, "hba").event_ids == ("e3",)
    assert n(MetricName.ball_wins, "hba").event_ids == ("e6", "e7", "e8")
    assert n(MetricName.high_ball_wins, "hba").event_ids == ("e6",)
    hpc = n(MetricName.pass_completion, "hba")
    assert hpc.value is None and hpc.numerator == 0 and hpc.denominator == 0
    assert hpc.event_ids == ()
    assert all(m.definition_version == "metrics-v1" for m in wm.metrics)
    assert wm.snapshot_id == "m1@10" and wm.window_end_ms == 10000
    assert wm.window_start_ms == 10000 - 60000


def test_window_boundary_exclusive_start_inclusive_end():
    events = [ev(1, 40_000), ev(2, 50_000), ev(3, 100_000)]
    wm = compute_window_metrics(META, events, 3, window_s=60)
    assert wm.window_start_ms == 40_000 and wm.window_end_ms == 100_000
    assert metric(wm, MetricName.passes_attempted, "nbr").event_ids == ("e2", "e3")


@pytest.mark.parametrize("w", [9, 601, 0, -5])
def test_window_s_out_of_range(w):
    with pytest.raises(DomainError) as ei:
        compute_window_metrics(META, [ev(1, 0)], 1, window_s=w)
    assert ei.value.code == "INVALID_WINDOW"


def test_metrics_reject_missing_x_not_high():
    # shot/clearance etc fine; a win without x cannot be built (x required), so just check
    # that high_ball_wins is a subset of ball_wins on real data
    meta, events = load_scenario(SCENARIO_DIR)
    wm = compute_window_metrics(meta, events, events[-1].sequence, window_s=600)
    for t in ("nbr", "hba"):
        assert set(metric(wm, MetricName.high_ball_wins, t).event_ids) <= set(
            metric(wm, MetricName.ball_wins, t).event_ids)


# ---- cards ----------------------------------------------------------------

def test_cards_synthetic_01(synth):
    meta, events = synth
    last = events[-1].sequence
    cards = compute_cards(meta, events, last).cards
    goals = [c for c in cards if c.kind == CardKind.goal]
    presses = [c for c in cards if c.kind == CardKind.press_surge]
    g_seq = seq_of(events, "e066")
    assert [c.trigger_seq for c in goals] == [g_seq]
    assert goals[0].card_id == f"goal@{g_seq}"
    assert goals[0].title == "Goal - Harbour Athletic"
    assert goals[0].body == "Harbour Athletic score at 60:08. Northbridge FC 0-1 Harbour Athletic."
    assert goals[0].expires_at_ms == 3608460 + GOAL_CARD_TTL_MS
    assert goals[0].metrics == ()
    assert goals[0].evidence_event_ids[-1] == "e066"
    by_id = {e.event_id: e for e in events}
    assert {by_id[i].possession_id for i in goals[0].evidence_event_ids} == {"p10"}
    assert len(presses) == 1 and presses[0].title == "Harbour Athletic press high"
    moment_b = next(m for m in meta.moments if m.key == "b")
    lo, hi = seq_of(events, moment_b.first_event_id), seq_of(events, moment_b.last_event_id)
    assert lo <= presses[0].trigger_seq <= hi
    assert presses[0].expires_at_ms == presses[0].trigger_clock_ms + PRESS_SURGE_TTL_MS
    assert [c.trigger_seq for c in cards] == sorted(c.trigger_seq for c in cards)
    assert not any("Northbridge" in c.title for c in presses)
    print([(c.card_id, c.title, c.body) for c in cards])


def test_card_stability_and_evidence_resolution(synth):
    meta, events = synth
    last = events[-1].sequence
    full = compute_cards(meta, events, last).cards
    seq_by_id = {e.event_id: e.sequence for e in events}
    for c in full:
        at_trigger = compute_cards(meta, events, c.trigger_seq).cards
        assert c in at_trigger
        assert at_trigger == tuple(x for x in full if x.trigger_seq <= c.trigger_seq)
        assert c.evidence_event_ids
        for i in c.evidence_event_ids:
            assert seq_by_id[i] <= c.trigger_seq
        for m in c.metrics:
            assert set(m.event_ids) <= set(c.evidence_event_ids)
        assert [seq_by_id[i] for i in c.evidence_event_ids] == sorted(seq_by_id[i] for i in c.evidence_event_ids)


def test_press_body_numbers_equal_metric_values(synth):
    meta, events = synth
    card = next(c for c in compute_cards(meta, events, events[-1].sequence).cards
                if c.kind == CardKind.press_surge)
    pressures = next(m for m in card.metrics if m.name == MetricName.pressures)
    pc = next(m for m in card.metrics if m.name == MetricName.pass_completion)
    assert pressures.team_id == "hba" and pc.team_id == "nbr"
    assert pressures.value >= PRESS_MIN_PRESSURES
    by_id = {e.event_id: e for e in events}
    assert all(by_id[i].type == "pressure" and by_id[i].x < 52.5 for i in pressures.event_ids)
    assert card.body == (
        f"Harbour Athletic pressed {int(pressures.value)} times in Northbridge FC's half in the "
        f"last 60 s. Northbridge FC completed {pc.numerator} of {pc.denominator} passes."
    )
    assert set(card.evidence_event_ids) == set(pressures.event_ids) | set(pc.event_ids)


def _pressure(n, clock, team="hba", x=20.0):
    return ev(n, clock, team=team, type_="pressure", outcome=None, x=x, possession_id=None,
              pressured_player_id="nbr-07" if team == "hba" else "hba-04")


def test_press_surge_trigger_and_cooldown():
    meta = ScenarioMeta.model_validate(base_meta(initial_score={"home": 0, "away": 0}))
    events, n = [], 0
    # nbr completes 2 of 5 passes, then 10 hba pressures in nbr's half
    for i in range(5):
        n += 1
        events.append(ev(n, 1000 * n, outcome="complete" if i < 2 else "incomplete"))
    for _ in range(10):
        n += 1
        events.append(_pressure(n, 1000 * n))
    cards = compute_cards(meta, events, n).cards
    assert [c.card_id for c in cards] == ["press_surge@15"]
    # still holding after trigger: cooldown suppresses a repeat
    for _ in range(3):
        n += 1
        events.append(_pressure(n, 1000 * n))
    assert [c.card_id for c in compute_cards(meta, events, n).cards] == ["press_surge@15"]
    # after cooldown, window refreshed with pressures + failed passes -> second card
    t0 = events[-1].event_time_ms
    for k in range(5):
        n += 1
        events.append(ev(n, 15_000 + PRESS_COOLDOWN_MS + 5000 + 10 * k, outcome="incomplete"))
    base = events[-1].event_time_ms
    for k in range(10):
        n += 1
        events.append(_pressure(n, base + 100 * (k + 1)))
    ids = [c.card_id for c in compute_cards(meta, events, n).cards]
    assert ids[0] == "press_surge@15" and len(ids) == 2 and t0 < base


def test_press_surge_needs_five_attempts_and_low_completion():
    meta = ScenarioMeta.model_validate(base_meta(initial_score={"home": 0, "away": 0}))
    events = [ev(i, 1000 * i, outcome="incomplete") for i in range(1, 5)]  # only 4 attempts
    events += [_pressure(4 + i, 5000 + 1000 * i) for i in range(1, 11)]
    assert compute_cards(meta, events, events[-1].sequence).cards == ()
    # 5 attempts but 4 complete (0.8) -> no card
    events = [ev(i, 1000 * i, outcome="incomplete" if i == 1 else "complete") for i in range(1, 6)]
    events += [_pressure(5 + i, 6000 + 1000 * i) for i in range(1, 11)]
    assert compute_cards(meta, events, events[-1].sequence).cards == ()


def test_press_surge_ignores_pressures_in_own_half():
    meta = ScenarioMeta.model_validate(base_meta(initial_score={"home": 0, "away": 0}))
    events = [ev(i, 1000 * i, outcome="incomplete") for i in range(1, 6)]
    events += [_pressure(5 + i, 6000 + 1000 * i, x=80.0) for i in range(1, 11)]
    assert compute_cards(meta, events, events[-1].sequence).cards == ()
