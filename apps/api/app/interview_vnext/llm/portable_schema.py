"""Portable strict-output JSON Schema projection and lint.

Provider constrained decoding is intentionally treated as a syntax boundary.
Pydantic remains the authority for constraints that are removed here.

V3-5A §6.2:projection 不再只回 dict——每一筆 removed/rewritten constraint 都
記進 hash-addressed `SchemaProjectionReport`(RFC 6901 pointer + value hash),
prompt obligations 由 policy 固定 tuple 提供;`portable_strict_output_schema()`
留作 thin compatibility helper,active executor/catalog 必須用有 report 的版本。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import (
    NonEmptyText,
    SemVer,
    Sha256,
    StableName,
)


_ANNOTATION_KEYWORDS = frozenset({"$id", "$schema", "description", "title"})
_STRUCTURAL_KEYWORDS = frozenset(
    {
        "$defs",
        "$ref",
        "additionalProperties",
        "anyOf",
        "enum",
        "items",
        "properties",
        "required",
        "type",
    }
)
_UNSUPPORTED_CONSTRAINTS = frozenset(
    {
        "default",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "maxItems",
        "maxLength",
        "maximum",
        "minItems",
        "minLength",
        "minimum",
        "multipleOf",
        "pattern",
        "uniqueItems",
    }
)
_JSON_TYPES = frozenset(
    {"array", "boolean", "integer", "null", "number", "object", "string"}
)


class ProviderSchemaPortabilityError(ValueError):
    """A provider-facing schema is outside the approved portable subset."""


# ── Projection policy(hash-addressed;prompt obligations 的唯一來源)─────────

# RFC 6901;root 為空字串,每個 reference token 內 "~"→"~0"、"/"→"~1"。
JsonPointer = Annotated[str, Field(pattern=r"^(?:/(?:[^~/]|~0|~1)*)*$")]


class SchemaProjectionPolicyDefinition(DomainModel):
    schema_version: Literal["schema_projection_policy.v1"] = (
        "schema_projection_policy.v1"
    )
    name: StableName
    version: SemVer
    target_profile: StableName
    annotation_keywords: tuple[NonEmptyText, ...]
    structural_keywords: tuple[NonEmptyText, ...]
    removed_keywords: tuple[NonEmptyText, ...]
    rewritten_keywords: tuple[NonEmptyText, ...]
    base_prompt_obligations: tuple[StableName, ...]
    pattern_prompt_obligation: StableName

    @model_validator(mode="after")
    def keyword_sets_are_canonical(self) -> "SchemaProjectionPolicyDefinition":
        for field_name in (
            "annotation_keywords",
            "structural_keywords",
            "removed_keywords",
            "rewritten_keywords",
            "base_prompt_obligations",
        ):
            values = getattr(self, field_name)
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"{field_name} must be unique and sorted")
        return self


class SchemaProjectionPolicy(SchemaProjectionPolicyDefinition):
    policy_hash: Sha256

    @model_validator(mode="after")
    def hash_matches_definition(self) -> "SchemaProjectionPolicy":
        definition = SchemaProjectionPolicyDefinition.model_validate(
            self.model_dump(exclude={"policy_hash"})
        )
        if canonical_hash(definition) != self.policy_hash:
            raise ValueError("schema projection policy hash mismatch")
        return self


def define_schema_projection_policy(**values) -> SchemaProjectionPolicy:
    definition = SchemaProjectionPolicyDefinition(**values)
    return SchemaProjectionPolicy(
        **definition.model_dump(), policy_hash=canonical_hash(definition)
    )


PORTABLE_STRICT_OUTPUT_POLICY_V2 = define_schema_projection_policy(
    name="portable-strict-output",
    version="2.0.0",
    target_profile="portable-strict",
    annotation_keywords=tuple(sorted(_ANNOTATION_KEYWORDS)),
    structural_keywords=tuple(sorted(_STRUCTURAL_KEYWORDS)),
    removed_keywords=tuple(sorted(_UNSUPPORTED_CONSTRAINTS)),
    rewritten_keywords=("const",),
    base_prompt_obligations=("local_constraints_require_post_validation",),
    pattern_prompt_obligation="unsupported_pattern_not_enforced_by_provider",
)


# ── Projection report(§6.2)─────────────────────────────────────────────────


class RemovedSchemaConstraint(DomainModel):
    # keyword 是 JSON Schema 關鍵字(camelCase),故用 NonEmptyText 而非 StableName
    json_pointer: JsonPointer
    keyword: NonEmptyText
    value_hash: Sha256


class SchemaProjectionReportDefinition(DomainModel):
    schema_version: Literal["schema_projection_report.v1"] = (
        "schema_projection_report.v1"
    )
    policy_name: StableName
    policy_version: SemVer
    policy_hash: Sha256
    source_schema_id: NonEmptyText
    source_schema_hash: Sha256
    target_profile: StableName
    projected_schema_id: NonEmptyText
    projected_schema_hash: Sha256
    removed_constraints: tuple[RemovedSchemaConstraint, ...]
    rewritten_constraints: tuple[RemovedSchemaConstraint, ...]
    prompt_obligations: tuple[StableName, ...]

    @model_validator(mode="after")
    def entries_are_canonical(self) -> "SchemaProjectionReportDefinition":
        for field_name in ("removed_constraints", "rewritten_constraints"):
            entries = getattr(self, field_name)
            keys = tuple((item.json_pointer, item.keyword) for item in entries)
            if tuple(sorted(set(keys))) != keys:
                raise ValueError(
                    f"{field_name} must be unique and sorted by (pointer, keyword)"
                )
        if tuple(sorted(set(self.prompt_obligations))) != self.prompt_obligations:
            raise ValueError("prompt obligations must be unique and sorted")
        return self


class SchemaProjectionReport(SchemaProjectionReportDefinition):
    report_hash: Sha256

    @model_validator(mode="after")
    def hash_matches_definition(self) -> "SchemaProjectionReport":
        definition = SchemaProjectionReportDefinition.model_validate(
            self.model_dump(exclude={"report_hash"})
        )
        if canonical_hash(definition) != self.report_hash:
            raise ValueError("schema projection report hash mismatch")
        return self


@dataclass(frozen=True)
class ProjectedSchema:
    schema: dict[str, Any]
    report: SchemaProjectionReport


# ── Projection ───────────────────────────────────────────────────────────────


def _escape_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _project_tracked(
    value: Any,
    pointer: str,
    removed: list[tuple[str, str, str]],
    rewritten: list[tuple[str, str, str]],
) -> Any:
    if isinstance(value, list):
        return [
            _project_tracked(item, f"{pointer}/{index}", removed, rewritten)
            for index, item in enumerate(value)
        ]
    if not isinstance(value, dict):
        return value

    projected: dict[str, Any] = {}
    for key, item in value.items():
        if key in _UNSUPPORTED_CONSTRAINTS:
            removed.append((pointer, key, canonical_hash(item)))
            continue
        if key == "const":
            rewritten.append((pointer, key, canonical_hash(item)))
            projected["enum"] = [
                _project_tracked(
                    item, f"{pointer}/{_escape_token(key)}", removed, rewritten
                )
            ]
            continue
        projected[key] = _project_tracked(
            item, f"{pointer}/{_escape_token(key)}", removed, rewritten
        )

    if projected.get("type") == "object":
        properties = projected.get("properties", {})
        projected["additionalProperties"] = False
        projected["required"] = list(properties)
    return projected


def portable_strict_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Thin compatibility helper:同一投影、丟棄 report(§6.2)。"""

    removed: list[tuple[str, str, str]] = []
    rewritten: list[tuple[str, str, str]] = []
    projected = _project_tracked(deepcopy(schema), "", removed, rewritten)
    assert_portable_strict_output_schema(projected)
    return projected


def project_portable_strict_output_schema(
    source_schema: dict[str, Any],
    *,
    source_schema_id: str,
    target_profile: str,
) -> ProjectedSchema:
    """Project a local schema for providers and account for every lost constraint.

    Projected schema 沿用 source schema ID(同一個 logical contract 的 provider
    投影);兩者以 hash 區分。traversal 依 object insertion order 產出 projected
    schema,report entries 按 (json_pointer, keyword) 排序(§6.2)。
    """

    policy = PORTABLE_STRICT_OUTPUT_POLICY_V2
    if target_profile != policy.target_profile:
        raise ValueError(
            "projection target profile does not match the active policy: "
            f"{target_profile!r} != {policy.target_profile!r}"
        )
    source_schema_hash = canonical_hash(source_schema)
    removed: list[tuple[str, str, str]] = []
    rewritten: list[tuple[str, str, str]] = []
    projected = _project_tracked(deepcopy(source_schema), "", removed, rewritten)
    assert_portable_strict_output_schema(projected)

    obligations = set(policy.base_prompt_obligations)
    if any(keyword == "pattern" for _, keyword, _ in removed):
        obligations.add(policy.pattern_prompt_obligation)

    def entries(
        items: list[tuple[str, str, str]],
    ) -> tuple[RemovedSchemaConstraint, ...]:
        return tuple(
            RemovedSchemaConstraint(
                json_pointer=pointer, keyword=keyword, value_hash=value_hash
            )
            for pointer, keyword, value_hash in sorted(items)
        )

    definition = SchemaProjectionReportDefinition(
        policy_name=policy.name,
        policy_version=policy.version,
        policy_hash=policy.policy_hash,
        source_schema_id=source_schema_id,
        source_schema_hash=source_schema_hash,
        target_profile=target_profile,
        projected_schema_id=source_schema_id,
        projected_schema_hash=canonical_hash(projected),
        removed_constraints=entries(removed),
        rewritten_constraints=entries(rewritten),
        prompt_obligations=tuple(sorted(obligations)),
    )
    report = SchemaProjectionReport(
        **definition.model_dump(), report_hash=canonical_hash(definition)
    )
    return ProjectedSchema(schema=projected, report=report)


def assert_portable_strict_output_schema(
    schema: dict[str, Any], *, max_nullable_unions: int = 16
) -> None:
    """Reject unsupported semantics before a schema reaches either provider."""

    nullable_unions = 0

    def visit(value: Any, path: str) -> None:
        nonlocal nullable_unions
        if isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")
            return
        if not isinstance(value, dict):
            return

        unknown = set(value) - _ANNOTATION_KEYWORDS - _STRUCTURAL_KEYWORDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ProviderSchemaPortabilityError(
                f"unsupported JSON Schema keyword(s) at {path}: {names}"
            )

        schema_type = value.get("type")
        if schema_type is not None and schema_type not in _JSON_TYPES:
            raise ProviderSchemaPortabilityError(
                f"unsupported JSON type at {path}: {schema_type!r}"
            )

        if schema_type == "object":
            properties = value.get("properties")
            required = value.get("required")
            if not isinstance(properties, dict) or not isinstance(required, list):
                raise ProviderSchemaPortabilityError(
                    f"object at {path} requires properties and required"
                )
            if required != list(properties):
                raise ProviderSchemaPortabilityError(
                    f"every property must be required in schema order at {path}"
                )
            if value.get("additionalProperties") is not False:
                raise ProviderSchemaPortabilityError(
                    f"additionalProperties must be false at {path}"
                )

        if "enum" in value:
            enum = value["enum"]
            if not isinstance(enum, list) or not enum or len(enum) != len(
                {repr(item) for item in enum}
            ):
                raise ProviderSchemaPortabilityError(
                    f"enum must be finite, non-empty, and unique at {path}"
                )

        if "anyOf" in value:
            options = value["anyOf"]
            if not isinstance(options, list) or len(options) != 2:
                raise ProviderSchemaPortabilityError(
                    f"only two-branch nullable anyOf is allowed at {path}"
                )
            nulls = sum(
                isinstance(option, dict) and option.get("type") == "null"
                for option in options
            )
            if nulls != 1:
                raise ProviderSchemaPortabilityError(
                    f"anyOf must contain exactly one null branch at {path}"
                )
            nullable_unions += 1

        for key, item in value.items():
            if key in {"$defs", "properties"} and isinstance(item, dict):
                for name, child in item.items():
                    visit(child, f"{path}.{key}.{name}")
            elif key not in {"enum", "required"}:
                visit(item, f"{path}.{key}")

    visit(schema, "$")
    if nullable_unions > max_nullable_unions:
        raise ProviderSchemaPortabilityError(
            f"nullable union count {nullable_unions} exceeds {max_nullable_unions}"
        )
