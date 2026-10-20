"""Hand-written scripted model replies for the synthetic-01 moments."""

from contracts.agents import EvidenceBundle, MomentCandidate


# Hand-written model replies for the two synthetic-01 moments (keyed by card id).
_CLAIMS = {
    "press_surge@2058": [
        {"claim_id": "c1", "kind": "observation",
         "text": "Harbour Athletic made 16 pressures in Northbridge FC's end of the pitch in the last 60 s.",
         "evidence_event_ids": ["e024", "e025"], "metric": ("pressures_opp_half", "hba")},
        {"claim_id": "c2", "kind": "interpretation",
         "text": "Northbridge FC completed 6 of 10 passes, which is consistent with the pressure "
                 "making it hard to keep the ball.",
         "evidence_event_ids": ["e022", "e023"], "metric": ("pass_completion", "nbr")},
    ],
    "goal@2066": [
        {"claim_id": "c1", "kind": "observation",
         "text": "Harbour Athletic scored at 60:08 to make it 0-1.",
         "evidence_event_ids": ["e066"], "metric": None},
        {"claim_id": "c2", "kind": "interpretation",
         "text": "The goal followed an interception and a quick pass and carry, which suggests "
                 "a fast counter-attack.",
         "evidence_event_ids": ["e063", "e064", "e065"], "metric": None},
    ],
}

_VARIANTS = {
    "press_surge@2058": (
        ("Harbour pressed high", "In the last 60 s Harbour Athletic made 16 pressures in Northbridge FC's "
         "end of the pitch; Northbridge completed 6 of 10 passes (60%)."),
        ("Harbour hassled Northbridge", "Harbour Athletic kept closing Northbridge FC down near their own "
         "goal, which suggests Northbridge found it hard to keep the ball."),
    ),
    "goal@2066": (
        ("Harbour Athletic score", "Harbour Athletic scored at 60:08 to lead 0-1, after an interception and "
         "a quick carry that suggests a counter-attack."),
        ("Harbour hit them on the break", "Harbour Athletic won the ball back and scored quickly, which "
         "suggests a counter-attack (a fast attack right after winning the ball)."),
    ),
}


def hand_written(candidate: MomentCandidate, bundle: EvidenceBundle) -> dict[str, dict]:
    """Valid analyst / editor / storyteller outputs (as dicts) for a synthetic-01 candidate."""
    key = candidate.source_card.card_id
    ids = {"candidate_id": candidate.candidate_id, "snapshot_id": candidate.snapshot_id}
    claims = []
    for c in _CLAIMS[key]:
        refs = []
        if c["metric"]:
            name, team = c["metric"]
            refs.append({"name": name, "team_id": team})
        claims.append({"claim_id": c["claim_id"], "kind": c["kind"], "text": c["text"],
                       "evidence_event_ids": c["evidence_event_ids"], "metric_refs": refs})
    claim_ids = [c["claim_id"] for c in claims]
    (at, ab), (ct, cb) = _VARIANTS[key]
    return {
        "analyst": {**ids, "claims": claims},
        "editor": {**ids, "reviews": [{"claim_id": i, "verdict": "approved", "reason": "Supported by the cited events."}
                                      for i in claim_ids]},
        "storyteller": {**ids, "variants": [
            {"persona": "analyst", "title": at, "body": ab, "claim_ids": claim_ids},
            {"persona": "casual", "title": ct, "body": cb, "claim_ids": claim_ids},
        ]},
    }
