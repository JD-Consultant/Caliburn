"""Shared strict provider models and deterministic evidence-basis mapping."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.consultant.results import AnalysisBasis, SkillId
from app.consultant.state import QuoteAnchor


class ProviderWireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OutputQuoteAnchor(ProviderWireModel):
    source_id: UUID = Field(description="必須是 context 明列的員工來源 ID")
    start: int = Field(
        ge=0, description="quote 在來源文字中的 0-based 起點；不得用占位值"
    )
    end: int = Field(
        gt=0,
        description="quote 的 exclusive 終點，必須等於 start + len(quote)",
    )
    quote: str = Field(min_length=1, description="必須逐字存在於指定員工來源")


class OutputEvidenceReference(ProviderWireModel):
    """Model-facing evidence reference before application-side resolution."""

    source_handle: str
    quote: str = Field(min_length=1)
    occurrence: int | None = Field(default=None, ge=1)
    skill_ids: tuple[SkillId, ...] = Field(min_length=1)


class OutputAnalysisBasis(ProviderWireModel):
    source_ids: tuple[UUID, ...]
    quote_anchors: tuple[OutputQuoteAnchor, ...] = Field(
        description="無法保證逐字位置時可留空，不得用假 offset 占位"
    )
    skill_ids: tuple[SkillId, ...]


class ProviderWireMappingError(ValueError):
    pass


class AnalysisBasisTable:
    def __init__(self, values: tuple[OutputAnalysisBasis, ...]) -> None:
        self._values = values
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
            self._mapped[ordinal] = AnalysisBasis(
                source_ids=value.source_ids,
                quote_anchors=tuple(
                    QuoteAnchor(
                        source_id=item.source_id,
                        start=item.start,
                        end=item.end,
                        quote=item.quote,
                    )
                    for item in value.quote_anchors
                ),
                skill_ids=value.skill_ids,
            )
        return self._mapped[ordinal]

    def reject_unused(self) -> None:
        unused = set(range(1, len(self._values) + 1)) - self._used
        if unused:
            raise ProviderWireMappingError(
                f"unused analysis basis ordinals carry content: {sorted(unused)}"
            )
