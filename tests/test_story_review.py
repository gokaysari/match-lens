"""Story review: the Evidence Editor checks the story against the approved claims; one storyteller repair."""

import asyncio
import copy
import json

import pytest
from conftest import SCENARIO_DIR

from agents.checks import check_story_review
from agents.model import Delay, FakeModelClient
from agents.prompts import load_prompt
from contracts.agents import InsightOutcome as Outcome
from contracts.agents import Role, StepStatus, StoryOutput, StoryReview
from domain.ingest import load_scenario
from workflow.candidates import build_candidates
from workflow.coordinator import Timeouts, run_moment


@pytest.fixture(scope="module")
def goal():
    meta, events = load_scenario(SCENARIO_DIR)
    return next(cb for cb in build_candidates(meta, events, events[-1].sequence)
                if cb[0].source_card.kind == "goal")


def run(coro):
    return asyncio.run(coro)


def ids(cand):
    return {"candidate_id": cand.candidate_id, "snapshot_id": cand.snapshot_id}


C1 = "Harbour Athletic scored at {t.e066} to make it {score}."
C3 = "Northbridge FC completed {pass_completion.nbr.frac} passes, down from {prev.pass_completion.nbr.frac}."


def analyst(cand):
    return {**ids(cand), "claims": [
        {"claim_id": "c1", "kind": "observation", "text": C1, "evidence_event_ids": ["e066"]},
        {"claim_id": "c3", "kind": "observation", "text": C3, "evidence_event_ids": ["e032", "e038"]}]}


def claim_review(cand):
    return {**ids(cand), "reviews": [{"claim_id": c, "verdict": "approved", "reason": "Supported."}
                                     for c in ("c1", "c3")]}


def story(cand, a_body, c_body):
    return {**ids(cand), "variants": [
        {"persona": "analyst", "title": "Harbour score", "body": a_body, "claim_ids": ["c1", "c3"]},
        {"persona": "casual", "title": "Harbour hit back", "body": c_body, "claim_ids": ["c1"]}]}


def review(cand, *rejected):
    rej = set(rejected)
    return {**ids(cand), "reviews": [
        {"persona": p, "verdict": "rejected" if p in rej else "approved", "reason": "checked"}
        for p in ("analyst", "casual")],
        "repair_hint": "Fix the swapped windows and the scorer." if rej else None}


def swapped(cand):  # the reviewer's failing case
    return story(cand,
                 "Northbridge FC completed {prev.pass_completion.nbr.frac} passes, up from "
                 "{pass_completion.nbr.frac}.",
                 "Northbridge FC scored to make it {score}.")


def correct(cand):
    return story(cand,
                 "Harbour Athletic scored at {t.e066} to make it {score}; Northbridge FC completed "
                 "{pass_completion.nbr.frac} passes, down from {prev.pass_completion.nbr.frac}.",
                 "Harbour Athletic scored to make it {score}.")


def client(cand, *, stories, reviews, analysts=None):
    m = FakeModelClient("fake")
    m.script(Role.analyst, json.dumps(analyst(cand)))
    m.script(Role.editor, json.dumps(claim_review(cand)))
    for s in stories:
        m.script(Role.storyteller, s if isinstance(s, (str, Exception, Delay)) else json.dumps(s))
    for r in reviews:
        m.script(Role.story_editor, r if isinstance(r, (str, Exception, Delay)) else json.dumps(r))
    return m


def roles(trace):
    return [(s.role, s.attempt, s.status) for s in trace.steps]


def test_swapped_story_is_not_published_but_correct_repair_is(goal):
    cand, bundle = goal
    m = client(cand, stories=[swapped(cand), correct(cand)],
               reviews=[review(cand, "analyst", "casual"), review(cand)])
    insight, trace = run(run_moment(cand, bundle, m))
    assert insight.outcome == Outcome.published
    assert roles(trace) == [
        (Role.analyst, 1, StepStatus.ok), (Role.editor, 1, StepStatus.ok),
        (Role.storyteller, 1, StepStatus.ok), (Role.story_editor, 1, StepStatus.rejected),
        (Role.storyteller, 2, StepStatus.ok), (Role.story_editor, 2, StepStatus.ok)]
    assert len(m.calls) == 6
    body = next(v.body for v in insight.variants if v.persona.value == "analyst")
    assert "down from 21 of 21" in body and "2 of 7" in body
    repair = json.loads(m.calls[4][2])["repair"]
    assert repair["review"]["repair_hint"] and repair["previous_output"]["variants"][0]["body"].startswith(
        "Northbridge FC completed {prev.")
    assert "STORY_REJECTED:analyst" in repair["check_codes"]


def test_swapped_story_still_rejected_after_repair_falls_back(goal):
    cand, bundle = goal
    m = client(cand, stories=[swapped(cand), swapped(cand)],
               reviews=[review(cand, "analyst"), review(cand, "analyst", "casual")])
    insight, trace = run(run_moment(cand, bundle, m))
    assert insight.outcome == Outcome.fallback and insight.claims == ()
    assert roles(trace)[-1] == (Role.story_editor, 2, StepStatus.rejected)
    assert "STORY_REJECTED:analyst" in trace.steps[-1].detail
    assert len(m.calls) == 6


def test_check_failure_on_story_triggers_the_one_repair_then_review(goal):
    cand, bundle = goal
    bad = correct(cand)
    bad["variants"][0]["body"] = "Harbour Athletic scored 1 goal."
    m = client(cand, stories=[bad, correct(cand)], reviews=[review(cand)])
    insight, trace = run(run_moment(cand, bundle, m))
    assert insight.outcome == Outcome.published
    assert roles(trace) == [
        (Role.analyst, 1, StepStatus.ok), (Role.editor, 1, StepStatus.ok),
        (Role.storyteller, 1, StepStatus.invalid), (Role.storyteller, 2, StepStatus.ok),
        (Role.story_editor, 1, StepStatus.ok)]
    repair = json.loads(m.calls[3][2])["repair"]
    assert "DIGIT_FORBIDDEN:analyst" in repair["check_codes"] and "previous_output" in repair
    assert "review" not in repair


def test_story_invalid_after_repair_falls_back(goal):
    cand, bundle = goal
    bad = correct(cand)
    bad["variants"][0]["body"] = "Harbour Athletic scored 1 goal."
    m = client(cand, stories=[bad, bad], reviews=[])
    insight, trace = run(run_moment(cand, bundle, m))
    assert insight.outcome == Outcome.fallback
    assert roles(trace)[-1] == (Role.storyteller, 2, StepStatus.invalid)


@pytest.mark.parametrize("bad,status", [
    ("not json", StepStatus.invalid),
    (json.dumps({"candidate_id": "x/y"}), StepStatus.invalid),
    (RuntimeError("boom"), StepStatus.error),
])
def test_story_editor_failure_never_publishes_unreviewed(goal, bad, status):
    cand, bundle = goal
    m = client(cand, stories=[correct(cand)], reviews=[bad])
    insight, trace = run(run_moment(cand, bundle, m))
    assert insight.outcome == Outcome.fallback
    assert roles(trace)[-1] == (Role.story_editor, 1, status)
    assert len(m.calls) == 4  # no repair for a broken reviewer


def test_story_editor_review_failing_checks_falls_back(goal):
    cand, bundle = goal
    rev = review(cand)
    rev["reviews"] = rev["reviews"][:1]
    m = client(cand, stories=[correct(cand)], reviews=[rev])
    insight, trace = run(run_moment(cand, bundle, m))
    assert insight.outcome == Outcome.fallback
    assert "MISSING_REVIEW:casual" in trace.steps[-1].detail


def test_story_editor_timeout_falls_back(goal):
    cand, bundle = goal
    m = client(cand, stories=[correct(cand)], reviews=[Delay(1.0, json.dumps(review(cand)))])
    t = Timeouts(story_editor_s=0.05)
    insight, trace = run(run_moment(cand, bundle, m, timeouts=t))
    assert insight.outcome == Outcome.fallback
    assert roles(trace)[-1] == (Role.story_editor, 1, StepStatus.timeout)


def test_budget_is_60s_with_per_role_timeouts():
    t = Timeouts()
    assert (t.total_s, t.analyst_s, t.editor_s, t.storyteller_s, t.story_editor_s) == (60, 20, 15, 15, 15)


def test_story_editor_input(goal):
    cand, bundle = goal
    m = client(cand, stories=[correct(cand)], reviews=[review(cand)])
    run(run_moment(cand, bundle, m))
    role, system, raw = m.calls[3]
    assert role == Role.story_editor and system == load_prompt(Role.story_editor)
    data = json.loads(raw)
    assert data["team_names"]["nbr"] == "Northbridge FC"
    c3 = next(c for c in data["approved_claims"] if c["claim_id"] == "c3")
    assert c3["kind"] == "observation" and c3["template"] == C3 and c3["rendered"] == "Northbridge FC completed 2 of 7 passes, down from 21 of 21."
    assert {f["key"] for f in data["facts"]} == {"t.e066", "score", "pass_completion.nbr.frac",
                                                  "prev.pass_completion.nbr.frac"}
    assert all(set(f) == {"key", "text", "meaning"} for f in data["facts"])
    v = next(v for v in data["variants"] if v["persona"] == "casual")
    assert v["body_template"] == "Harbour Athletic scored to make it {score}."
    assert v["body"] == "Harbour Athletic scored to make it 0-1."
    assert "events" not in data and "bundle" not in data


def test_story_editor_prompt():
    text = load_prompt(Role.story_editor)
    assert "wrong team" in text and "previous window" in text and "repair_hint" in text
    assert "persona" in text and "exactly one JSON object" in text


def test_check_story_review_codes(goal):
    cand, _ = goal
    st = StoryOutput.model_validate(correct(cand))

    def codes(mut):
        d = review(cand)
        mut(d)
        return check_story_review(StoryReview.model_validate(d), cand)

    assert codes(lambda d: None) == ()
    assert "ID_MISMATCH:snapshot_id" in codes(lambda d: d.update(snapshot_id="x@1"))
    assert "ID_MISMATCH:candidate_id" in codes(lambda d: d.update(candidate_id="x/y"))
    assert "MISSING_REVIEW:casual" in codes(lambda d: d.update(reviews=d["reviews"][:1]))
    assert "DUPLICATE_REVIEW:analyst" in codes(lambda d: d["reviews"][1].update(persona="analyst"))
    assert "REPAIR_HINT_MISSING" in codes(lambda d: d["reviews"][0].update(verdict="rejected"))
    assert "REPAIR_HINT_UNEXPECTED" in codes(lambda d: d.update(repair_hint="fix"))
    d = review(cand, "casual")
    assert check_story_review(StoryReview.model_validate(d), cand) == ()
    d["repair_hint"] = "  "
    assert check_story_review(StoryReview.model_validate(d), cand) == ("REPAIR_HINT_MISSING",)


def test_happy_path_makes_four_calls(goal):
    cand, bundle = goal
    m = client(cand, stories=[correct(cand)], reviews=[review(cand)])
    insight, _ = run(run_moment(cand, bundle, m))
    assert insight.outcome == Outcome.published and len(m.calls) == 4
    assert copy.deepcopy(insight) == insight


def test_repair_is_documented_in_the_writer_prompts():
    st = load_prompt(Role.storyteller)
    assert "repair" in st and "STORY_REJECTED" in st and "repair_hint" in st and "previous_output" in st
    assert "CODE:<claim_id>:<detail>" in load_prompt(Role.analyst)
