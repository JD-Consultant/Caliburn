"""Typed transient state and trusted runtime context for the read graph."""

from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from memory_read_spike.runtime import SpikeRuntime
from memory_read_spike.scope import TrustedReadScope


def merge_disclosed_refs(left: set[str], right: set[str]) -> set[str]:
    return left | right


class MemoryReadState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    disclosed_message_refs: Annotated[set[str], merge_disclosed_refs]
    model_steps: Annotated[int, operator.add]


@dataclass(frozen=True)
class MemoryReadContext:
    scope: TrustedReadScope
    canonical_runtime: SpikeRuntime
