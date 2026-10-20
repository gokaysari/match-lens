import pytest

from domain.ingest import IngestError, load_scenario
from conftest import SCENARIO_DIR, base_event as ev, base_meta


def test_valid_minimal_loads(make_scenario):
    meta, events = load_scenario(make_scenario([ev(), ev(event_id="e2", sequence=5, event_time_ms=10)]))
    assert meta.match_id == "m1" and [e.event_id for e in events] == ["e1", "e2"]


def test_committed_scenario_loads():
    meta, events = load_scenario(SCENARIO_DIR)
    assert meta.match_id and events


def test_empty_events_rejected(make_scenario):
    with pytest.raises(IngestError) as ei:
        load_scenario(make_scenario([]))
    assert ei.value.code == "EMPTY_SCENARIO"


def code_of(make_scenario, events, meta=None):
    with pytest.raises(IngestError) as ei:
        load_scenario(make_scenario(events, meta))
    return ei.value


def test_invalid_event(make_scenario):
    err = code_of(make_scenario, [ev(), ev(event_id="e2", sequence=2, x=999)])
    assert err.code == "INVALID_EVENT" and err.event_ids == ["e2"]


def test_duplicate_event_id(make_scenario):
    err = code_of(make_scenario, [ev(), ev(sequence=2, event_time_ms=5)])
    assert err.code == "DUPLICATE_EVENT_ID" and err.event_ids == ["e1"]


@pytest.mark.parametrize("seq", [1, 3])
def test_non_monotonic_sequence(make_scenario, seq):
    err = code_of(make_scenario, [ev(sequence=3), ev(event_id="e2", sequence=seq)])
    assert err.code == "NON_MONOTONIC_SEQUENCE" and err.event_ids == ["e2"]


def test_sequence_gap_allowed(make_scenario):
    load_scenario(make_scenario([ev(sequence=1), ev(event_id="e2", sequence=9, event_time_ms=1)]))


def test_clock_regression(make_scenario):
    err = code_of(make_scenario, [ev(event_time_ms=100), ev(event_id="e2", sequence=2, event_time_ms=99)])
    assert err.code == "CLOCK_REGRESSION" and err.event_ids == ["e2"]


def test_clock_reset_across_periods_ok(make_scenario):
    # period 2 clock restarts below the last period-1 stoppage-time event: allowed
    load_scenario(make_scenario([ev(event_time_ms=2_900_000),
                                 ev(event_id="e2", sequence=2, period=2, event_time_ms=2_700_000)]))


def test_decreasing_period_is_clock_regression(make_scenario):
    err = code_of(make_scenario, [ev(period=2, event_time_ms=2_800_000), ev(event_id="e2", sequence=2, period=1, event_time_ms=5)])
    assert err.code == "CLOCK_REGRESSION" and err.event_ids == ["e2"]


def test_match_id_mismatch(make_scenario):
    err = code_of(make_scenario, [ev(), ev(event_id="e2", sequence=2, match_id="other")])
    assert err.code == "MATCH_ID_MISMATCH" and err.event_ids == ["e2"]


def test_unknown_team(make_scenario):
    err = code_of(make_scenario, [ev(team_id="zzz")])
    assert err.code == "UNKNOWN_TEAM" and err.event_ids == ["e1"]


def test_unknown_player(make_scenario):
    err = code_of(make_scenario, [ev(player_id="nbr-99")])
    assert err.code == "UNKNOWN_PLAYER" and err.event_ids == ["e1"]


def test_player_on_wrong_team_is_unknown_player(make_scenario):
    err = code_of(make_scenario, [ev(team_id="hba", player_id="nbr-07")])
    assert err.code == "UNKNOWN_PLAYER"


def test_null_player_allowed(make_scenario):
    load_scenario(make_scenario([ev(type="foul", player_id=None, possession_id=None, outcome=None,
                                    recipient_player_id=None, end_x=None, end_y=None)]))


@pytest.mark.parametrize("t,extra", [
    ("pass", {"recipient_player_id": None}),
    ("shot", {"recipient_player_id": None, "end_x": 90.0, "end_y": 30.0}),
    ("tackle", {"recipient_player_id": None, "end_x": None, "end_y": None}),
    ("dribble", {"recipient_player_id": None, "end_x": None, "end_y": None}),
])
def test_missing_outcome(make_scenario, t, extra):
    err = code_of(make_scenario, [ev(type=t, outcome=None, **extra)])
    assert err.code == "MISSING_OUTCOME" and err.event_ids == ["e1"]


def test_missing_player_on_ball(make_scenario):
    err = code_of(make_scenario, [ev(player_id=None)])
    assert err.code == "MISSING_PLAYER" and err.event_ids == ["e1"]


def test_period2_clock_mismatch(make_scenario):
    err = code_of(make_scenario, [ev(period=2, event_time_ms=2_699_999)])
    assert err.code == "PERIOD_CLOCK_MISMATCH" and err.event_ids == ["e1"]


def test_seed_mismatch(make_scenario):
    err = code_of(make_scenario, [ev(scenario_seed=2)])
    assert err.code == "SEED_MISMATCH" and err.event_ids == ["e1"]


def test_possession_used_by_two_teams(make_scenario):
    err = code_of(make_scenario, [ev(), ev(event_id="e2", sequence=2, team_id="hba", player_id="hba-04",
                                           recipient_player_id="hba-09")])
    assert err.code == "POSSESSION_INCONSISTENT" and err.event_ids == ["e2"]


def test_possession_reappears(make_scenario):
    err = code_of(make_scenario, [ev(), ev(event_id="e2", sequence=2, possession_id="p02"),
                                  ev(event_id="e3", sequence=3, possession_id="p01")])
    assert err.code == "POSSESSION_INCONSISTENT" and err.event_ids == ["e3"]


def test_duplicate_moment_keys(make_scenario):
    m = base_meta()
    m["moments"] = m["moments"] * 2
    assert code_of(make_scenario, [ev()], m).code == "INVALID_META"


def test_duplicate_shirt_numbers_in_team(make_scenario):
    m = base_meta()
    m["players"][1]["shirt_number"] = 7
    assert code_of(make_scenario, [ev()], m).code == "INVALID_META"


@pytest.mark.parametrize("name", ["meta.json", "events.jsonl"])
def test_invalid_encoding(make_scenario, name):
    d = make_scenario([ev()])
    (d / name).write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(IngestError) as ei:
        load_scenario(d)
    assert ei.value.code == "INVALID_ENCODING"


def test_bad_json_line_is_invalid_event(make_scenario, tmp_path):
    d = make_scenario([ev()])
    (d / "events.jsonl").write_text("{not json\n")
    with pytest.raises(IngestError) as ei:
        load_scenario(d)
    assert ei.value.code == "INVALID_EVENT"


def test_missing_files(tmp_path, make_scenario):
    with pytest.raises(IngestError) as ei:
        load_scenario(tmp_path / "nope")
    assert ei.value.code == "MISSING_FILE"
    d = make_scenario([ev()])
    (d / "events.jsonl").unlink()
    with pytest.raises(IngestError) as ei:
        load_scenario(d)
    assert ei.value.code == "MISSING_FILE"


def test_coerced_values_rejected_as_invalid_event(make_scenario):
    err = code_of(make_scenario, [ev(sequence="7")])
    assert err.code == "INVALID_EVENT" and err.event_ids == ["e1"]
    assert "sequence" in str(err)  # field path in the message


def test_invalid_meta_strict_and_detail(make_scenario):
    err = code_of(make_scenario, [ev()], base_meta(scenario_seed="1"))
    assert err.code == "INVALID_META" and "scenario_seed" in str(err)


def test_recipient_unknown_and_opponent(make_scenario):
    assert code_of(make_scenario, [ev(recipient_player_id="nbr-99")]).code == "UNKNOWN_PLAYER"
    err = code_of(make_scenario, [ev(recipient_player_id="hba-04")])
    assert err.code == "INVALID_EVENT" and err.event_ids == ["e1"]


def press(**o):
    base = dict(type="pressure", team_id="hba", player_id="hba-04", outcome=None, end_x=None,
                end_y=None, recipient_player_id=None, possession_id=None,
                pressured_player_id="nbr-07")
    base.update(o)
    return ev(**base)


def test_pressured_must_be_known_opponent(make_scenario):
    load_scenario(make_scenario([press()]))
    assert code_of(make_scenario, [press(pressured_player_id="nbr-99")]).code == "UNKNOWN_PLAYER"
    err = code_of(make_scenario, [press(pressured_player_id="hba-09")])
    assert err.code == "INVALID_EVENT" and err.event_ids == ["e1"]


def test_event_outside_segment(make_scenario):
    err = code_of(make_scenario, [ev(event_time_ms=50)], base_meta(segment_start_ms=100))
    assert err.code == "EVENT_OUTSIDE_SEGMENT" and err.event_ids == ["e1"]
    err = code_of(make_scenario, [ev(event_time_ms=500)], base_meta(segment_end_ms=400))
    assert err.code == "EVENT_OUTSIDE_SEGMENT"


def moment(first, last):
    return [{"key": "a", "description": "d", "first_event_id": first, "last_event_id": last}]


def test_moment_events_must_exist_and_be_ordered(make_scenario):
    evs = [ev(), ev(event_id="e2", sequence=2, event_time_ms=1)]
    err = code_of(make_scenario, evs, base_meta(moments=moment("e1", "zz")))
    assert err.code == "UNKNOWN_MOMENT_EVENT" and err.event_ids == ["zz"]
    err = code_of(make_scenario, evs, base_meta(moments=moment("e2", "e1")))
    assert err.code == "UNKNOWN_MOMENT_EVENT"
    load_scenario(make_scenario(evs, base_meta(moments=moment("e1", "e2"))))


def test_meta_referential_integrity(make_scenario):
    m = base_meta()
    cases = {
        "dup team": {**m, "teams": m["teams"] + [m["teams"][0]]},
        "two homes": {**m, "teams": [{**m["teams"][0]}, {**m["teams"][1], "side": "home"}]},
        "no away": {**m, "teams": [m["teams"][0]]},
        "dup player": {**m, "players": m["players"] + [m["players"][0]]},
        "player unknown team": {**m, "players": m["players"] + [
            {"id": "zzz-01", "team_id": "zzz", "name": "x", "shirt_number": 1}]},
    }
    for name, meta in cases.items():
        err = code_of(make_scenario, [ev()], meta)
        assert err.code == "INVALID_META", name
