"""Singleton registry of all available AI agents.

The registry is built lazily so the agent modules can import from the
registry (e.g. via `app.agents`) without triggering circular imports.
"""
from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.fisher.agent import FisherAgent
from app.agents.redflag.agent import RedFlagAgent
from app.agents.scenario.agent import ScenarioAgent
from app.agents.tournament.agent import TournamentAgent


def _build_registry() -> dict[str, BaseAgent]:
    instances: list[BaseAgent] = [
        FisherAgent(),
        TournamentAgent(),
        ScenarioAgent(),
        RedFlagAgent(),
    ]
    return {agent.id: agent for agent in instances}


AGENTS: dict[str, BaseAgent] = _build_registry()


def list_agents() -> list[BaseAgent]:
    return list(AGENTS.values())


def get_agent(agent_id: str) -> BaseAgent | None:
    return AGENTS.get(agent_id)
