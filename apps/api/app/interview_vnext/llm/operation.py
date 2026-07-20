"""Versioned LLM operation definitions independent of provider/model selection."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import SemVer, Sha256, StableName


class ContractIdentity(DomainModel):
    """Stable identity for a schema, prompt, or context policy artifact."""

    name: StableName
    version: SemVer
    content_hash: Sha256


class RepairPolicy(DomainModel):
    schema_repair_attempts: int = Field(default=0, ge=0, le=1)
    semantic_repair_attempts: int = Field(default=0, ge=0, le=1)


class OperationDefinition(DomainModel):
    schema_version: Literal["llm_operation_definition.v1"] = "llm_operation_definition.v1"
    name: StableName
    version: SemVer
    input_contract: ContractIdentity
    output_contract: ContractIdentity
    prompt_template: ContractIdentity
    context_policy: ContractIdentity
    quality_profile: StableName
    timeout_ms: int = Field(ge=1, le=900_000)
    max_attempts: int = Field(default=1, ge=1, le=5)
    max_output_tokens: int = Field(ge=1)
    allowed_tools: tuple[StableName, ...] = ()
    repair_policy: RepairPolicy = RepairPolicy()
    safety_policy_flags: tuple[StableName, ...] = ()

    @model_validator(mode="after")
    def ordered_sets_are_canonical(self) -> "OperationDefinition":
        for field_name, values in (
            ("allowed_tools", self.allowed_tools),
            ("safety_policy_flags", self.safety_policy_flags),
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"{field_name} must be unique and lexicographically sorted")
        if self.repair_policy.schema_repair_attempts >= self.max_attempts:
            raise ValueError("schema repair attempts must be lower than max_attempts")
        return self


class OperationSpec(OperationDefinition):
    """Hash-addressed operation definition used by inference and Capture."""

    definition_hash: Sha256

    @model_validator(mode="after")
    def definition_hash_matches(self) -> "OperationSpec":
        definition = OperationDefinition.model_validate(
            self.model_dump(exclude={"definition_hash"})
        )
        if canonical_hash(definition) != self.definition_hash:
            raise ValueError("operation definition hash mismatch")
        return self


def define_operation(**values) -> OperationSpec:
    definition = OperationDefinition(**values)
    return OperationSpec(**definition.model_dump(), definition_hash=canonical_hash(definition))
