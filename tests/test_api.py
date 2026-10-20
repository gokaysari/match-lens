import json
import shutil

import pytest
from conftest import ROOT, SCENARIO_DIR
from fastapi.testclient import TestClient

from app import create_app
from contracts.api import ApiError, MatchInfo, CardList, EventPage, Snapshot, WindowMetrics
from contracts.events import ScenarioMeta
from domain.ingest import IngestError

E066_SEQ = 2066


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(ROOT / "scenarios"))


def seqs():
    return [json.loads(l)["sequence"] for l in (SCENARIO_DIR / "events.jsonl").read_text().splitlines() if l]


def test_meta(client):
    r = client.get("/api/matches/synthetic-01/meta")
    assert r.status_code == 200
    assert MatchInfo.model_validate(r.json()).match_id == "synthetic-01"
    assert "moments" not in r.json() and "title" not in r.json()
    for line in (SCENARIO_DIR / "events.jsonl").read_text().splitlines():
        assert json.loads(line)["event_id"] not in r.text


def test_duplicate_match_id_refused(tmp_path):
    for n in ("a", "b"):
        shutil.copytree(SCENARIO_DIR, tmp_path / n)
    with pytest.raises(IngestError) as ei:
        create_app(tmp_path)
    assert ei.value.code == "DUPLICATE_MATCH"


def test_snapshot_at_goal(client):
    r = client.get(f"/api/matches/synthetic-01/snapshot?at_seq={E066_SEQ}")
    assert r.status_code == 200
    s = Snapshot.model_validate(r.json())
    assert (s.score.home, s.score.away) == (0, 1)
    assert s.snapshot_id == f"synthetic-01@{E066_SEQ}"


@pytest.mark.parametrize("ep", ["snapshot", "metrics", "cards"])
def test_at_seq_required(client, ep):
    r = client.get(f"/api/matches/synthetic-01/{ep}")
    assert r.status_code == 422 and ApiError.model_validate(r.json()).code == "INVALID_QUERY"


def test_events_default_range_returns_all(client):
    r = client.get("/api/matches/synthetic-01/events")
    assert r.status_code == 200
    page = EventPage.model_validate(r.json())
    assert len(page.events) == 97
    assert page.snapshot_id == f"synthetic-01@{max(seqs())}"


def test_events_range(client):
    page = EventPage.model_validate(
        client.get(f"/api/matches/synthetic-01/events?from_seq=2010&at_seq=2020").json())
    assert [e.sequence for e in page.events] == [s for s in seqs() if 2010 <= s <= 2020]
    assert page.snapshot_id == "synthetic-01@2020"


def test_events_from_after_at_is_422(client):
    r = client.get("/api/matches/synthetic-01/events?from_seq=2020&at_seq=2010")
    assert r.status_code == 422 and ApiError.model_validate(r.json()).code == "INVALID_QUERY"


def test_metrics(client):
    r = client.get(f"/api/matches/synthetic-01/metrics?at_seq={E066_SEQ}&window_s=30")
    assert r.status_code == 200
    wm = WindowMetrics.model_validate(r.json())
    assert wm.window_end_ms - wm.window_start_ms == 30_000 and len(wm.metrics) == 18


def test_metrics_default_window(client):
    wm = WindowMetrics.model_validate(
        client.get(f"/api/matches/synthetic-01/metrics?at_seq={E066_SEQ}").json())
    assert wm.window_end_ms - wm.window_start_ms == 60_000


def test_cards(client):
    cl = CardList.model_validate(client.get(f"/api/matches/synthetic-01/cards?at_seq={E066_SEQ}").json())
    assert [c.card_id for c in cl.cards][-1] == f"goal@{E066_SEQ}"
    early = CardList.model_validate(client.get("/api/matches/synthetic-01/cards?at_seq=2001").json())
    assert early.cards == ()


@pytest.mark.parametrize("ep", ["snapshot", "events", "metrics", "cards"])
def test_unknown_sequence_404(client, ep):
    r = client.get(f"/api/matches/synthetic-01/{ep}?at_seq=999999")
    assert r.status_code == 404
    assert ApiError.model_validate(r.json()).code == "UNKNOWN_SEQUENCE"


@pytest.mark.parametrize("ep", ["meta", "snapshot", "events", "metrics", "cards"])
def test_unknown_match_404(client, ep):
    r = client.get(f"/api/matches/nope/{ep}?at_seq=2001")
    assert r.status_code == 404
    assert ApiError.model_validate(r.json()).code == "UNKNOWN_MATCH"


@pytest.mark.parametrize("w", ["9", "601", "abc"])
def test_window_out_of_range_422(client, w):
    r = client.get(f"/api/matches/synthetic-01/metrics?window_s={w}")
    assert r.status_code == 422
    assert ApiError.model_validate(r.json()).code == "INVALID_QUERY"


def test_bad_at_seq_422(client):
    r = client.get("/api/matches/synthetic-01/snapshot?at_seq=abc")
    assert r.status_code == 422 and ApiError.model_validate(r.json()).code == "INVALID_QUERY"


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_non_get_is_405(client, method):
    r = getattr(client, method)("/api/matches/synthetic-01/snapshot")
    assert r.status_code == 405


def test_no_cors_headers(client):
    r = client.get("/api/matches/synthetic-01/meta", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_refuses_broken_scenario_dir(tmp_path):
    d = tmp_path / "broken"
    shutil.copytree(SCENARIO_DIR, d, ignore=shutil.ignore_patterns("__pycache__", "generate.py"))
    (d / "events.jsonl").write_text("not json\n")
    with pytest.raises(IngestError):
        create_app(tmp_path)


def test_refuses_empty_scenario_dir(tmp_path):
    d = tmp_path / "empty"
    shutil.copytree(SCENARIO_DIR, d, ignore=shutil.ignore_patterns("__pycache__", "generate.py"))
    (d / "events.jsonl").write_text("")
    with pytest.raises(IngestError) as ei:
        create_app(tmp_path)
    assert ei.value.code == "EMPTY_SCENARIO"


def test_env_scenarios_dir(monkeypatch):
    monkeypatch.setenv("MATCHLENS_SCENARIOS_DIR", str(ROOT / "scenarios"))
    assert TestClient(create_app()).get("/api/matches/synthetic-01/meta").status_code == 200


def test_405_carries_allow_header(client):
    r = client.post("/api/matches/synthetic-01/snapshot")
    assert r.status_code == 405 and ApiError.model_validate(r.json()).code == "METHOD_NOT_ALLOWED"
    assert "GET" in r.headers.get("allow", "")


def test_domain_error_mapping_and_internal(client, caplog):
    from domain.errors import DomainError
    app = create_app(ROOT / "scenarios")

    @app.get("/boom/{code}")
    def boom(code: str):
        raise DomainError(code, "x")

    c = TestClient(app, raise_server_exceptions=False)
    assert c.get("/boom/UNKNOWN_EVENT").status_code == 404
    assert c.get("/boom/FUTURE_EVENT_FORBIDDEN").status_code == 404
    with caplog.at_level("ERROR"):
        r = c.get("/boom/SOMETHING_NEW")
    assert r.status_code == 500 and ApiError.model_validate(r.json()).code == "INTERNAL"
    assert "SOMETHING_NEW" not in r.text
    assert any("SOMETHING_NEW" in rec.getMessage() and "x" in rec.getMessage()
               for rec in caplog.records)
