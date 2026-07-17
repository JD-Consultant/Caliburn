"""Secret-free OpenAI Responses eval profile (V3-4).

Hard invariants (stateless call, no SDK retry, disabled truncation) are typed as
`Literal` so they appear in the config dump/hash yet cannot be overridden by a
caller. API keys and environment secrets must never enter this model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import NonEmptyText


# SDK 2.46.0 accepted reasoning efforts; the V3-4 baseline only exercises "medium".
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]

DEFAULT_REQUESTED_MODEL = "gpt-5.6"
DEFAULT_ACCEPTED_RESOLVED_MODELS: tuple[str, ...] = ("gpt-5.6", "gpt-5.6-sol")


class OpenAIResponsesEvalConfig(DomainModel):
    schema_version: Literal["openai_responses_eval_config.v1"] = (
        "openai_responses_eval_config.v1"
    )
    provider: Literal["openai"] = "openai"
    requested_model: NonEmptyText = DEFAULT_REQUESTED_MODEL
    accepted_resolved_models: tuple[NonEmptyText, ...] = (
        DEFAULT_ACCEPTED_RESOLVED_MODELS
    )
    reasoning_mode: Literal["standard"] = "standard"
    reasoning_effort: ReasoningEffort = "medium"
    service_tier: Literal["default"] = "default"
    connect_timeout_seconds: float = Field(default=10.0, gt=0.0, le=60.0)
    store: Literal[False] = False
    background: Literal[False] = False
    stream: Literal[False] = False
    truncation: Literal["disabled"] = "disabled"
    sdk_max_retries: Literal[0] = 0
    contains_test_data: Literal[True] = True

    @model_validator(mode="after")
    def accepted_models_are_unique_and_sorted(self) -> "OpenAIResponsesEvalConfig":
        if not self.accepted_resolved_models:
            raise ValueError("accepted resolved models cannot be empty")
        if (
            tuple(sorted(set(self.accepted_resolved_models)))
            != self.accepted_resolved_models
        ):
            raise ValueError("accepted resolved models must be unique and sorted")
        return self

    @property
    def config_hash(self) -> str:
        return canonical_hash(self)
