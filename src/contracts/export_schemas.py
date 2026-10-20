"""Export JSON Schemas for the event and API contracts: python src/contracts/export_schemas.py"""

import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow running as a plain script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts.agents import AnalystOutput, EditorReview, Insight, RunTrace, StoryOutput
from contracts.api import MatchInfo, ApiError, CardList, EventPage, Snapshot, WindowMetrics
from contracts.events import MatchEvent, ScenarioMeta

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


def render_schemas() -> dict[str, str]:
    models = {
        "match_event.schema.json": MatchEvent,
        "scenario_meta.schema.json": ScenarioMeta,
        "api_error.schema.json": ApiError,
        "match_info.schema.json": MatchInfo,
        "snapshot.schema.json": Snapshot,
        "event_page.schema.json": EventPage,
        "window_metrics.schema.json": WindowMetrics,
        "card_list.schema.json": CardList,
        "analyst_output.schema.json": AnalystOutput,
        "editor_review.schema.json": EditorReview,
        "story_output.schema.json": StoryOutput,
        "insight.schema.json": Insight,
        "run_trace.schema.json": RunTrace,
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
