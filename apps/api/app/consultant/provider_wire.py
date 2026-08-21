"""Shared strict provider models and deterministic evidence-basis mapping."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.consultant.evidence_anchor import EvidenceAnchorError, resolve_evidence_reference
from app.consultant.results import AnalysisBasis, SkillId
from app.consultant.workspace_resources import (
    Handle,
    WorkspaceCatalog,
    WorkspaceEvidenceReference,
)


class ProviderWireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OutputEvidenceReference(ProviderWireModel):
    """Model-facing evidence reference before application-side resolution."""

    source_handle: Handle
    quote: str = Field(min_length=1)
    occurrence: int | None = Field(default=None, ge=1)
    skill_ids: tuple[SkillId, ...] = Field(min_length=1)


class OutputAnalysisBasis(ProviderWireModel):
    evidence: tuple[OutputEvidenceReference, ...] = Field(min_length=1)


class ProviderWireMappingError(ValueError):
    pass


class AnalysisBasisTable:
    def __init__(
        self,
        values: tuple[OutputAnalysisBasis, ...],
        *,
        catalog: WorkspaceCatalog,
    ) -> None:
        self._values = values
        self._catalog = catalog
        self._mapped: dict[int, AnalysisBasis] = {}
        self._used: set[int] = set()

    def resolve(self, ordinal: int, label: str) -> AnalysisBasis:
        if ordinal <= 0 or ordinal > len(self._values):
            raise ProviderWireMappingError(
                f"{label} must reference a 1-based analysis basis ordinal"
            )
        self._used.add(ordinal)
        if ordinal not in self._mapped:
            value = self._values[ordinal - 1]
            source_ids = []
            quote_anchors = []
            skill_ids = []
            for reference in value.evidence:
                try:
                    workspace_reference = WorkspaceEvidenceReference.model_validate(
                        reference.model_dump(mode="python")
                    )
                    anchor = resolve_evidence_reference(
                        workspace_reference,
                        self._catalog,
                    )
                except (EvidenceAnchorError, ValidationError, ValueError) as error:
                    raise ProviderWireMappingError(
                        f"{label} evidence could not be resolved: {error}"
                    ) from error
                if anchor.source_id not in source_ids:
                    source_ids.append(anchor.source_id)
                quote_anchors.append(anchor)
                for skill_id in reference.skill_ids:
                    if skill_id not in skill_ids:
                        skill_ids.append(skill_id)
            self._mapped[ordinal] = AnalysisBasis(
                source_ids=tuple(source_ids),
                quote_anchors=tuple(quote_anchors),
                skill_ids=tuple(skill_ids),
            )
        return self._mapped[ordinal]

    def reject_unused(self) -> None:
        unused = set(range(1, len(self._values) + 1)) - self._used
        if unused:
            raise ProviderWireMappingError(
                f"unused analysis basis ordinals carry content: {sorted(unused)}"
            )
