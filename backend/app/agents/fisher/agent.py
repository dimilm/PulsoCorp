"""Fisher checklist agent (15-Punkte-Checkliste)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.context import build_stock_context
from app.agents.fisher.schema import FisherResult
from app.models.stock import Stock


class FisherAgent(BaseAgent):
    id = "fisher"
    name = "Fisher-Checkliste"
    description = (
        "Bewertet das Unternehmen anhand der 15 klassischen Fisher-Fragen "
        "(Common Stocks and Uncommon Profits) und liefert pro Frage eine "
        "Bewertung 0-2 plus Gesamtscore und Verdict."
    )
    prompt_path = Path(__file__).with_name("prompt.md")
    output_schema = FisherResult

    def build_input(self, db: Session, stock: Stock, **_: Any) -> dict[str, Any]:
        return build_stock_context(db, stock)
