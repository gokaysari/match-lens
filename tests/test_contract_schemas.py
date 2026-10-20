import json

from contracts.export_schemas import SCHEMA_DIR, render_schemas


def test_committed_schemas_are_fresh():
    rendered = render_schemas()
    assert set(rendered) == {"match_event.schema.json", "scenario_meta.schema.json"}
    for name, text in rendered.items():
        assert (SCHEMA_DIR / name).read_text() == text
        json.loads(text)
