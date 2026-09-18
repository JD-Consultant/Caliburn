"""Secret-free receipts for the isolated live Memory read smoke."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LiveSmokeStatus(StrEnum):
    DRY_RUN = "dry_run"
    PREFLIGHT_BLOCKED = "preflight_blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class LiveUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    embedding_tokens: int = Field(default=0, ge=0)


class ModelVisibleTurn(BaseModel):
    """Model I/O evidence with provider-private reasoning payloads removed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_index: int = Field(ge=1)
    input: tuple[dict[str, Any], ...]
    output: dict[str, Any]


class LiveSmokeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    status: LiveSmokeStatus
    requested_model: str
    resolved_model: str | None = None
    provider: str | None = None
    requested_embedding_model: str
    resolved_embedding_model: str | None = None
    reasoning: Literal["medium"] = "medium"
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    usage: LiveUsage = Field(default_factory=LiveUsage)
    latency_ms: int = Field(default=0, ge=0)
    cost_usd: Decimal | None = Field(default=None, ge=0)
    cost_upper_bound_usd: Decimal | None = Field(default=None, ge=0)
    request_ids: tuple[str, ...] = ()
    reasoning_payloads_redacted: Literal[True] = True
    model_visible_turns: tuple[ModelVisibleTurn, ...] = ()
    final_answer: str | None = None
    error_code: str | None = None
