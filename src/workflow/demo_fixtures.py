"""Hand-written model replies for the two synthetic-01 moments: the one copy used by the
smoke demo (`workflow.run_fake`) and by the tests. Numbers appear only as {fact} placeholders."""

from __future__ import annotations

from contracts.agents import EvidenceBundle, MomentCandidate

# keyed by card id
_CLAIMS = {
    "press_surge@2058": [
        {"claim_id": "c1", "kind": "observation",
         "text": "Harbour Athletic made {pressures_opp_half.hba} pressures in Northbridge FC's half "
                 "in the last {window_s} s.",
         "evidence_event_ids": ["e024", "e025"]},
        {"claim_id": "c2", "kind": "interpretation",
         "text": "Northbridge FC completed {pass_completion.nbr.frac} passes, which is consistent with "
                 "the pressure making it hard to keep the ball.",
         "evidence_event_ids": ["e022", "e023"]},
    ],
    "goal@2066": [
        {"claim_id": "c1", "kind": "observation",
         "text": "Harbour Athletic scored at {t.e066} to make it {score}.",
         "evidence_event_ids": ["e066"]},
        {"claim_id": "c2", "kind": "interpretation",
         "text": "The goal followed an interception, a quick pass and a carry in a move lasting "
                 "{poss.duration_s} s, which suggests a fast counter-attack.",
         "evidence_event_ids": ["e063", "e064", "e065"]},
    ],
}

_VARIANTS = {
    "press_surge@2058": (
        ("Harbour pressed high",
         "Harbour Athletic made {pressures_opp_half.hba} pressures in Northbridge FC's half in the last "
         "{window_s} s; Northbridge completed {pass_completion.nbr.frac} passes."),
        ("Harbour hassled Northbridge",
         "Harbour Athletic kept closing Northbridge FC down, which suggests Northbridge found it hard "
         "to keep the ball."),
    ),
    "goal@2066": (
        ("Harbour Athletic score",
         "Harbour Athletic scored at {t.e066} to lead {score}, after an interception and a quick carry "
         "that suggests a counter-attack."),
        ("Harbour hit them on the break",
         "Harbour Athletic won the ball back and scored quickly, which suggests a counter-attack "
         "(a fast attack right after winning the ball)."),
    ),
}


def hand_written(candidate: MomentCandidate, bundle: EvidenceBundle) -> dict[str, dict]:
    """Valid analyst / editor / storyteller / story-review outputs (as dicts) for a synthetic-01 candidate."""
    key = candidate.source_card.card_id
    ids = {"candidate_id": candidate.candidate_id, "snapshot_id": candidate.snapshot_id}
    claims = [dict(c) for c in _CLAIMS[key]]
    claim_ids = [c["claim_id"] for c in claims]
    (at, ab), (ct, cb) = _VARIANTS[key]
    return {
        "analyst": {**ids, "claims": claims},
        "editor": {**ids, "reviews": [{"claim_id": i, "verdict": "approved",
                                       "reason": "Supported by the cited events."} for i in claim_ids]},
        "storyteller": {**ids, "variants": [
            {"persona": "analyst", "title": at, "body": ab, "claim_ids": claim_ids},
            {"persona": "casual", "title": ct, "body": cb, "claim_ids": claim_ids},
        ]},
        "story_review": {**ids, "reviews": [{"persona": p, "verdict": "approved",
                                             "reason": "Restates only what the claims say."}
                                            for p in ("analyst", "casual")]},
    }
