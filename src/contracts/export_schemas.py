"""Export JSON Schemas for the event contract: python src/contracts/export_schemas.py"""

import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow running as a plain script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.events import MatchEvent, ScenarioMeta

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


def render_schemas() -> dict[str, str]:
    models = {
        "match_event.schema.json": MatchEvent,
        "scenario_meta.schema.json": ScenarioMeta,
    }
    return {
        name: json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        for name, model in models.items()
    }


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in render_schemas().items():
        (SCHEMA_DIR / name).write_text(text)


if __name__ == "__main__":
    main()
