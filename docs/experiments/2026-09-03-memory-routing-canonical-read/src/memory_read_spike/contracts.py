"""Model-visible contracts for the isolated memory read experiment."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SearchSemanticMemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)


class ReadConversationContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_ref: str = Field(min_length=1)


class MemoryHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    content: str
    message_refs: tuple[str, ...]


class SearchSemanticMemoryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memories: tuple[MemoryHit, ...]


class ConversationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: Literal["employee", "consultant"]
    text: str


class ReadConversationContextResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: tuple[ConversationItem, ...]
