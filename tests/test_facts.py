"""Deterministic facts (the only values model text may quote) on synthetic-01."""

import re

import pytest
from conftest import SCENARIO_DIR

from contracts.agents import FACT_KEY_PATTERN, Fact
from domain.ingest import load_scenario
from workflow.candidates import build_candidates
from workflow.facts import build_facts


@pytest.fixture(scope="module")
def synth():
    return load_scenario(SCENARIO_DIR)


@pytest.fixture(scope="module")
def cards(synth):
    meta, events = synth
    return {c.source_card.kind.value: (c, b) for c, b in build_candidates(meta, events, events[-1].sequence)}


def facts_of(synth, cards, kind) -> dict[str, Fact]:
    meta, events = synth
    cand, _ = cards[kind]
    got = build_facts(meta, events, cand.source_card, cand.watermark_seq)
    assert isinstance(got, tuple)
    d = {f.key: f for f in got}
    assert len(d) == len(got), "duplicate keys"
    return d


PRESS_TEXTS = {
    # counts, window 58:52-59:52 (press@2058)
    "passes_attempted.nbr": "10", "passes_attempted.hba": "4",
    "passes_completed.nbr": "6", "passes_completed.hba": "1",
    "pressures.nbr": "0", "pressures.hba": "16",
    "pressures_opp_half.nbr": "0", "pressures_opp_half.hba": "16",
    "ball_wins.nbr": "3", "ball_wins.hba": "4",
    "high_ball_wins.nbr": "0", "high_ball_wins.hba": "4",
    "shots.nbr": "0", "shots.hba": "0", "goals.nbr": "0", "goals.hba": "0",
    # ratios
    "pass_completion.nbr.pct": "60%", "pass_completion.nbr.frac": "6 of 10",
    "pass_completion.nbr.num": "6", "pass_completion.nbr.den": "10",
    "pass_completion.hba.pct": "25%", "pass_completion.hba.frac": "1 of 4",
    "pass_completion.hba.num": "1", "pass_completion.hba.den": "4",
    "score": "0-0", "score.nbr": "0", "score.hba": "0",
    "clock": "59:52", "window": "58:52-59:52", "window_s": "60",
    "poss.team": "Harbour Athletic", "poss.actions": "2", "poss.duration_s": "1.5",
    "poss.start_dist_m": "22",
}


def test_press_facts_exact_texts(synth, cards):
    d = facts_of(synth, cards, "press_surge")
    got = {k: f.text for k, f in d.items() if not k.startswith("t.")}
    assert got == PRESS_TEXTS


def test_press_has_no_previous_window_before_period_start(synth, cards):
    # previous window 57:52-58:52 starts before the first event of the period (58:00)
    d = facts_of(synth, cards, "press_surge")
    assert not [k for k in d if k.startswith("prev.")]


def test_event_clock_facts_cover_card_evidence(synth, cards):
    d = facts_of(synth, cards, "press_surge")
    cand, _ = cards["press_surge"]
    t_keys = {k for k in d if k.startswith("t.")}
    assert t_keys == {f"t.{eid}" for eid in cand.source_card.evidence_event_ids}
    assert d["t.e024"].text == "58:59" and d["t.e024"].event_ids == ("e024",)
    assert d["t.e023"].text == "58:57"


def test_goal_facts_current_and_previous_window(synth, cards):
    d = facts_of(synth, cards, "goal")
    t = {k: f.text for k, f in d.items()}
    assert t["clock"] == "60:08" and t["window"] == "59:08-60:08" and t["window_s"] == "60"
    assert t["score"] == "0-1" and t["score.nbr"] == "0" and t["score.hba"] == "1"
    assert t["pass_completion.nbr.frac"] == "2 of 7" and t["pass_completion.nbr.pct"] == "29%"
    assert t["pressures.hba"] == "14"
    # previous window 58:08-59:08
    assert t["prev.pass_completion.nbr.frac"] == "21 of 21"
    assert t["prev.pass_completion.nbr.pct"] == "100%"
    assert t["prev.pressures.hba"] == "4" and t["prev.passes_attempted.hba"] == "0"
    assert d["prev.pressures.hba"].meaning.count("58:08-59:08") == 1
    # possession of the goal
    assert t["poss.team"] == "Harbour Athletic" and t["poss.actions"] == "4"
    assert t["poss.duration_s"] == "8.4" and t["poss.start_dist_m"] == "33"
    assert t["t.e066"] == "60:08"


def test_missing_ratio_stays_missing(synth, cards):
    d = facts_of(synth, cards, "goal")
    # Harbour had no pass attempts in the previous window: no ratio facts at all, count stays 0
    assert not [k for k in d if k.startswith("prev.pass_completion.hba")]
    assert d["prev.passes_attempted.hba"].text == "0"


def test_every_fact_is_well_formed(synth, cards):
    for kind in cards:
        d = facts_of(synth, cards, kind)
        for k, f in d.items():
            assert re.fullmatch(FACT_KEY_PATTERN, k) and k == k.lower()
            assert f.meaning.strip() and f.text.strip()


def test_meanings_are_explicit(synth, cards):
    d = facts_of(synth, cards, "press_surge")
    m = d["pressures_opp_half.hba"].meaning
    assert "Harbour Athletic" in m and "Northbridge FC's half" in m and "58:52-59:52" in m and "count" in m
    m = d["pass_completion.nbr.pct"].meaning
    assert "Northbridge FC" in m and "percent" in m and "58:52-59:52" in m
    assert "of attempted" in d["pass_completion.nbr.frac"].meaning
    assert "Harbour Athletic" in d["poss.start_dist_m"].meaning and "metres" in d["poss.start_dist_m"].meaning
    assert "seconds" in d["poss.duration_s"].meaning
    assert "home-away" in d["score"].meaning
    assert d["clock"].meaning and d["window_s"].meaning


def test_event_ids_trace_the_value(synth, cards):
    meta, events = synth
    d = facts_of(synth, cards, "press_surge")
    by_id = {e.event_id: e for e in events}
    pressures = d["pressures_opp_half.hba"].event_ids
    assert len(pressures) == 16 and all(by_id[i].type.value == "pressure" for i in pressures)
    assert len(d["pass_completion.nbr.frac"].event_ids) == 10
    assert d["poss.actions"].event_ids == ("e057", "e058")


def test_no_fact_uses_an_event_after_the_trigger(synth, cards):
    meta, events = synth
    seq = {e.event_id: e.sequence for e in events}
    for kind, (cand, _) in cards.items():
        d = facts_of(synth, cards, kind)
        assert all(seq[i] <= cand.watermark_seq for f in d.values() for i in f.event_ids)
        # identical when the future does not exist at all
        past = [e for e in events if e.sequence <= cand.watermark_seq]
        assert build_facts(meta, past, cand.source_card, cand.watermark_seq) == build_facts(
            meta, events, cand.source_card, cand.watermark_seq)


def test_bundle_carries_the_facts(cards):
    for cand, bundle in cards.values():
        assert bundle.facts and {f.key for f in bundle.facts} >= {"score", "clock", "window"}
