"""Strict structured output contract for the Planner Agent."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RoutingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Literal["research", "plan_only"]
    reason: str = Field(min_length=1, max_length=400)
    steps: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_plan(self) -> "RoutingDecision":
        if any(not step.strip() or len(step) > 300 for step in self.steps):
            raise ValueError("Plan steps must contain 1-300 nonblank characters.")
        if self.route == "plan_only" and not self.steps:
            raise ValueError("Plan-only routing requires at least one step.")
        return self
