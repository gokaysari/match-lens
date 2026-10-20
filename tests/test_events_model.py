import pytest
from pydantic import ValidationError

from contracts.events import MatchEvent, ScenarioMeta
from conftest import base_event, base_meta


def test_valid_event():
    e = MatchEvent.model_validate(base_event())
    assert e.schema_version == "1.0" and e.type == "pass" and e.synthetic is True


def test_missing_optionals_stay_none():
    e = MatchEvent.model_validate(
        base_event(player_id=None, outcome=None, end_x=None, end_y=None)
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
        MatchEvent.model_validate(base_event(type=t, outcome=None, end_x=10.0, end_y=10.0))


@pytest.mark.parametrize("t,o", [("pass", "goal"), ("shot", "complete"), ("tackle", "complete"),
                                 ("pressure", "won"), ("kick_off", "goal")])
def test_invalid_outcome_for_type(t, o):
    with pytest.raises(ValidationError):
        MatchEvent.model_validate(base_event(type=t, outcome=o, end_x=None, end_y=None))


def test_valid_outcomes():
    MatchEvent.model_validate(base_event(type="shot", outcome="goal"))
    MatchEvent.model_validate(base_event(type="tackle", outcome="won", end_x=None, end_y=None))


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
