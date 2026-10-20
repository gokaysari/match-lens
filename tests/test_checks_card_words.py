"""The source-card exemption covers number words the card itself uses as numbers,
not every word that appears in the card text."""

import pytest

from agents.checks import check_analyst
from contracts.agents import AnalystOutput, Claim, ClaimKind, MetricRef
from domain.ingest import load_scenario
from workflow.candidates import build_candidates


@pytest.fixture(scope="module")
def press():
    meta, events = load_scenario("scenarios/synthetic-01")
    cand, bundle = next(cb for cb in build_candidates(meta, events, 2097) if "press_surge" in cb[0].candidate_id)
    assert "half" in cand.source_card.body  # pitch half, as in "Northbridge FC's half"
    return cand, bundle


def _check(press, text):
    cand, bundle = press
    claim = Claim(
        claim_id="c1", kind=ClaimKind.observation, text=text,
        evidence_event_ids=cand.source_card.evidence_event_ids[:2],
        metric_refs=(MetricRef(name="pressures_opp_half", team_id="hba"),),
    )
    out = AnalystOutput(candidate_id=cand.candidate_id, snapshot_id=cand.snapshot_id, claims=(claim,))
    return check_analyst(out, cand, bundle)


def test_fraction_half_rejected_even_when_card_mentions_a_pitch_half(press):
    assert "NUMBER_WORD:half" in _check(press, "Half of Northbridge FC's passes failed.")


def test_pitch_half_from_the_card_still_passes(press):
    assert _check(press, "Harbour Athletic pressed 16 times in Northbridge FC's half.") == ()
