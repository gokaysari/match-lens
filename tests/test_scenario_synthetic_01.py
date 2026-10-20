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


def _rows(g, seed):
    import json
    return [json.loads(l) for l in g.render(seed=seed)["events.jsonl"].decode().splitlines()]


def test_generator_seed_changes_jitter_not_script():
    g = load_generator()
    base = _rows(g, g.SEED)
    key = lambda r: (r["team_id"], r["player_id"], r["type"], r["outcome"], r["recipient_player_id"],
                     r["possession_id"])
    for seed in (g.SEED + 1, g.SEED + 2, 7):
        other = _rows(g, seed)
        assert [key(r) for r in other] == [key(r) for r in base]
        assert [(r["x"], r["y"]) for r in other] != [(r["x"], r["y"]) for r in base]
        assert [r["event_time_ms"] for r in other] != [r["event_time_ms"] for r in base]


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


def test_attack_direction_both_teams():
    _, events = load_scenario(SCENARIO_DIR)
    nbr = [e for e in events if e.team_id == "nbr" and e.type == "pass" and e.outcome == "complete"]
    assert any(e.end_x > e.x + 3 for e in nbr)
    hba = [e for e in events if e.team_id == "hba" and e.type == "pass" and e.outcome == "complete"
           and abs(e.end_x - e.x) > 3]
    assert hba and all(e.end_x < e.x for e in hba), "Harbour progressive passes must reduce x"
    assert all(e.end_x <= 1e-9 for e in events if e.type == "shot" and e.team_id == "hba")
    assert all(e.end_x >= 85 for e in events if e.type == "shot" and e.team_id == "nbr")


def _end(e):
    return (e.end_x, e.end_y) if e.end_x is not None else (e.x, e.y)


def test_continuity_within_possession():
    _, events = load_scenario(SCENARIO_DIR)
    on_ball = [e for e in events if e.possession_id is not None]
    for prev, cur in zip(on_ball, on_ball[1:]):
        if prev.possession_id != cur.possession_id:
            continue
        px, py = _end(prev)
        d = ((cur.x - px) ** 2 + (cur.y - py) ** 2) ** 0.5
        assert d <= 4.0, (prev.event_id, cur.event_id, d)


def test_possession_ids_and_team_consistency():
    _, events = load_scenario(SCENARIO_DIR)
    teams: dict[str, str] = {}
    for e in events:
        if e.possession_id is not None:
            assert teams.setdefault(e.possession_id, e.team_id) == e.team_id
    ordered = []
    for e in events:
        if e.possession_id is not None and (not ordered or ordered[-1] != e.possession_id):
            ordered.append(e.possession_id)
    assert len(ordered) == len(set(ordered))  # a possession id is never reused after it ended
    ko = [e for e in events if e.type == "kick_off"]
    assert ko and (ko[0].x, ko[0].y) == (52.5, 34.0)


def test_complete_pass_is_followed_by_recipient():
    _, events = load_scenario(SCENARIO_DIR)
    last_pass = {}
    for e in events:
        if e.possession_id is None:
            continue
        prev = last_pass.get(e.possession_id)
        if prev is not None:
            assert e.player_id == prev.recipient_player_id, (prev.event_id, e.event_id)
        last_pass[e.possession_id] = e if (e.type == "pass" and e.outcome == "complete") else None


def test_no_self_pass_in_possession():
    _, events = load_scenario(SCENARIO_DIR)
    on_ball = [e for e in events if e.possession_id is not None]
    for prev, cur in zip(on_ball, on_ball[1:]):
        if prev.possession_id == cur.possession_id and prev.type == "pass" and cur.type == "pass":
            assert prev.player_id != cur.player_id, (prev.event_id, cur.event_id)


def test_pressure_targets_northbridge_ball_carrier():
    _, events = load_scenario(SCENARIO_DIR)
    for e in events:
        if e.type == "pressure":
            assert e.pressured_player_id and e.pressured_player_id.startswith("nbr-")


def test_moment_b_duration_and_variety():
    meta, events = load_scenario(SCENARIO_DIR)
    ids = [e.event_id for e in events]
    m = next(m for m in meta.moments if m.key == "b")
    seg = events[ids.index(m.first_event_id): ids.index(m.last_event_id) + 1]
    dur = (seg[-1].event_time_ms - seg[0].event_time_ms) / 1000
    assert 55 <= dur <= 65
    assert f"{round(dur)} seconds" in m.description
    hba = [e for e in seg if e.team_id == "hba" and e.type in ("tackle", "interception", "ball_recovery")]
    assert {e.type for e in hba} == {"tackle", "interception", "ball_recovery"}
    assert len({e.player_id for e in hba}) >= 3
    nbr_regain = [e for e in seg if e.team_id == "nbr" and e.type in ("tackle", "interception", "ball_recovery")]
    assert len({e.type for e in nbr_regain}) >= 2


def test_segment_and_initial_score():
    meta, events = load_scenario(SCENARIO_DIR)
    assert (meta.initial_score.home, meta.initial_score.away) == (0, 0)
    assert meta.segment_start_ms == 58 * 60_000 and meta.segment_end_ms == 62 * 60_000


def test_every_possession_change_is_explained():
    _, events = load_scenario(SCENARIO_DIR)
    on_ball = [e for e in events if e.possession_id is not None]
    changes = 0
    for prev, cur in zip(on_ball, on_ball[1:]):
        if prev.possession_id == cur.possession_id:
            continue
        changes += 1
        lost = prev.outcome in ("incomplete", "lost", "blocked", "saved", "off_target", "goal") \
            or prev.type == "clearance"
        tackled = cur.type == "tackle" and cur.outcome == "won"
        assert lost or tackled, (prev.event_id, cur.event_id)
    assert changes >= 8
