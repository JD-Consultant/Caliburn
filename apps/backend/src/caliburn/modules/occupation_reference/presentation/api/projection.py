"""Project complete pinned sources into the shared public HTTP schema."""

from indexer_contract.references import (
    OccupationReference,
    OccupationReferenceHit,
    ReferenceCompetencyBlock,
    ReferenceEvidence,
    ReferenceIndicator,
    ReferenceNamedContent,
    ReferenceRetrievalPolicy,
    ReferenceSearchResponse,
    ReferenceTaskDetail,
    ReferenceTaskName,
    ReferenceTaskSummary,
    ReferenceUnit,
)

from caliburn.modules.occupation_reference.application.search import (
    ReferenceSearch,
    ReferenceTask,
    SearchResult,
)
from caliburn.modules.occupation_reference.domain.source import (
    PREPROCESSING,
    ReferenceDocument,
)


def project_reference(document: ReferenceDocument) -> OccupationReference:
    profile = document.source.ocs_profile
    names = profile.ocs_name
    units = []
    source_units = (
        document.source.ocs_content.ocu_units if document.source.ocs_content else []
    )
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
                    for entry in document.tasks
                    if entry.unit_id == unit_id
                ],
            )
        )
    return OccupationReference(
        reference_id=document.reference_id,
        source_sha256=document.source_sha256,
        source_file=document.source_file,
        ocs_code=document.ocs_code,
        title=((names.occupation_name or names.job_category_name) if names else None)
        or document.ocs_code,
        overview=profile.job_description or "",
        units=units,
    )


def project_search(
    result: SearchResult, service: ReferenceSearch
) -> ReferenceSearchResponse:
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


def project_task(result: ReferenceTask) -> ReferenceTaskDetail:
    entry = result.entry
    return ReferenceTaskDetail(
        reference_id=result.reference_id,
        source_sha256=result.source_sha256,
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
