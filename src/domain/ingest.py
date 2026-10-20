"""Load and strictly validate a synthetic scenario. Nothing is dropped or repaired."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from contracts.events import MatchEvent, ScenarioMeta


class IngestError(Exception):
    """Explicit ingest failure carrying a machine-readable code and offending event ids."""

    def __init__(self, code: str, message: str, event_ids: list[str] | None = None):
        self.code = code
        self.event_ids = list(event_ids or [])
        super().__init__(f"{code}: {message} (event_ids={self.event_ids})")


def _parse_events(path: Path) -> list[MatchEvent]:
    events: list[MatchEvent] = []
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IngestError("INVALID_EVENT", f"line {lineno} is not valid JSON: {exc.msg}") from exc
        eid = raw.get("event_id") if isinstance(raw, dict) else None
        try:
            events.append(MatchEvent.model_validate(raw))
        except ValidationError as exc:
            raise IngestError(
                "INVALID_EVENT",
                f"line {lineno} failed schema validation: {exc.error_count()} error(s)",
                [eid] if isinstance(eid, str) else [],
            ) from exc
    return events


def load_scenario(directory: str | Path) -> tuple[ScenarioMeta, list[MatchEvent]]:
    d = Path(directory)
    try:
        meta = ScenarioMeta.model_validate_json((d / "meta.json").read_text())
    except ValidationError as exc:
        raise IngestError("INVALID_META", f"meta.json failed validation: {exc.error_count()} error(s)") from exc
    events = _parse_events(d / "events.jsonl")

    teams = {t.id for t in meta.teams}
    players = {p.id: p.team_id for p in meta.players}
    seen: set[str] = set()
    prev: MatchEvent | None = None
    for e in events:
        if e.match_id != meta.match_id:
            raise IngestError("MATCH_ID_MISMATCH", f"expected {meta.match_id}, got {e.match_id}", [e.event_id])
        if e.event_id in seen:
            raise IngestError("DUPLICATE_EVENT_ID", "event_id appears more than once", [e.event_id])
        seen.add(e.event_id)
        if prev is not None:
            if e.sequence <= prev.sequence:
                raise IngestError(
                    "NON_MONOTONIC_SEQUENCE",
                    f"sequence {e.sequence} does not follow {prev.sequence}",
                    [e.event_id],
                )
            if e.period < prev.period:
                raise IngestError("CLOCK_REGRESSION", "period decreased", [e.event_id])
            if e.period == prev.period and e.event_time_ms < prev.event_time_ms:
                raise IngestError(
                    "CLOCK_REGRESSION",
                    f"event_time_ms {e.event_time_ms} < {prev.event_time_ms} within period {e.period}",
                    [e.event_id],
                )
        if e.team_id not in teams:
            raise IngestError("UNKNOWN_TEAM", f"team {e.team_id} not in meta", [e.event_id])
        if e.player_id is not None and players.get(e.player_id) != e.team_id:
            raise IngestError(
                "UNKNOWN_PLAYER", f"player {e.player_id} not on team {e.team_id} in meta", [e.event_id]
            )
        prev = e
    return meta, events
