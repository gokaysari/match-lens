import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = ROOT / "scenarios" / "synthetic-01"


def base_event(**over):
    e = {
        "schema_version": "1.0",
        "match_id": "m1",
        "event_id": "e1",
        "sequence": 1,
        "period": 1,
        "event_time_ms": 0,
        "team_id": "nbr",
        "player_id": "nbr-07",
        "type": "pass",
        "outcome": "complete",
        "x": 50.0,
        "y": 34.0,
        "end_x": 55.0,
        "end_y": 30.0,
        "scenario_seed": 1,
        "synthetic": True,
    }
    e.update(over)
    return e


def base_meta(**over):
    m = {
        "schema_version": "1.0",
        "match_id": "m1",
        "scenario_seed": 1,
        "title": "t",
        "teams": [
            {"id": "nbr", "name": "Northbridge FC", "side": "home"},
            {"id": "hba", "name": "Harbour Athletic", "side": "away"},
        ],
        "players": [
            {"id": "nbr-07", "team_id": "nbr", "name": "N Seven", "shirt_number": 7},
            {"id": "hba-09", "team_id": "hba", "name": "H Nine", "shirt_number": 9},
        ],
        "moments": [
            {"key": "a", "description": "d", "first_event_id": "e1", "last_event_id": "e1"}
        ],
        "synthetic": True,
    }
    m.update(over)
    return m


def write_scenario(tmp_path: Path, events: list[dict], meta: dict | None = None) -> Path:
    (tmp_path / "meta.json").write_text(json.dumps(meta or base_meta()))
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return tmp_path


@pytest.fixture
def make_scenario(tmp_path):
    def _make(events, meta=None):
        return write_scenario(tmp_path, events, meta)

    return _make


def load_generator():
    spec = importlib.util.spec_from_file_location("gen_synth01", SCENARIO_DIR / "generate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
