"""Red-flag scan agent."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.context import build_stock_context
from app.agents.redflag.schema import RedFlagResult
from app.models.stock import Stock


class RedFlagAgent(BaseAgent):
    id = "redflag"
    name = "Red-Flag-Scan"
    description = (
        "Sucht systematisch nach Warnsignalen (Buchhaltung, Verschuldung, "
        "Regulatorik, Konzentration, Governance, Markt) und priorisiert sie "
        "nach Schweregrad."
    )
    prompt_path = Path(__file__).with_name("prompt.md")
    output_schema = RedFlagResult

    def build_input(self, db: Session, stock: Stock, **_: Any) -> dict[str, Any]:
        return build_stock_context(db, stock)
