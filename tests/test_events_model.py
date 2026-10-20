import pytest
from pydantic import ValidationError

from contracts.events import MatchEvent, ScenarioMeta
from conftest import base_event, base_meta


def test_valid_event():
    e = MatchEvent.model_validate(base_event())
    assert e.schema_version == "1.0" and e.type == "pass" and e.synthetic is True


def test_missing_optionals_stay_none():
    e = MatchEvent.model_validate(
        base_event(player_id=None, outcome=None, end_x=None, end_y=None,
                   recipient_player_id=None, possession_id=None, type="pressure")
    )
    assert e.player_id is None and e.outcome is None and e.end_x is None


def test_frozen():
    e = MatchEvent.model_validate(base_event())
    with pytest.raises(ValidationError):
        e.x = 1.0


@pytest.mark.parametrize("field,value", [
    ("x", -0.1), ("x", 105.1), ("y", -1.0), ("y", 68.1),
    ("end_x", 106.0), ("end_y", -2.0),
    ("sequence", 0), ("event_time_ms", -1), ("period", 3), ("period", 0),
])
def test_out_of_bounds_rejected(field, value):
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(**{field: value}))


def test_pitch_edges_accepted():
    MatchEvent.model_validate(base_event(x=0.0, y=0.0, end_x=105.0, end_y=68.0))


@pytest.mark.parametrize("t", ["tackle", "pressure", "interception", "clearance", "foul"])
def test_end_coords_rejected_for_other_types(t):
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(type=t, outcome=None, end_x=10.0, end_y=10.0,
                                                recipient_player_id=None))


@pytest.mark.parametrize("t,o", [("pass", "goal"), ("shot", "complete"), ("tackle", "complete"),
                                 ("pressure", "won"), ("kick_off", "goal")])
def test_invalid_outcome_for_type(t, o):
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(type=t, outcome=o, end_x=None, end_y=None,
                                                recipient_player_id=None))


def test_valid_outcomes():
    MatchEvent.model_validate(base_event(type="shot", outcome="goal", recipient_player_id=None))
    MatchEvent.model_validate(base_event(type="tackle", outcome="won", end_x=None, end_y=None,
                                         recipient_player_id=None))


def test_synthetic_must_be_true():
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(synthetic=False))
    e = base_event()
    del e["synthetic"]
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(e)


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(bogus=1))


def test_unknown_type_rejected():
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(type="header"))


def test_meta_valid_and_strict():
    m = ScenarioMeta.model_validate(base_meta())
    assert m.moments[0].first_event_id == "e1"
    with pytest.raises(ValidationError):
        ScenarioMeta.model_validate(base_meta(synthetic=False))
    with pytest.raises(ValidationError):
        ScenarioMeta.model_validate(base_meta(extra=1))


@pytest.mark.parametrize("field,value", [
    ("sequence", "7"), ("sequence", True), ("sequence", 7.0), ("event_time_ms", 5.0),
    ("period", "2"), ("x", "50.5"), ("y", "3"), ("end_x", "5.0"), ("scenario_seed", "1"),
    ("scenario_seed", 1.0), ("synthetic", 1), ("match_id", 5), ("type", 3),
])
def test_strict_types_rejected(field, value):
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(**{field: value}))


def test_int_accepted_for_float_coordinates():
    e = MatchEvent.model_validate(base_event(x=50, y=34, end_x=55, end_y=30))
    assert e.x == 50.0


def test_xy_optional_none_stays_none():
    e = MatchEvent.model_validate(
        base_event(type="substitution", outcome=None, x=None, y=None, end_x=None, end_y=None,
                   recipient_player_id=None, possession_id=None))
    assert e.x is None and e.y is None


def test_substitution_has_no_coordinates():
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(
            base_event(type="substitution", outcome=None, end_x=None, end_y=None,
                       recipient_player_id=None, possession_id=None))


@pytest.mark.parametrize("missing", ["x", "y"])
def test_xy_required_for_non_substitution(missing):
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(**{missing: None}))


ON_BALL = ["pass", "carry", "dribble", "shot", "kick_off", "clearance", "interception",
           "ball_recovery", "tackle"]


@pytest.mark.parametrize("t", ON_BALL)
def test_possession_required_on_ball(t):
    kw = dict(type=t, outcome=None, end_x=None, end_y=None, recipient_player_id=None,
              possession_id=None)
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(**kw))
    MatchEvent.model_validate(base_event(**{**kw, "possession_id": "p02"}))


def test_possession_optional_off_ball():
    MatchEvent.model_validate(base_event(type="pressure", outcome=None, end_x=None, end_y=None,
                                         recipient_player_id=None, possession_id=None))


def test_recipient_only_on_pass():
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(type="carry", outcome="complete"))  # recipient set


def test_recipient_required_when_complete():
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(recipient_player_id=None))
    MatchEvent.model_validate(base_event(outcome="incomplete", recipient_player_id=None))
    MatchEvent.model_validate(base_event(outcome="incomplete"))


def test_recipient_not_self():
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(recipient_player_id="nbr-07"))


def test_pressured_only_on_pressure():
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(pressured_player_id="hba-04"))
    MatchEvent.model_validate(base_event(
        type="pressure", team_id="hba", player_id="hba-04", outcome=None, end_x=None, end_y=None,
        recipient_player_id=None, possession_id=None, pressured_player_id="nbr-07"))


def test_meta_segment_and_score():
    with pytest.raises(ValidationError):
        ScenarioMeta.model_validate(base_meta(segment_start_ms=10, segment_end_ms=5))
    with pytest.raises(ValidationError):
        ScenarioMeta.model_validate(base_meta(initial_score={"home": -1, "away": 0}))
    with pytest.raises(ValidationError):
        ScenarioMeta.model_validate(base_meta(initial_score={"home": "0", "away": 0}))
    with pytest.raises(ValidationError):
        ScenarioMeta.model_validate(base_meta(scenario_seed="1"))


@pytest.mark.parametrize("kw", [{"end_x": None}, {"end_y": None}])
def test_end_coords_both_or_neither(kw):
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(**kw))
