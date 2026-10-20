import pytest

from domain.ingest import IngestError, load_scenario
from conftest import SCENARIO_DIR, base_event as ev


def test_valid_minimal_loads(make_scenario):
    meta, events = load_scenario(make_scenario([ev(), ev(event_id="e2", sequence=5, event_time_ms=10)]))
    assert meta.match_id == "m1" and [e.event_id for e in events] == ["e1", "e2"]


def test_committed_scenario_loads():
    meta, events = load_scenario(SCENARIO_DIR)
    assert meta.match_id and events


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
    load_scenario(make_scenario([ev(event_time_ms=2_700_000),
                                 ev(event_id="e2", sequence=2, period=2, event_time_ms=2_700_000)]))


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
    load_scenario(make_scenario([ev(player_id=None)]))


def test_bad_json_line_is_invalid_event(make_scenario, tmp_path):
    d = make_scenario([ev()])
    (d / "events.jsonl").write_text("{not json\n")
    with pytest.raises(IngestError) as ei:
        load_scenario(d)
    assert ei.value.code == "INVALID_EVENT"
