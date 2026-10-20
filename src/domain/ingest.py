"""Load and strictly validate a synthetic scenario. Nothing is dropped or repaired."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from contracts.events import ON_BALL_TYPES, VALID_OUTCOMES, EventType, MatchEvent, ScenarioMeta


PERIOD_2_START_MS = 2_700_000


class IngestError(Exception):
    """Explicit ingest failure carrying a machine-readable code and offending event ids."""

    def __init__(self, code: str, message: str, event_ids: list[str] | None = None):
        self.code = code
        self.event_ids = list(event_ids or [])
        super().__init__(f"{code}: {message} (event_ids={self.event_ids})")


def _details(exc: ValidationError, limit: int = 5) -> str:
    errs = [f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in exc.errors()]
    more = f"; +{len(errs) - limit} more" if len(errs) > limit else ""
    return "; ".join(errs[:limit]) + more


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise IngestError("MISSING_FILE", f"{path} does not exist") from exc
    except UnicodeDecodeError as exc:
        raise IngestError("INVALID_ENCODING", f"{path.name} is not valid UTF-8") from exc


def _load_meta(path: Path) -> ScenarioMeta:
    try:
        meta = ScenarioMeta.model_validate(json.loads(_read(path)))
    except json.JSONDecodeError as exc:
        raise IngestError("INVALID_META", f"meta.json is not valid JSON: {exc.msg}") from exc
    except ValidationError as exc:
        raise IngestError("INVALID_META", f"meta.json failed validation: {_details(exc)}") from exc

    team_ids = [t.id for t in meta.teams]
    if len(set(team_ids)) != len(team_ids):
        raise IngestError("INVALID_META", "duplicate team ids")
    if sorted(t.side for t in meta.teams) != ["away", "home"]:
        raise IngestError("INVALID_META", "exactly one home and one away team are required")
    player_ids = [p.id for p in meta.players]
    if len(set(player_ids)) != len(player_ids):
        raise IngestError("INVALID_META", "duplicate player ids")
    keys = [m.key for m in meta.moments]
    if len(set(keys)) != len(keys):
        raise IngestError("INVALID_META", "duplicate moment keys")
    shirts = [(p.team_id, p.shirt_number) for p in meta.players]
    if len(set(shirts)) != len(shirts):
        raise IngestError("INVALID_META", "duplicate shirt numbers within a team")
    for p in meta.players:
        if p.team_id not in team_ids:
            raise IngestError("INVALID_META", f"player {p.id} references unknown team {p.team_id}")
    return meta


def _parse_events(path: Path) -> list[MatchEvent]:
    events: list[MatchEvent] = []
    for lineno, line in enumerate(_read(path).splitlines(), start=1):
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
                f"line {lineno} failed schema validation: {_details(exc)}",
                [eid] if isinstance(eid, str) else [],
            ) from exc
    return events


def load_scenario(directory: str | Path) -> tuple[ScenarioMeta, list[MatchEvent]]:
    d = Path(directory)
    meta = _load_meta(d / "meta.json")
    events = _parse_events(d / "events.jsonl")
    if not events:
        raise IngestError("EMPTY_SCENARIO", "events.jsonl contains no events")

    teams = {t.id for t in meta.teams}
    players = {p.id: p.team_id for p in meta.players}
    seen: dict[str, MatchEvent] = {}
    prev: MatchEvent | None = None
    poss_team: dict[str, str] = {}
    last_poss: str | None = None
    poss_seen: set[str] = set()
    for e in events:
        if e.match_id != meta.match_id:
            raise IngestError("MATCH_ID_MISMATCH", f"expected {meta.match_id}, got {e.match_id}", [e.event_id])
        if e.event_id in seen:
            raise IngestError("DUPLICATE_EVENT_ID", "event_id appears more than once", [e.event_id])
        seen[e.event_id] = e
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
        if e.scenario_seed != meta.scenario_seed:
            raise IngestError(
                "SEED_MISMATCH", f"expected {meta.scenario_seed}, got {e.scenario_seed}", [e.event_id]
            )
        if e.period == 2 and e.event_time_ms < PERIOD_2_START_MS:
            raise IngestError(
                "PERIOD_CLOCK_MISMATCH",
                f"period 2 event_time_ms {e.event_time_ms} < {PERIOD_2_START_MS}",
                [e.event_id],
            )
        if e.type in VALID_OUTCOMES and e.outcome is None:
            raise IngestError("MISSING_OUTCOME", f"type '{e.type.value}' requires an outcome", [e.event_id])
        if e.type in ON_BALL_TYPES and e.player_id is None:
            raise IngestError("MISSING_PLAYER", f"type '{e.type.value}' requires a player", [e.event_id])
        if e.team_id not in teams:
            raise IngestError("UNKNOWN_TEAM", f"team {e.team_id} not in meta", [e.event_id])
        if e.player_id is not None and players.get(e.player_id) != e.team_id:
            raise IngestError(
                "UNKNOWN_PLAYER", f"player {e.player_id} not on team {e.team_id} in meta", [e.event_id]
            )
        if e.recipient_player_id is not None:
            if e.recipient_player_id not in players:
                raise IngestError("UNKNOWN_PLAYER", f"recipient {e.recipient_player_id} not in meta", [e.event_id])
            if players[e.recipient_player_id] != e.team_id:
                raise IngestError("INVALID_EVENT", "recipient is not a teammate", [e.event_id])
        if e.pressured_player_id is not None:
            if e.pressured_player_id not in players:
                raise IngestError("UNKNOWN_PLAYER", f"pressured player {e.pressured_player_id} not in meta", [e.event_id])
            if players[e.pressured_player_id] == e.team_id:
                raise IngestError("INVALID_EVENT", "pressured player is not an opponent", [e.event_id])
        if not meta.segment_start_ms <= e.event_time_ms <= meta.segment_end_ms:
            raise IngestError(
                "EVENT_OUTSIDE_SEGMENT",
                f"event_time_ms {e.event_time_ms} outside [{meta.segment_start_ms}, {meta.segment_end_ms}]",
                [e.event_id],
            )
        if e.type in ON_BALL_TYPES and e.possession_id is not None:
            pid = e.possession_id
            if poss_team.setdefault(pid, e.team_id) != e.team_id:
                raise IngestError("POSSESSION_INCONSISTENT", f"possession {pid} used by two teams", [e.event_id])
            if last_poss is not None and pid != last_poss and pid in poss_seen:
                raise IngestError("POSSESSION_INCONSISTENT", f"possession {pid} reappears", [e.event_id])
            poss_seen.add(pid)
            last_poss = pid
        prev = e

    for m in meta.moments:
        for eid in (m.first_event_id, m.last_event_id):
            if eid not in seen:
                raise IngestError("UNKNOWN_MOMENT_EVENT", f"moment {m.key} references unknown event", [eid])
        if seen[m.first_event_id].sequence > seen[m.last_event_id].sequence:
            raise IngestError(
                "UNKNOWN_MOMENT_EVENT",
                f"moment {m.key} first event is after its last event",
                [m.first_event_id, m.last_event_id],
            )
    return meta, events
