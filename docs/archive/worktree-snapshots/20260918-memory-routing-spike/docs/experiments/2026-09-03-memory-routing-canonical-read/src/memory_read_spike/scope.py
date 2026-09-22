"""Trusted scope and opaque canonical-message references for the spike."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID


_MESSAGE_REF = re.compile(
    r"^mref_v1_(?P<scope>[0-9a-f]{32})_(?P<message>[0-9a-f]{64})$"
)


@dataclass(frozen=True)
class TrustedReadScope:
    run_id: UUID
    document_id: UUID
    thread_id: str

    def __post_init__(self) -> None:
        if not self.thread_id.strip():
            raise ValueError("thread_id must not be empty")

    @property
    def semantic_namespace(self) -> tuple[str, ...]:
        return (
            "memory-routing-spike",
            str(self.run_id),
            str(self.document_id),
            "semantic",
        )

    @property
    def checkpoint_config(self) -> dict[str, dict[str, str]]:
        return {
            "configurable": {
                # LangGraph reserves checkpoint_ns for compiled subgraphs. Keep the
                # experiment scope in the framework's top-level thread key instead.
                "thread_id": (
                    f"memory-routing-spike:{self.run_id}:"
                    f"{self.document_id}:{self.thread_id}"
                ),
            }
        }


def _scope_fingerprint(scope: TrustedReadScope) -> str:
    material = f"{scope.run_id}\0{scope.document_id}\0{scope.thread_id}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def issue_message_ref(scope: TrustedReadScope, message_id: str) -> str:
    """Issue a stable opaque pointer without exposing trusted scope fields."""
    if not message_id:
        raise ValueError("message_id must not be empty")
    digest = hashlib.sha256(message_id.encode("utf-8")).hexdigest()
    return f"mref_v1_{_scope_fingerprint(scope)}_{digest}"


def classify_message_ref(
    scope: TrustedReadScope,
    message_ref: str,
) -> Literal["current_scope", "cross_scope", "malformed"]:
    match = _MESSAGE_REF.fullmatch(message_ref)
    if match is None:
        return "malformed"
    if match.group("scope") != _scope_fingerprint(scope):
        return "cross_scope"
    return "current_scope"
