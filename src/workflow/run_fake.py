"""Smoke demo (not a test): run the synthetic-01 candidates through the coordinator with a
scripted fake model. Usage: PYTHONPATH=src python -m workflow.run_fake"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from agents.model import FakeModelClient
from contracts.agents import Persona, Role
from domain.ingest import load_scenario
from workflow.candidates import build_candidates
from workflow.coordinator import run_moment
from workflow.demo_fixtures import hand_written

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "scenarios" / "synthetic-01"


async def main() -> None:
    meta, events = load_scenario(SCENARIO_DIR)
    for cand, bundle in build_candidates(meta, events, events[-1].sequence):
        hw = hand_written(cand, bundle)
        model = FakeModelClient("fake", {Role.analyst: [json.dumps(hw["analyst"])],
                                         Role.editor: [json.dumps(hw["editor"])],
                                         Role.storyteller: [json.dumps(hw["storyteller"])],
                                         Role.story_editor: [json.dumps(hw["story_review"])]})
        insight, _ = await run_moment(cand, bundle, model)
        titles = " | ".join(f"{v.persona.value}: {v.title}" for v in insight.variants)
        print(f"{insight.insight_id} {insight.outcome.value} {titles}")
        analyst = next(v for v in insight.variants if v.persona == Persona.analyst)
        print(f"  analyst body: {analyst.body}")


if __name__ == "__main__":
    asyncio.run(main())
