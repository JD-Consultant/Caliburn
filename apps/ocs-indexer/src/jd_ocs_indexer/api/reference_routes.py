"""Reference HTTP boundary: validated DTO projection over ordinary use cases."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from indexer_contract.references import (
    OccupationReference,
    OccupationReferenceHit,
    ReferenceCompetencyBlock,
    ReferenceEvidence,
    ReferenceIndicator,
    ReferenceNamedContent,
    ReferenceRetrievalPolicy,
    ReferenceSearchRequest,
    ReferenceSearchResponse,
    ReferenceTaskDetail,
    ReferenceTaskName,
    ReferenceTaskSummary,
    ReferenceUnit,
)

from jd_ocs_indexer.references.errors import ReferenceNotFoundError
from jd_ocs_indexer.references.service import ReferenceSearch
from jd_ocs_indexer.references.source import PREPROCESSING, ReferenceDocument

router = APIRouter(tags=["occupation-references"])


async def get_reference_search(request: Request) -> ReferenceSearch | None:
    service = request.app.state.reference_search
    if service is not None and not isinstance(service, ReferenceSearch):
        raise RuntimeError("invalid reference search dependency")
    return service


def require_reference_search(service: ReferenceSearch | None) -> ReferenceSearch:
    if service is None:
        raise HTTPException(503, detail={"code": "reference_service_unavailable"})
    return service


ReferenceDependency = Annotated[ReferenceSearch | None, Depends(get_reference_search)]


def project_reference(doc: ReferenceDocument) -> OccupationReference:
    profile = doc.source.ocs_profile
    names = profile.ocs_name
    units = []
    source_units = doc.source.ocs_content.ocu_units if doc.source.ocs_content else []
    for index, unit in enumerate(source_units or [], 1):
        unit_id = f"u{index}"
        units.append(
            ReferenceUnit(
                unit_id=unit_id,
                code=unit.ocu_code,
                name=unit.ocu_name,
                tasks=[
                    ReferenceTaskSummary(
                        task_id=entry.task_id,
                        names=[
                            ReferenceTaskName(code=item.code, name=item.name)
                            for item in entry.group.task_codes or []
                        ],
                        competency_block_count=len(entry.group.competency_blocks or []),
                    )
                    for entry in doc.tasks
                    if entry.unit_id == unit_id
                ],
            )
        )
    return OccupationReference(
        reference_id=doc.reference_id,
        source_sha256=doc.source_sha256,
        source_file=doc.source_file,
        ocs_code=doc.ocs_code,
        title=((names.occupation_name or names.job_category_name) if names else None)
        or doc.ocs_code,
        overview=profile.job_description or "",
        units=units,
    )


@router.post(
    "/occupation-references:search",
    response_model=ReferenceSearchResponse,
    operation_id="search_occupation_references",
)
async def search_occupation_references(
    body: ReferenceSearchRequest,
    request: Request,
    service: ReferenceDependency,
) -> ReferenceSearchResponse:
    service = require_reference_search(service)

    def search() -> ReferenceSearchResponse:
        result = service.search(body.query, limit=body.limit)
        return ReferenceSearchResponse(
            references=[
                OccupationReferenceHit(
                    reference=project_reference(hit.document),
                    retrieval_evidence=ReferenceEvidence(
                        document_cosine=hit.document_cosine,
                        task_cosine=hit.task_cosine,
                        matched_task_ids=list(hit.matched_task_ids),
                        overview_matched=hit.overview_matched,
                    ),
                    rerank_logit=hit.rerank_logit,
                )
                for hit in result.hits
            ],
            retrieval_policy=ReferenceRetrievalPolicy(
                preprocessing=PREPROCESSING,
                candidate_limit_per_route=service.candidate_limit,
                candidate_count=result.candidate_count,
                embedding_model=service.embedder.signature.model,
                embedding_dimensions=service.embedder.signature.dim,
                reranker_model=service.reranker.model,
                reranker_revision=service.reranker.revision,
            ),
        )

    return await request.app.state.retrieval.run(search)


@router.get(
    "/occupation-references/{reference_id}",
    response_model=OccupationReference,
    operation_id="read_occupation_reference",
)
async def read_occupation_reference(
    reference_id: str,
    service: ReferenceDependency,
) -> OccupationReference:
    service = require_reference_search(service)
    return project_reference(await run_in_threadpool(service.read, reference_id))


@router.get(
    "/occupation-references/{reference_id}/tasks/{task_id}",
    response_model=ReferenceTaskDetail,
    operation_id="read_reference_task",
)
async def read_reference_task(
    reference_id: str,
    task_id: str,
    service: ReferenceDependency,
) -> ReferenceTaskDetail:
    service = require_reference_search(service)
    doc = await run_in_threadpool(service.read, reference_id)
    entry = next((entry for entry in doc.tasks if entry.task_id == task_id), None)
    if entry is None:
        raise ReferenceNotFoundError("reference task not found")
    return ReferenceTaskDetail(
        reference_id=doc.reference_id,
        source_sha256=doc.source_sha256,
        task_id=entry.task_id,
        unit_id=entry.unit_id,
        names=[
            ReferenceTaskName(code=item.code, name=item.name)
            for item in entry.group.task_codes or []
        ],
        competency_blocks=[
            ReferenceCompetencyBlock(
                competency_level=block.competency_level,
                outputs=[
                    ReferenceNamedContent(code=item.code, name=item.name)
                    for item in block.outputs or []
                ],
                indicators=[
                    ReferenceIndicator(code=item.code, text=item.text)
                    for item in block.indicators or []
                ],
                knowledge=[
                    ReferenceNamedContent(code=item.code, name=item.name)
                    for item in block.knowledge or []
                ],
                skills=[
                    ReferenceNamedContent(code=item.code, name=item.name)
                    for item in block.skills or []
                ],
            )
            for block in entry.group.competency_blocks or []
        ],
    )
