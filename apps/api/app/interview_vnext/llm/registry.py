"""Deterministic registry for active LLM operation definitions."""

from __future__ import annotations

from collections.abc import Iterable

from app.interview_vnext.domain.hashing import canonical_hash

from .operation import OperationSpec


class OperationNotFound(KeyError):
    pass


class OperationRegistrationConflict(ValueError):
    pass


class OperationRegistry:
    def __init__(self, specs: Iterable[OperationSpec] = ()) -> None:
        self._specs: dict[str, OperationSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: OperationSpec) -> OperationSpec:
        spec = OperationSpec.model_validate(spec.model_dump())
        existing = self._specs.get(spec.name)
        if existing is None:
            self._specs[spec.name] = spec
            return spec
        if existing != spec:
            raise OperationRegistrationConflict(
                f"operation {spec.name!r} is already registered with another definition"
            )
        return existing

    def resolve(self, name: str, *, definition_hash: str | None = None) -> OperationSpec:
        try:
            spec = self._specs[name]
        except KeyError as exc:
            raise OperationNotFound(name) from exc
        if definition_hash is not None and definition_hash != spec.definition_hash:
            raise OperationRegistrationConflict(
                f"operation {name!r} definition hash does not match the active registry"
            )
        return spec

    @property
    def specs(self) -> tuple[OperationSpec, ...]:
        return tuple(self._specs[name] for name in sorted(self._specs))

    @property
    def manifest_hash(self) -> str:
        return canonical_hash([spec.model_dump(mode="json") for spec in self.specs])
