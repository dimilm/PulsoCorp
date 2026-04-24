from dataclasses import dataclass


@dataclass
class AIEvaluation:
    fundamental_score: int
    moat_score: int
    moat_text: str
    fair_value_dcf: float
    fair_value_nav: float
    recommendation: str
    recommendation_reason: str
    risk_notes: str
    estimated_cost: float
    # True when the value was produced by a deterministic fallback heuristic
    # rather than by a real LLM response. Persisted in `field_sources` as
    # `"ki_fallback"` so the UI can render a "heuristisch"-Badge.
    is_fallback: bool = False


class AIProvider:
    async def evaluate(self, payload: dict) -> AIEvaluation:
        raise NotImplementedError
