"""Builders for committed, hash-addressed LLM operation documents."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.interview_vnext.domain.hashing import canonical_hash

from .context import TURN_INTERPRET_CONTEXT_POLICY_V1
from .operation import ContractIdentity, RepairPolicy, OperationSpec, define_operation
from .schema_exports import published_schema


PROMPT_DIR = Path(__file__).with_name("prompts")
OPERATION_DIR = Path(__file__).with_name("operations")
TURN_INTERPRET_PROMPT_PATH = PROMPT_DIR / "turn-interpret.1.0.0.md"


def raw_text_hash(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def turn_interpret_operation() -> OperationSpec:
    prompt = TURN_INTERPRET_PROMPT_PATH.read_text(encoding="utf-8")
    return define_operation(
        name="turn.interpret",
        version="1.0.0",
        input_contract=ContractIdentity(
            name="turn-interpret-input",
            version="1.0.0",
            content_hash=canonical_hash(
                published_schema("turn-interpret-input.v1.schema.json")
            ),
        ),
        output_contract=ContractIdentity(
            name="turn-interpret-output",
            version="1.0.0",
            content_hash=canonical_hash(
                published_schema("turn-interpret-output.v1.schema.json")
            ),
        ),
        prompt_template=ContractIdentity(
            name="turn-interpret",
            version="1.0.0",
            content_hash=raw_text_hash(prompt),
        ),
        context_policy=ContractIdentity(
            name=TURN_INTERPRET_CONTEXT_POLICY_V1.name,
            version=TURN_INTERPRET_CONTEXT_POLICY_V1.version,
            content_hash=TURN_INTERPRET_CONTEXT_POLICY_V1.policy_hash,
        ),
        quality_profile="turn-interpret-verifier-v1",
        timeout_ms=120_000,
        max_attempts=3,
        max_output_tokens=TURN_INTERPRET_CONTEXT_POLICY_V1.reserved_output_tokens,
        allowed_tools=(),
        repair_policy=RepairPolicy(
            schema_repair_attempts=1,
            semantic_repair_attempts=0,
        ),
        safety_policy_flags=("no-chain-of-thought", "untrusted-input-boundary"),
    )


def operation_documents() -> dict[str, OperationSpec]:
    return {"turn-interpret.1.0.0.json": turn_interpret_operation()}
