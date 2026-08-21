from __future__ import annotations

from uuid import UUID

import pytest

from app.consultant.evidence_anchor import (
    EvidenceAnchorError,
    resolve_evidence_reference,
    resolve_exact_quote,
)
from app.consultant.provider_wire import OutputEvidenceReference
from app.consultant.state import (
    ApprovedJobDocument,
    EmployeeSource,
    EmployeeSourceKind,
    QuoteAnchor,
    SourceValidity,
)
from app.consultant.workspace_resources import WorkspaceCatalog, WorkspaceEvidenceReference


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000201")
FOREIGN_DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000202")
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000203")
FOREIGN_SOURCE_ID = UUID("00000000-0000-0000-0000-000000000204")
SUPERSEDED_SOURCE_ID = UUID("00000000-0000-0000-0000-000000000205")
REPLACEMENT_SOURCE_ID = UUID("00000000-0000-0000-0000-000000000206")


def _source(
    *,
    source_id: UUID = SOURCE_ID,
    document_id: UUID = DOCUMENT_ID,
    text: str = "核對訂單，再核對訂單。",
    validity: SourceValidity = SourceValidity.CURRENT,
    superseded_by_source_id: UUID | None = None,
) -> EmployeeSource:
    source = EmployeeSource.pending(
        source_id=source_id,
        document_id=document_id,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text=text,
    )
    return source.model_copy(
        update={
            "validity": validity,
            "superseded_by_source_id": superseded_by_source_id,
        }
    )


def test_resolver_finds_unique_chinese_quote_in_raw_source() -> None:
    anchor = resolve_exact_quote(raw="先核對訂單，再出貨。", quote="核對訂單")

    assert (anchor.start, anchor.end, anchor.quote) == (1, 5, "核對訂單")


def test_resolver_finds_quote_across_a_newline() -> None:
    anchor = resolve_exact_quote(raw="第一行\n第二行", quote="行\n第")

    assert (anchor.start, anchor.end) == (2, 5)


def test_resolver_finds_second_chinese_occurrence_in_raw_source() -> None:
    anchor = resolve_exact_quote(
        raw="核對訂單，再核對訂單。", quote="核對訂單", occurrence=2
    )

    assert (anchor.start, anchor.end) == (6, 10)


def test_resolver_rejects_ambiguous_quote_without_occurrence() -> None:
    with pytest.raises(EvidenceAnchorError, match="occurrence is required"):
        resolve_exact_quote(raw="核對訂單，再核對訂單。", quote="核對訂單")


def test_resolver_rejects_out_of_range_occurrence() -> None:
    with pytest.raises(EvidenceAnchorError, match="occurrence is out of range"):
        resolve_exact_quote(
            raw="核對訂單，再核對訂單。", quote="核對訂單", occurrence=3
        )


def test_resolver_rejects_quote_that_does_not_occur() -> None:
    with pytest.raises(EvidenceAnchorError, match="quote does not occur"):
        resolve_exact_quote(raw="核對訂單", quote="出貨")


def test_resolver_rejects_read_file_gutter() -> None:
    with pytest.raises(EvidenceAnchorError, match="quote does not occur"):
        resolve_exact_quote(raw="核對訂單", quote="1→核對訂單", occurrence=1)


def test_evidence_reference_resolves_to_durable_quote_anchor() -> None:
    source = _source()
    catalog = WorkspaceCatalog.from_snapshot(
        ApprovedJobDocument(document_id=DOCUMENT_ID),
        pending=(),
        sources=(source,),
    )
    reference = WorkspaceEvidenceReference(
        source_handle="source-001",
        quote="核對訂單",
        occurrence=2,
        skill_ids=("task-boundary",),
    )

    anchor = resolve_evidence_reference(reference, catalog)

    assert anchor == QuoteAnchor(
        source_id=SOURCE_ID,
        start=6,
        end=10,
        quote="核對訂單",
    )


def test_evidence_reference_rejects_source_from_another_document() -> None:
    foreign_source = _source(
        source_id=FOREIGN_SOURCE_ID,
        document_id=FOREIGN_DOCUMENT_ID,
        text="外部文件的內容。",
    )
    catalog = WorkspaceCatalog.from_snapshot(
        ApprovedJobDocument(document_id=DOCUMENT_ID),
        pending=(),
        sources=(foreign_source,),
    )
    reference = WorkspaceEvidenceReference(
        source_handle="source-001",
        quote="外部文件的內容。",
        skill_ids=("task-boundary",),
    )

    with pytest.raises(EvidenceAnchorError, match="different document"):
        resolve_evidence_reference(reference, catalog)


def test_evidence_reference_rejects_superseded_source() -> None:
    superseded = _source(
        source_id=SUPERSEDED_SOURCE_ID,
        validity=SourceValidity.SUPERSEDED,
        superseded_by_source_id=REPLACEMENT_SOURCE_ID,
    )
    catalog = WorkspaceCatalog.from_snapshot(
        ApprovedJobDocument(document_id=DOCUMENT_ID),
        pending=(),
        sources=(superseded,),
    )
    reference = WorkspaceEvidenceReference(
        source_handle="source-001",
        quote="核對訂單",
        skill_ids=("task-boundary",),
    )

    with pytest.raises(EvidenceAnchorError, match="superseded"):
        resolve_evidence_reference(reference, catalog)


def test_evidence_resolver_rejects_provider_wire_reference_type() -> None:
    source = _source()
    catalog = WorkspaceCatalog.from_snapshot(
        ApprovedJobDocument(document_id=DOCUMENT_ID),
        pending=(),
        sources=(source,),
    )
    reference = OutputEvidenceReference(
        source_handle="source-001",
        quote="核對訂單",
        occurrence=1,
        skill_ids=("task-boundary",),
    )

    with pytest.raises(EvidenceAnchorError, match="invalid evidence reference"):
        resolve_evidence_reference(reference, catalog)


def test_evidence_resolver_rejects_reversed_argument_types() -> None:
    source = _source()
    catalog = WorkspaceCatalog.from_snapshot(
        ApprovedJobDocument(document_id=DOCUMENT_ID),
        pending=(),
        sources=(source,),
    )
    reference = WorkspaceEvidenceReference(
        source_handle="source-001",
        quote="核對訂單",
        skill_ids=("task-boundary",),
    )

    with pytest.raises(EvidenceAnchorError, match="workspace catalog"):
        resolve_evidence_reference(catalog, reference)
