"""Match Lens read-only replay API (contract: src/contracts/api.py). GET only, no CORS."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[2] / "src")
if _SRC not in sys.path:  # lets `uvicorn --app-dir services/api` find contracts/domain
    sys.path.insert(0, _SRC)

from fastapi import FastAPI  # noqa: E402, Query, Request
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

from contracts.api import ApiError, CardList, EventPage, Snapshot, WindowMetrics  # noqa: E402
from contracts.events import MatchEvent, ScenarioMeta  # noqa: E402
from domain.cards import compute_cards  # noqa: E402
from domain.errors import DomainError  # noqa: E402
from domain.ingest import load_scenario  # noqa: E402
from domain.metrics import WINDOW_S_DEFAULT, WINDOW_S_MAX, WINDOW_S_MIN, compute_window_metrics  # noqa: E402
from domain.snapshot import build_snapshot, snapshot_id, visible_events  # noqa: E402

DEFAULT_SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "scenarios"
_STATUS = {"UNKNOWN_MATCH": 404, "UNKNOWN_SEQUENCE": 404, "INVALID_QUERY": 422, "INVALID_WINDOW": 422}


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(ApiError(code=code, message=message).model_dump(), status_code=status)


def load_matches(directory: Path) -> dict[str, tuple[ScenarioMeta, list[MatchEvent]]]:
    """Load every scenario subdirectory once. Raises IngestError on any broken scenario."""
    matches: dict[str, tuple[ScenarioMeta, list[MatchEvent]]] = {}
    for sub in sorted(p for p in Path(directory).iterdir() if p.is_dir() and not p.name.startswith((".", "__"))):
        meta, events = load_scenario(sub)
        matches[meta.match_id] = (meta, events)
    return matches


def create_app(scenarios_dir: str | Path | None = None) -> FastAPI:
    directory = Path(scenarios_dir or os.environ.get("MATCHLENS_SCENARIOS_DIR") or DEFAULT_SCENARIOS_DIR)
    matches = load_matches(directory)

    app = FastAPI(title="Match Lens replay API", docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError):
        return _error(_STATUS.get(exc.code, 422), exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()))
        return _error(422, "INVALID_QUERY", f"{where}: {first.get('msg', 'invalid request')}")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        return _error(exc.status_code, code, str(exc.detail))

    def match(match_id: str) -> tuple[ScenarioMeta, list[MatchEvent]]:
        if match_id not in matches:
            raise DomainError("UNKNOWN_MATCH", f"unknown match {match_id}")
        return matches[match_id]

    def watermark(events: list[MatchEvent], at_seq: int | None) -> int:
        return events[-1].sequence if at_seq is None else at_seq

    R = {404: {"model": ApiError}, 422: {"model": ApiError}}

    @app.get("/api/matches/{match_id}/meta", response_model=ScenarioMeta, responses=R)
    def get_meta(match_id: str):
        return match(match_id)[0]

    @app.get("/api/matches/{match_id}/snapshot", response_model=Snapshot, responses=R)
    def get_snapshot(match_id: str, at_seq: int | None = None):
        meta, events = match(match_id)
        return build_snapshot(meta, events, watermark(events, at_seq))

    @app.get("/api/matches/{match_id}/events", response_model=EventPage, responses=R)
    def get_events(match_id: str, at_seq: int | None = None, from_seq: int | None = None):
        meta, events = match(match_id)
        w = watermark(events, at_seq)
        vis = visible_events(events, w)
        lo = events[0].sequence if from_seq is None else from_seq
        if lo > w:
            raise DomainError("INVALID_QUERY", "from_seq must be <= at_seq")
        return EventPage(match_id=meta.match_id, snapshot_id=snapshot_id(meta, w),
                         events=tuple(e for e in vis if e.sequence >= lo))

    @app.get("/api/matches/{match_id}/metrics", response_model=WindowMetrics, responses=R)
    def get_metrics(match_id: str, at_seq: int | None = None,
                    window_s: int = Query(WINDOW_S_DEFAULT, ge=WINDOW_S_MIN, le=WINDOW_S_MAX)):
        meta, events = match(match_id)
        return compute_window_metrics(meta, events, watermark(events, at_seq), window_s)

    @app.get("/api/matches/{match_id}/cards", response_model=CardList, responses=R)
    def get_cards(match_id: str, at_seq: int | None = None):
        meta, events = match(match_id)
        return compute_cards(meta, events, watermark(events, at_seq))

    return app


app = create_app()
