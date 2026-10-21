"""Checks for contracts v2: model text has no digits; numbers are {fact} placeholders."""

import pytest
from conftest import SCENARIO_DIR

from agents.checks import check_analyst, check_story
from agents.render import render
from contracts.agents import AnalystOutput, Claim, ClaimKind, Persona, PersonaText, StoryOutput
from domain.ingest import load_scenario
from workflow.candidates import build_candidates


@pytest.fixture(scope="module")
def cands():
    meta, events = load_scenario(SCENARIO_DIR)
    return {c.source_card.kind.value: (c, b) for c, b in build_candidates(meta, events, events[-1].sequence)}


@pytest.fixture
def press(cands):
    return cands["press_surge"]


@pytest.fixture
def goal(cands):
    return cands["goal"]


def claim(text, cid="c1", kind=ClaimKind.observation, eids=("e024", "e025")):
    return Claim(claim_id=cid, kind=kind, text=text, evidence_event_ids=tuple(eids))


def analyst(cb, *claims_):
    c, b = cb
    return check_analyst(AnalystOutput(candidate_id=c.candidate_id, snapshot_id=c.snapshot_id, claims=claims_), c, b)


def one(cb, text):
    return analyst(cb, claim(text))


def story(cb, claims_, analyst_title="Moment", analyst_body="A body.", casual_title="Moment", casual_body="Another.",
          analyst_ids=None, casual_ids=None):
    c, b = cb
    ids = tuple(x.claim_id for x in claims_)
    out = StoryOutput(candidate_id=c.candidate_id, snapshot_id=c.snapshot_id, variants=(
        PersonaText(persona=Persona.analyst, title=analyst_title, body=analyst_body,
                    claim_ids=tuple(analyst_ids) if analyst_ids is not None else ids),
        PersonaText(persona=Persona.casual, title=casual_title, body=casual_body,
                    claim_ids=tuple(casual_ids) if casual_ids is not None else ids)))
    return check_story(out, claims_, c, b)


OK = "Harbour Athletic made {pressures_opp_half.hba} pressures in Northbridge FC's half in the last {window_s} s."


# ---------------------------------------------------------------- digits


def test_valid_placeholder_text_passes(press):
    assert one(press, OK) == ()


@pytest.mark.parametrize("text", [
    "Harbour Athletic made 16 pressures.",
    "Harbour Athletic scored at 1:00.",
    "Harbour Athletic scored at 60:08 after 8 passes.",
    "Harbour Athletic pressed after event e058.",
    "Harbour Athletic pressed in the 3rd minute.",
    "Harbour Athletic won 2² duels.",  # superscript digit
    "Harbour Athletic won ٣ duels.",  # arabic-indic digit
    "Harbour Athletic won ½ of duels.",  # vulgar fraction
])
def test_any_digit_in_claim_is_forbidden(press, text):
    assert "DIGIT_FORBIDDEN:c1" in one(press, text)


def test_digits_inside_a_placeholder_key_are_fine(goal):
    assert analyst(goal, claim("Harbour Athletic scored at {t.e066}, making it {score}.", eids=("e066",))) == ()


# ---------------------------------------------------------------- placeholder grammar


@pytest.mark.parametrize("text", [
    "Made {Pressures_opp_half.hba} pressures.",
    "Made { pressures_opp_half.hba } pressures.",
    "Made {} pressures.",
    "Made {pressures_opp_half.hba pressures.",
    "Made pressures_opp_half.hba} pressures.",
    "Made {pressures_opp_half..hba} pressures.",
    "Made {{pressures_opp_half.hba}} pressures.",
    "Made {pressures-opp} pressures.",
])
def test_bad_placeholder(press, text):
    assert "BAD_PLACEHOLDER:c1" in one(press, text)


def test_unknown_fact(press):
    assert "UNKNOWN_FACT:c1:shots.invented" in one(press, "Harbour made {shots.invented} shots.")


def test_unknown_fact_prev_window_missing_for_this_moment(press):
    # the press moment has no previous window: prev.* keys do not exist
    assert "UNKNOWN_FACT:c1:prev.pressures.hba" in one(press, "Down from {prev.pressures.hba} pressures.")


# ---------------------------------------------------------------- number words


@pytest.mark.parametrize("word", [
    "two", "Twenty", "ninety", "hundred", "halves", "double", "doubled", "twice", "triple", "tripled",
    "third", "thirds", "quarter", "quarters", "tenth", "dozen", "couple", "handful", "zero", "nil",
])
def test_number_words_rejected(press, word):
    assert f"NUMBER_WORD:c1:{word.lower()}" in one(press, f"Harbour pressed {word} time.")


@pytest.mark.parametrize("noun", ["goal", "pass", "shots", "chance", "pressure", "minute"])
@pytest.mark.parametrize("word", ["one", "single"])
def test_one_and_single_only_before_counted_nouns(press, word, noun):
    assert f"NUMBER_WORD:c1:{word}" in one(press, f"Harbour had {word} {noun}.")


def test_one_and_single_elsewhere_are_english(press):
    assert one(press, "No one escaped, one of them long, a single moment of calm.") == ()


@pytest.mark.parametrize("text", [
    "Harbour won half of the passes.", "A goal, a half.", "A goal by half.",
    "Half the passes were won.", "Harbour doubled up.",
])
def test_fraction_half_rejected(press, text):
    assert any(c.startswith("NUMBER_WORD:") for c in one(press, text))


@pytest.mark.parametrize("text", [
    "Pressure in the second half of the period.",
    "Pressed in their own half, first half too.",
    "Harbour Athletic pressed in Northbridge FC's half.",
    "Pressure in the opposition half.",
    "Pressed before half-time, or half time.",
])
def test_pitch_and_period_halves_pass(press, text):
    assert one(press, text) == ()


@pytest.mark.parametrize("phrase", [
    "final third", "middle third", "attacking third", "defensive third", "one-two", "half-space",
    "half-time", "half time", "back four", "back three",
    "Final Third", "BACK FOUR", "Half-Time", "One-Two",
])
def test_exempt_football_phrases(press, phrase):
    assert one(press, f"Harbour Athletic worked the {phrase} patiently.") == ()


def test_exempt_phrase_does_not_hide_other_number_words(press):
    codes = one(press, "In the final third they had two shots.")
    assert "NUMBER_WORD:c1:two" in codes and "NUMBER_WORD:c1:third" not in codes
    assert "NUMBER_WORD:c1:third" in one(press, "A third of the passes failed.")
    assert "NUMBER_WORD:c1:four" in one(press, "Harbour had four, not a back four.")


def test_first_and_second_are_allowed(press):
    assert one(press, "The first touch came before the second ball and the first half.") == ()


# ---------------------------------------------------------------- structural analyst rules still hold


def test_markup_and_structure(press):
    assert "MARKUP_FORBIDDEN:c1" in one(press, "Harbour <b>pressed</b>.")
    assert "UNKNOWN_EVIDENCE:e999" in analyst(press, claim(OK, eids=("e999",)))
    assert "NO_OBSERVATION" in analyst(press, claim(OK, kind=ClaimKind.interpretation))
    assert "TOO_MANY_CLAIMS" in analyst(press, *[claim(OK, cid=f"c{i}") for i in range(4)])
    assert "DUPLICATE_CLAIM_ID:c1" in analyst(press, claim(OK), claim(OK, kind=ClaimKind.interpretation))


# ---------------------------------------------------------------- story


C1 = claim(OK)
C2 = claim("Northbridge FC completed {pass_completion.nbr.frac} passes.", cid="c2",
           kind=ClaimKind.interpretation, eids=("e022", "e023"))


def test_story_with_claims_placeholders_passes(press):
    assert story(press, [C1, C2], analyst_body="Harbour made {pressures_opp_half.hba} pressures; Northbridge "
                 "completed {pass_completion.nbr.frac} passes.", casual_body="Harbour pressed hard.") == ()


@pytest.mark.parametrize("body", [
    "Harbour Athletic made 16 pressures and 59 tackles.", "Harbour won the ball 1 times.",
    "Harbour pressed for 60 s.", "At 1:00 they pressed.",
])
def test_story_digits_forbidden(press, body):
    assert "DIGIT_FORBIDDEN:analyst" in story(press, [C1], analyst_body=body)
    assert "DIGIT_FORBIDDEN:casual" in story(press, [C1], casual_body=body)
    assert "DIGIT_FORBIDDEN:analyst" in story(press, [C1], analyst_title=body[:50])


def test_story_unknown_and_bad_placeholders(press):
    assert "UNKNOWN_FACT:analyst:shots.invented" in story(press, [C1], analyst_body="They had {shots.invented}.")
    assert "BAD_PLACEHOLDER:analyst" in story(press, [C1], analyst_body="They had {Shots}.")


def test_story_fact_not_in_its_claims(press):
    # a real bundle fact, but the cited claims never used it
    codes = story(press, [C1, C2], analyst_body="They completed {pass_completion.nbr.pct} of passes.",
                  analyst_ids=["c1"])
    assert "FACT_NOT_IN_CLAIMS:pass_completion.nbr.pct" in codes
    assert story(press, [C1, C2], analyst_body="They completed {pass_completion.nbr.frac} passes.",
                 analyst_ids=["c1"]) == ("FACT_NOT_IN_CLAIMS:pass_completion.nbr.frac",)
    assert "FACT_NOT_IN_CLAIMS:score" in story(press, [C1], analyst_body="It is {score}.")


def test_story_may_use_any_cited_claims_placeholder(press):
    assert story(press, [C1, C2], analyst_body="Harbour made {pressures_opp_half.hba} pressures.",
                 casual_body="Northbridge completed {pass_completion.nbr.frac} passes.",
                 analyst_ids=["c1", "c2"], casual_ids=["c2"]) == ()


def test_casual_at_most_one_placeholder_over_title_and_body(press):
    assert story(press, [C1, C2], casual_body="Made {pressures_opp_half.hba}, completed "
                 "{pass_completion.nbr.frac}.") == ("CASUAL_TOO_MANY_NUMBERS",)
    codes = story(press, [C1], casual_title="{pressures_opp_half.hba} pressures",
                  casual_body="Over {window_s} s.")
    assert "CASUAL_TOO_MANY_NUMBERS" in codes
    assert story(press, [C1], casual_body="Same {pressures_opp_half.hba} again, {pressures_opp_half.hba}.") == (
        "CASUAL_TOO_MANY_NUMBERS",)


def test_story_number_words_markup_identical(press):
    assert "NUMBER_WORD:analyst:twice" in story(press, [C1], analyst_body="Twice as many pressures.")
    assert "MARKUP_FORBIDDEN:casual" in story(press, [C1], casual_body="a > b")
    assert "IDENTICAL_BODIES" in story(press, [C1], analyst_body="Same.", casual_body="Same.")


def test_story_rendered_length_limits(press):
    # the template is short, the rendered text is not: fact values count toward the limits
    c, b = press
    long_text = "Harbour Athletic " * 5  # 85 chars
    facts = tuple(f.model_copy(update={"text": long_text}) if f.key == "poss.team" else f for f in b.facts)
    cb = (c, b.model_copy(update={"facts": facts}))
    cl = claim("Team {poss.team} had the ball.")
    assert "TOO_LONG:analyst" in story(cb, [cl], analyst_title="{poss.team}")
    assert "TOO_LONG:casual" in story(cb, [cl], casual_body="{poss.team}{poss.team}{poss.team}{poss.team}")
    assert "TOO_LONG:analyst" not in story(cb, [cl], analyst_body="{poss.team}")


def test_render_replaces_each_placeholder(press):
    facts = press[1].facts
    assert render("{pressures_opp_half.hba} in {window_s} s, {pressures_opp_half.hba}", facts) == "16 in 60 s, 16"
    assert render("no placeholders", facts) == "no placeholders"
    with pytest.raises(KeyError):
        render("{nope}", facts)


# ---------------------------------------------------------------- review round: number words


def words(cb, text):
    return [c for c in one(cb, text) if c.startswith("NUMBER_WORD:")]


@pytest.mark.parametrize("text,word", [
    ("They go one up.", "one"), ("A second goal arrived.", "second"), ("It was a brace.", "brace"),
    ("A hat-trick of chances.", "hat-trick"), ("A hat trick of chances.", "hat-trick"),
    ("Harbour had just one.", "one"), ("Only one, then more.", "one"),
    ("Both goals came late.", "both"), ("They had no shots at all.", "no"),
    ("The first shot missed.", "first"), ("One down and pressing.", "one"), ("One ahead now.", "one"),
    ("Two passes.", "two"),
])
def test_reviewer_number_phrases_rejected(press, text, word):
    assert f"NUMBER_WORD:c1:{word}" in words(press, text)


@pytest.mark.parametrize("text", [
    "The first half was open.", "A second ball dropped.", "A good first touch.", "No one escaped.",
    "Both teams pressed.", "None at all, nobody settled.", "One of them long.", "He is the only one here.",
])
def test_reviewer_number_phrases_allowed(press, text):
    assert words(press, text) == []


@pytest.mark.parametrize("ordinal", ["first", "second"])
@pytest.mark.parametrize("noun", ["goal", "goals", "card", "shot", "pass", "passes", "chance", "corner",
                                  "save", "tackle", "press", "pressures", "minute"])
def test_ordinal_before_counted_noun(press, ordinal, noun):
    assert f"NUMBER_WORD:c1:{ordinal}" in words(press, f"Their {ordinal} {noun} came.")


@pytest.mark.parametrize("noun", ["goals", "cards", "shots", "passes", "chances", "corners", "saves",
                                  "tackles", "pressures", "minutes"])
@pytest.mark.parametrize("word", ["both", "no"])
def test_both_no_before_counted_noun(press, word, noun):
    assert f"NUMBER_WORD:c1:{word}" in words(press, f"There were {word} {noun}.")


# ---------------------------------------------------------------- review round: half


@pytest.mark.parametrize("text", [
    "Harbour pressed in their half.", "Harbour pressed in the opponents' half.",
    "Play stayed in Harbour's half.", "Play stayed in Northbridge half.",
    "Harbour won it in the attacking half.", "They pressed in the defensive half.",
    "Harbour pressed in the other half.", "Play stayed in the opposing half of the pitch.",
    "Most play was in half of the pitch they own.", "Pressed in his own half.", "Play in the home half.",
])
def test_pitch_half_phrases_pass(press, text):
    assert words(press, text) == []


@pytest.mark.parametrize("text", [
    "Harbour completed half of the passes.", "Harbour won half the passes.", "Down by half.",
    "Harbour had a half.", "Half of their passes failed.",
])
def test_fraction_half_phrases_fail(press, text):
    assert "NUMBER_WORD:c1:half" in words(press, text)


# ---------------------------------------------------------------- review round: once


@pytest.mark.parametrize("text", [
    "Once Harbour won the ball, they attacked.", "Harbour attacked. Once they won it, they ran.",
    "Harbour won it, once the press worked.", "The press worked at once.",
])
def test_once_as_conjunction_or_at_once_passes(press, text):
    assert words(press, text) == []


@pytest.mark.parametrize("text", [
    "Harbour won it once.", "Harbour scored once more.", "They won it once again.", "Harbour scored once, then faded.",
    "It happened once in a while.",
])
def test_once_as_a_count_fails(press, text):
    assert "NUMBER_WORD:c1:once" in words(press, text)


# ---------------------------------------------------------------- review round: codes name the claim


def test_codes_name_the_claim_without_cross_claim_dedupe(press):
    codes = analyst(press, claim("Harbour pressed twice {nope.x}.", cid="c1"),
                    claim("Harbour pressed twice {nope.x}.", cid="c2", kind=ClaimKind.interpretation))
    assert {"NUMBER_WORD:c1:twice", "NUMBER_WORD:c2:twice", "UNKNOWN_FACT:c1:nope.x",
            "UNKNOWN_FACT:c2:nope.x"} <= set(codes)


# ---------------------------------------------------------------- fix round 2: fewer false rejections


@pytest.mark.parametrize("text", [
    "Once in possession, Harbour ran.", "Harbour pressed once the ball went wide.",
    "Harbour lost the ball once Northbridge FC closed in.", "A side who had once looked passive.",
    "Harbour pressed at once.",
])
def test_once_conjunction_allowed_anywhere(press, text):
    assert words(press, text) == []


@pytest.mark.parametrize("text", [
    "A half-volley dropped wide.", "A half-chance came.", "Pressed before half-time.",
    "Late in the half Harbour pressed.", "Harbour pressed in the half as Northbridge FC tired.",
    "Harbour pressed in the first half of the match.",
])
def test_half_compounds_and_pitch_half_allowed(press, text):
    assert words(press, text) == []


@pytest.mark.parametrize("text", [
    "Harbour won half of the passes.", "Half the shots missed.", "Harbour won half of their duels.",
    "They had it in half.", "Harbour pressed half as often.", "Harbour won by half.", "A half.",
])
def test_half_fraction_rejected(press, text):
    assert "NUMBER_WORD:c1:half" in words(press, text)


@pytest.mark.parametrize("text", [
    "Harbour were under no pressure.", "There was no pressure.", "Harbour had no chance to settle.",
    "No way through.", "There was no time.", "No one moved.",
])
def test_no_idioms_allowed(press, text):
    assert words(press, text) == []


@pytest.mark.parametrize("text", ["They had no shots.", "No passes were completed.", "There were no goals."])
def test_no_plural_counted_noun_rejected(press, text):
    assert "NUMBER_WORD:c1:no" in words(press, text)


@pytest.mark.parametrize("phrase", [
    "front three", "front two", "back five", "back four", "back three", "third-man run", "double pivot",
    "double press", "one-two",
])
def test_more_exempt_football_terms(press, phrase):
    assert words(press, f"Harbour Athletic used the {phrase} well.") == []


@pytest.mark.parametrize("text,word", [
    ("They pressed in half.", "half"), ("Harbour went one-up.", "one"), ("A lone shot came.", "lone"),
    ("None of them connected.", "none"), ("A pair of tackles followed.", "pair"),
    ("One of their passes failed.", "one"),
])
def test_further_count_phrases_rejected(press, text, word):
    assert f"NUMBER_WORD:c1:{word}" in words(press, text)
