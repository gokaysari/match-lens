"""Deterministic moment selection: one candidate per template card up to the watermark."""

from __future__ import annotations

from collections.abc import Sequence

from contracts.agents import EvidenceBundle, MomentCandidate
from contracts.events import MatchEvent, ScenarioMeta
from domain.cards import compute_cards
from domain.metrics import compute_window_metrics, window_events
from domain.snapshot import snapshot_id, visible_events
from workflow.facts import WINDOW_S, build_facts

BUNDLE_WINDOW_S = WINDOW_S  # facts and bundle metrics use the same window
BUNDLE_MAX_EVENTS = 60


def build_candidates(
    meta: ScenarioMeta, events: Sequence[MatchEvent], watermark_seq: int
) -> list[tuple[MomentCandidate, EvidenceBundle]]:
    out: list[tuple[MomentCandidate, EvidenceBundle]] = []
    for card in compute_cards(meta, events, watermark_seq).cards:
        if card.trigger_seq > watermark_seq:
            continue
        vis = visible_events(events, card.trigger_seq)
        _, _, window = window_events(vis, BUNDLE_WINDOW_S)
        evidence_ids = set(card.evidence_event_ids)
        keep = [e for e in vis if e.event_id in evidence_ids]
        room = max(0, BUNDLE_MAX_EVENTS - len(keep))
        extra = [e for e in window if e.event_id not in evidence_ids]
        chosen = keep + (extra[-room:] if room else [])
        chosen.sort(key=lambda e: e.sequence)
        snap = snapshot_id(meta, card.trigger_seq)
        cid = f"{meta.match_id}/{card.card_id}"
        cand = MomentCandidate(
            candidate_id=cid, match_id=meta.match_id, snapshot_id=snap,
            watermark_seq=card.trigger_seq, trigger_clock_ms=card.trigger_clock_ms,
            expires_at_ms=card.expires_at_ms, source_card=card,
        )
        bundle = EvidenceBundle(
            candidate_id=cid, snapshot_id=snap, events=tuple(chosen),
            metrics=compute_window_metrics(meta, events, card.trigger_seq, BUNDLE_WINDOW_S).metrics,
            facts=build_facts(meta, events, card, card.trigger_seq),
            team_names={t.id: t.name for t in meta.teams},
            player_names={p.id: p.name for p in meta.players},
        )
        out.append((cand, bundle))
    return out
