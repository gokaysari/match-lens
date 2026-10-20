from collections import Counter

from conftest import SCENARIO_DIR, load_generator
from domain.ingest import load_scenario

FILES = ("meta.json", "events.jsonl")


def test_generator_matches_committed_bytes():
    rendered = load_generator().render()
    assert set(rendered) == set(FILES)
    for name in FILES:
        assert (SCENARIO_DIR / name).read_bytes() == rendered[name]


def test_generator_deterministic():
    g = load_generator()
    assert g.render() == g.render()


def test_generator_seed_changes_jitter_not_script():
    g = load_generator()
    other = g.render(seed=g.SEED + 1)
    assert other["events.jsonl"] != g.render()["events.jsonl"]


def test_scale_and_clock():
    meta, events = load_scenario(SCENARIO_DIR)
    assert 80 <= len(events) <= 140
    assert {e.period for e in events} == {2}
    start, end = events[0].event_time_ms, events[-1].event_time_ms
    assert 57 * 60_000 <= start <= 59 * 60_000
    assert 61 * 60_000 <= end <= 63 * 60_000
    assert meta.synthetic and all(e.synthetic for e in events)


def test_goal_is_unique_harbour_and_in_moment_c():
    meta, events = load_scenario(SCENARIO_DIR)
    goals = [e for e in events if e.outcome == "goal"]
    assert len(goals) == 1
    goal = goals[0]
    assert goal.team_id == "hba" and goal.type == "shot"
    ids = [e.event_id for e in events]
    c = next(m for m in meta.moments if m.key == "c")
    window = ids[ids.index(c.first_event_id): ids.index(c.last_event_id) + 1]
    assert goal.event_id in window and window[-1] == goal.event_id


def test_moment_c_is_fast_counter():
    meta, events = load_scenario(SCENARIO_DIR)
    by_id = {e.event_id: e for e in events}
    ids = [e.event_id for e in events]
    c = next(m for m in meta.moments if m.key == "c")
    seg = [by_id[i] for i in ids[ids.index(c.first_event_id): ids.index(c.last_event_id) + 1]]
    assert seg[0].type in ("interception", "ball_recovery") and seg[0].team_id == "hba"
    assert seg[0].x < 52.5  # won high up for Harbour, who attack toward x=0
    assert seg[-1].event_time_ms - seg[0].event_time_ms <= 10_000
    assert len(seg) - 1 <= 4  # actions after the recovery
    assert all(e.team_id == "hba" for e in seg)


def test_moments_present_and_resolve():
    meta, events = load_scenario(SCENARIO_DIR)
    ids = [e.event_id for e in events]
    assert [m.key for m in meta.moments] == ["a", "b", "c", "d"]
    pos = [(ids.index(m.first_event_id), ids.index(m.last_event_id)) for m in meta.moments]
    assert all(f <= l for f, l in pos)
    assert all(pos[i][1] < pos[i + 1][0] for i in range(3))


def test_moment_b_pressure_and_pass_drop():
    meta, events = load_scenario(SCENARIO_DIR)
    ids = [e.event_id for e in events]
    rng = {m.key: events[ids.index(m.first_event_id): ids.index(m.last_event_id) + 1] for m in meta.moments}

    def comp(seg):
        p = [e for e in seg if e.type == "pass" and e.team_id == "nbr"]
        return sum(e.outcome == "complete" for e in p) / len(p)

    assert comp(rng["b"]) < comp(rng["a"])
    pressure = [e for e in rng["b"] if e.type == "pressure" and e.team_id == "hba"]
    assert len(pressure) >= 5 and all(e.x < 52.5 + 10 for e in pressure)  # in Northbridge's half-ish
    assert rng["b"][-1].event_time_ms - rng["b"][0].event_time_ms >= 50_000


def test_moment_d_blocked_shot_and_low_threat():
    meta, events = load_scenario(SCENARIO_DIR)
    ids = [e.event_id for e in events]
    m = next(m for m in meta.moments if m.key == "d")
    seg = events[ids.index(m.first_event_id): ids.index(m.last_event_id) + 1]
    shots = [e for e in seg if e.type == "shot"]
    assert [s.outcome for s in shots] == ["blocked"] and shots[0].team_id == "nbr"
    assert Counter(e.team_id for e in seg)["nbr"] > Counter(e.team_id for e in seg)["hba"]


def test_attack_direction_and_pass_continuity():
    _, events = load_scenario(SCENARIO_DIR)
    for e in events:
        if e.team_id == "nbr" and e.end_x is not None and e.type == "pass" and e.outcome == "complete":
            assert e.end_x >= e.x - 25  # sanity: no wild reversals
    # next action by the same team starts near where a completed pass ended
    for prev, cur in zip(events, events[1:]):
        if prev.type == "pass" and prev.outcome == "complete" and cur.team_id == prev.team_id \
                and cur.type in ("pass", "carry", "shot", "dribble"):
            d = ((cur.x - prev.end_x) ** 2 + (cur.y - prev.end_y) ** 2) ** 0.5
            assert d <= 4.0, (prev.event_id, cur.event_id, d)
