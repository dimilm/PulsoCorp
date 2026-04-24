"""Schema for the red-flag scan agent."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FlagCategory = Literal[
    "accounting",
    "leverage",
    "regulatory",
    "concentration",
    "governance",
    "market",
    "other",
]
Severity = Literal["low", "med", "high"]


class RedFlag(BaseModel):
    category: FlagCategory
    severity: Severity
    title: str = Field(min_length=3, max_length=120)
    description: str
    evidence_hint: str = Field(
        description="Hinweis, woran man die Beobachtung im Datenbestand erkennen kann"
    )


class RedFlagResult(BaseModel):
    flags: list[RedFlag]
    overall_risk: Severity
    summary: str
