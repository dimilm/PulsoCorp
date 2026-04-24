"""AI agent registry.

Each agent encapsulates a single evaluation method (Fisher checklist, peer
tournament, bull/bear scenario, red-flag scan). The registry below is the
single source of truth consumed by the API and the UI.
"""
from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.fisher.agent import FisherAgent
from app.agents.redflag.agent import RedFlagAgent
from app.agents.registry import AGENTS, get_agent, list_agents
from app.agents.scenario.agent import ScenarioAgent
from app.agents.tournament.agent import TournamentAgent

__all__ = [
    "AGENTS",
    "BaseAgent",
    "FisherAgent",
    "RedFlagAgent",
    "ScenarioAgent",
    "TournamentAgent",
    "get_agent",
    "list_agents",
]
