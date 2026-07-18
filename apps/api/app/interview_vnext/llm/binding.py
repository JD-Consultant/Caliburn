"""Runtime provider binding identity(ADR 0036 D2/D3;V3-5A §6.1)。

`ProviderBinding` 描述「某部署如何以指定 adapter/model/upstream/policy 執行一個
operation」。它是 hash-addressed immutable artifact:caller 不再自由填
provider/requested_model,executor 只憑 composition root/eval wiring 解析出的唯一
binding 執行。provider-specific config 不入 binding,只留 `provider_config_hash`;
真 config 由 adapter-specific composition 持有。
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.identifiers import (
    NonEmptyText,
    SemVer,
    Sha256,
    StableName,
)

from .operation import ContractIdentity


# Binding 是持久化 artifact,secret 樣式字串一律 reject(§6.1);pattern 與
# capture_export 的 export gate 對齊,兩道都 fail closed。
_SECRET_PATTERNS = (
    re.compile(r"sk-or-[A-Za-z0-9]"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"Authorization\s*[:=]"),
    re.compile(r"(?i)api[_-]?key"),
)

_ORDERED_TUPLE_FIELDS = (
    "accepted_gateway_models",
    "accepted_upstream_models",
    "required_capabilities",
)


class ProviderBindingDefinition(DomainModel):
    schema_version: Literal["provider_binding.v1"] = "provider_binding.v1"
    binding_id: StableName
    operation_name: StableName
    quality_profile: StableName
    adapter_id: StableName
    adapter_version: SemVer
    gateway_provider: StableName
    requested_model: NonEmptyText
    accepted_gateway_models: tuple[NonEmptyText, ...]
    upstream_provider: NonEmptyText | None
    upstream_endpoint: NonEmptyText | None
    accepted_upstream_models: tuple[NonEmptyText, ...]
    required_capabilities: tuple[StableName, ...]
    schema_projection_policy: ContractIdentity
    conformance_policy: ContractIdentity
    retry_owner: Literal["executor"] = "executor"
    provider_internal_retries: Literal[0] = 0
    storage_policy: StableName
    cache_policy: StableName
    reasoning_policy: StableName
    data_collection_policy: StableName
    provider_config_hash: Sha256

    @model_validator(mode="after")
    def binding_is_canonical(self) -> "ProviderBindingDefinition":
        encoded = canonical_json(self.model_dump(mode="json"))
        for pattern in _SECRET_PATTERNS:
            if pattern.search(encoded):
                raise ValueError(
                    f"binding contains a secret-like value: pattern {pattern.pattern}"
                )
        for field_name in _ORDERED_TUPLE_FIELDS:
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} entries must be unique")
            if tuple(sorted(values)) != values:
                raise ValueError(
                    f"{field_name} must be lexicographically sorted"
                )
        if not self.accepted_gateway_models:
            raise ValueError("accepted gateway models cannot be empty")
        if self.requested_model not in self.accepted_gateway_models:
            raise ValueError(
                "requested model must be in the accepted gateway models"
            )
        if self.gateway_provider == "openrouter" and (
            self.upstream_provider is None or self.upstream_endpoint is None
        ):
            raise ValueError(
                "an OpenRouter binding requires exact upstream provider and endpoint"
            )
        return self


class ProviderBinding(ProviderBindingDefinition):
    binding_hash: Sha256

    @model_validator(mode="after")
    def hash_matches_definition(self) -> "ProviderBinding":
        definition = ProviderBindingDefinition.model_validate(
            self.model_dump(exclude={"binding_hash"})
        )
        if canonical_hash(definition) != self.binding_hash:
            raise ValueError("provider binding hash mismatch")
        return self


def define_provider_binding(**values) -> ProviderBinding:
    definition = ProviderBindingDefinition(**values)
    return ProviderBinding(
        **definition.model_dump(), binding_hash=canonical_hash(definition)
    )
