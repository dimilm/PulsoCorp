"""Schemas for the AI agent endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AgentInfoOut(BaseModel):
    id: str
    name: str
    description: str
    output_schema: dict[str, Any]


class AIRunOut(BaseModel):
    id: int
    isin: str
    agent_id: str
    created_at: datetime
    provider: str
    model: str
    status: str
    input_payload: dict[str, Any]
    result_payload: dict[str, Any] | None = None
    error_text: str | None = None
    cost_estimate: float | None = None
    duration_ms: int | None = None

    model_config = ConfigDict(from_attributes=True)


class AgentRunRequest(BaseModel):
    """Optional body parameters per agent. Currently only Tournament uses
    `peers` to override the auto-suggested bracket."""

    peers: list[str] | None = None
