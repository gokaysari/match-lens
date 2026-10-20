"""Output of the single-agent baseline: analysis and story in one reply (evaluation only)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from contracts.agents import AnalystOutput, StoryOutput


class SingleAgentOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    analysis: AnalystOutput
    story: StoryOutput
