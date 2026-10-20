import json

from contracts.export_schemas import SCHEMA_DIR, render_schemas


def test_committed_schemas_are_fresh():
    rendered = render_schemas()
    assert set(rendered) == {
        "match_event.schema.json", "scenario_meta.schema.json", "api_error.schema.json",
        "snapshot.schema.json", "event_page.schema.json", "window_metrics.schema.json",
        "card_list.schema.json", "analyst_output.schema.json", "editor_review.schema.json",
        "story_output.schema.json", "insight.schema.json", "run_trace.schema.json",
        "match_info.schema.json",
    }
    for name, text in rendered.items():
        assert (SCHEMA_DIR / name).read_text() == text
        json.loads(text)
