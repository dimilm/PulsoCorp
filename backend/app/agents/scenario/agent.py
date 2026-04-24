"""Bull / Base / Bear scenario agent."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.context import build_stock_context
from app.agents.scenario.schema import ScenarioResult
from app.models.stock import Stock


class ScenarioAgent(BaseAgent):
    id = "scenario"
    name = "Bull/Base/Bear-Szenario"
    description = (
        "Modelliert drei Zukunftsszenarien (Bull, Base, Bear) mit Annahmen, "
        "Kurszielen und Eintrittswahrscheinlichkeiten. Liefert einen "
        "Erwartungswert und die erwartete Rendite über einen "
        "Anlagehorizont von 1–10 Jahren."
    )
    prompt_path = Path(__file__).with_name("prompt.md")
    output_schema = ScenarioResult

    def build_input(self, db: Session, stock: Stock, **_: Any) -> dict[str, Any]:
        return build_stock_context(db, stock)
