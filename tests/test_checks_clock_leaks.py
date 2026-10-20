"""Clock digits (mm:ss) are times, never a source of bare allowed numbers; and a
few quantity words that slipped through. Reproduces review findings on 468fc31."""

import pytest

from agents.checks import check_analyst, check_story
from contracts.agents import (AnalystOutput, Claim, ClaimKind, MetricRef, Persona, PersonaText,
                              StoryOutput)
from domain.ingest import load_scenario
from workflow.candidates import build_candidates


@pytest.fixture(scope="module")
def cands():
    meta, events = load_scenario("scenarios/synthetic-01")
    return {c.candidate_id.split("/")[1].split("@")[0]: (c, b) for c, b in build_candidates(meta, events, 2097)}


def claim(text, eids, refs=(), cid="c1"):
    return Claim(claim_id=cid, kind=ClaimKind.observation, text=text, evidence_event_ids=tuple(eids),
                 metric_refs=tuple(MetricRef(name=n, team_id=t) for n, t in refs))


def analyst(cb, *claims_):
    c, b = cb
    return check_analyst(AnalystOutput(candidate_id=c.candidate_id, snapshot_id=c.snapshot_id, claims=claims_), c, b)


def story(cb, claims_, analyst_body, casual_body):
    c, _ = cb
    ids = tuple(x.claim_id for x in claims_)
    out = StoryOutput(candidate_id=c.candidate_id, snapshot_id=c.snapshot_id, variants=(
        PersonaText(persona=Persona.analyst, title="Moment", body=analyst_body, claim_ids=ids),
        PersonaText(persona=Persona.casual, title="Moment", body=casual_body, claim_ids=ids)))
    return check_story(out, claims_, c)


GOAL_REFS = (("shots", "hba"), ("goals", "hba"))


@pytest.mark.parametrize("text", [
    "Harbour Athletic scored from 8 shots.",
    "Harbour Athletic had 60 touches before the goal.",
    "Harbour Athletic scored at 60:08 after 8 passes.",
    "Harbour Athletic scored 8 seconds after winning the ball.",
])
def test_card_clock_digits_do_not_whitelist_counts(cands, text):
    cb = cands["goal"]
    codes = analyst(cb, claim(text, cb[0].source_card.evidence_event_ids, GOAL_REFS))
    assert any(code.startswith("NUMBER_NOT_ALLOWED") for code in codes), codes


def test_card_clock_itself_is_allowed(cands):
    cb = cands["goal"]
    assert analyst(cb, claim("Harbour Athletic scored at 60:08.", cb[0].source_card.evidence_event_ids, GOAL_REFS)) == ()


def _press_claim(cands):
    cb = cands["press_surge"]
    c = claim("Harbour Athletic made 16 pressures in Northbridge FC's half, the first at 59:01.",
              ["e025"], (("pressures_opp_half", "hba"),))
    assert analyst(cb, c) == ()  # 59:01 is e025's clock, 16 is the metric
    return cb, c


def test_story_claim_clock_digits_do_not_whitelist_counts(cands):
    cb, c = _press_claim(cands)
    codes = story(cb, [c], "Harbour Athletic made 16 pressures and 59 tackles.", "Harbour won the ball 1 times.")
    assert "NUMBER_NOT_ALLOWED:59" in codes and "NUMBER_NOT_ALLOWED:1" in codes, codes


def test_story_may_repeat_a_claim_clock(cands):
    cb, c = _press_claim(cands)
    assert story(cb, [c], "Harbour Athletic made 16 pressures from 59:01.", "Harbour pressed hard from 59:01.") == ()


@pytest.mark.parametrize("text,word", [
    ("Harbour Athletic pressed 16 times in half a minute.", "half"),
    ("Harbour Athletic made a dozen pressures.", "dozen"),
    ("Harbour Athletic won a couple of tackles.", "couple"),
    ("Harbour Athletic won a handful of duels.", "handful"),
])
def test_more_quantity_words_rejected(cands, text, word):
    cb = cands["press_surge"]
    codes = analyst(cb, claim(text, cb[0].source_card.evidence_event_ids[:2], (("pressures_opp_half", "hba"),)))
    assert f"NUMBER_WORD:{word}" in codes, codes
