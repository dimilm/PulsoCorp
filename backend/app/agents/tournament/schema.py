"""Pydantic schema for the peer-tournament agent."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Categories LLM judges per match. Order matters for the UI table.
TOURNAMENT_CATEGORIES: tuple[str, ...] = (
    "moat",
    "growth",
    "profitability",
    "balance_sheet",
    "valuation",
    "management",
    "risk",
)

CategoryScores = dict[str, int]  # 1-3 per side


class CompanyProfile(BaseModel):
    """Lean snapshot fed to the LLM for both sides of every match."""

    isin: str
    name: str
    sector: str | None = None
    metrics: dict[str, float | None]


class MatchScore(BaseModel):
    a: int = Field(ge=1, le=3)
    b: int = Field(ge=1, le=3)


class Match(BaseModel):
    a: str = Field(description="ISIN der Aktie A")
    b: str = Field(description="ISIN der Aktie B")
    category_scores: dict[str, MatchScore]
    winner: str = Field(description="ISIN des Match-Siegers")
    rationale: str


class TournamentResult(BaseModel):
    rounds: list[list[Match]] = Field(
        description="Liste von Runden; jede Runde ist eine Liste von Matches"
    )
    winner_isin: str
    winner_rationale: str
    summary: str


# A single match-call returns just the match payload. The agent assembles the
# bracket from many of these calls.
class SingleMatch(BaseModel):
    category_scores: dict[str, MatchScore]
    winner: Literal["a", "b"]
    rationale: str
