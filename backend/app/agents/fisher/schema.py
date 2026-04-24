"""Pydantic output schema for the Fisher checklist agent."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Order matters: it's the canonical sequence of Fisher's 15 questions and
# it's what the UI table renders top-to-bottom.
FISHER_QUESTION_IDS: tuple[str, ...] = (
    "growth_runway",
    "management_for_growth",
    "research_effectiveness",
    "sales_organisation",
    "profit_margins",
    "margin_improvement",
    "labour_relations",
    "executive_relations",
    "depth_of_management",
    "cost_analysis",
    "industry_position",
    "long_term_outlook",
    "capital_dilution",
    "management_candor",
    "management_integrity",
)

QuestionRating = Literal[0, 1, 2]
Verdict = Literal["strong", "neutral", "weak"]


class FisherQuestion(BaseModel):
    id: str = Field(description="Stable id matching one of FISHER_QUESTION_IDS")
    question: str = Field(description="Original Fisher question, German wording")
    rating: QuestionRating = Field(description="0 = weak, 1 = mixed, 2 = strong")
    rationale: str = Field(description="Kurze Begründung (1-3 Sätze)")


class FisherResult(BaseModel):
    questions: list[FisherQuestion]
    total_score: int = Field(ge=0, le=30, description="Sum of all 15 ratings (0-30)")
    verdict: Verdict
    summary: str
