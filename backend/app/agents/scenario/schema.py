"""Schema for the Bull / Base / Bear scenario agent."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class Scenario(BaseModel):
    assumptions: list[str] = Field(min_length=1, max_length=8)
    target_price: float
    probability: float = Field(ge=0, le=1)


class ScenarioResult(BaseModel):
    bull: Scenario
    base: Scenario
    bear: Scenario
    expected_value: float
    expected_return_pct: float
    time_horizon_years: int = Field(ge=1, le=10)
    summary: str

    @model_validator(mode="after")
    def _probabilities_sum_to_one(self) -> "ScenarioResult":
        total = self.bull.probability + self.base.probability + self.bear.probability
        # Allow 5% slack so the LLM is not forced into perfect arithmetic.
        if not 0.95 <= total <= 1.05:
            raise ValueError(
                f"Wahrscheinlichkeiten müssen zusammen ca. 1.0 ergeben, sind aber {total:.2f}"
            )
        return self
