"""共用知識與技能定義的 HTTP 入口。"""

from fastapi import APIRouter, Request, Response, status

from caliburn.modules.job_description.application import knowledge, skills
from caliburn.modules.job_description.presentation.api.dependencies import (
    JobDescriptionUoWFactory,
)
from caliburn.modules.job_description.presentation.api.errors import (
    ERROR_RESPONSES,
    JobDescriptionRoute,
)
from caliburn.modules.job_description.presentation.api.responses import (
    CREATED_RESPONSES,
    created_response,
    write_response,
)
from caliburn.modules.job_description.presentation.api.schemas.common import (
    CorrelationIdInput,
    ExpectedVersionQuery,
)
from caliburn.modules.job_description.presentation.api.schemas.content import (
    AddKnowledgeRequest,
    AddSkillRequest,
    JobDescriptionResponse,
    UpdateKnowledgeRequest,
    UpdateSkillRequest,
)
from caliburn.shared.presentation.api.values import HttpId


def build_definitions_router(uow_factory: JobDescriptionUoWFactory) -> APIRouter:
    """只映射 HTTP 與用例；交易與版本前置由 Application 完成。"""
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/job-descriptions",
        tags=["jd-definitions"],
        route_class=JobDescriptionRoute,
        responses=ERROR_RESPONSES,
    )

    @router.post(
        "/{job_description_id}/knowledge",
        response_model=JobDescriptionResponse,
        operation_id="jd_add_knowledge",
        summary="新增共用知識",
        name="jd_add_knowledge",
        status_code=status.HTTP_201_CREATED,
        responses=CREATED_RESPONSES,
    )
    def add_knowledge(
        workspace_id: HttpId,
        job_description_id: HttpId,
        body: AddKnowledgeRequest,
        request: Request,
        response: Response,
    ) -> JobDescriptionResponse:
        result = knowledge.add_knowledge(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            expected_version=body.expected_version,
            name=body.name,
            description=body.description,
            correlation_id=body.correlation_id,
            citations=tuple(change.to_application() for change in body.citations),
            uow_factory=uow_factory,
        )
        return created_response(request, response, result)

    @router.patch(
        "/{job_description_id}/knowledge/{knowledge_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_update_knowledge",
        summary="修改共用知識",
        name="jd_update_knowledge",
    )
    def update_knowledge(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        knowledge_id: HttpId,
        body: UpdateKnowledgeRequest,
    ) -> JobDescriptionResponse:
        result = knowledge.update_knowledge(
            workspace_id=workspace_id,
            input=knowledge.UpdateKnowledgeInput.model_validate(
                {
                    "job_description_id": job_description_id,
                    "knowledge_id": knowledge_id,
                    **body.model_dump(exclude_unset=True),
                }
            ),
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    @router.delete(
        "/{job_description_id}/knowledge/{knowledge_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_delete_knowledge",
        summary="刪除共用知識",
        name="jd_delete_knowledge",
    )
    def delete_knowledge(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        knowledge_id: HttpId,
        expected_version: ExpectedVersionQuery,
        correlation_id: CorrelationIdInput | None = None,
    ) -> JobDescriptionResponse:
        result = knowledge.delete_knowledge(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            knowledge_id=knowledge_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    @router.post(
        "/{job_description_id}/skills",
        response_model=JobDescriptionResponse,
        operation_id="jd_add_skill",
        summary="新增共用技能",
        name="jd_add_skill",
        status_code=status.HTTP_201_CREATED,
        responses=CREATED_RESPONSES,
    )
    def add_skill(
        workspace_id: HttpId,
        job_description_id: HttpId,
        body: AddSkillRequest,
        request: Request,
        response: Response,
    ) -> JobDescriptionResponse:
        result = skills.add_skill(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            expected_version=body.expected_version,
            name=body.name,
            description=body.description,
            correlation_id=body.correlation_id,
            citations=tuple(change.to_application() for change in body.citations),
            uow_factory=uow_factory,
        )
        return created_response(request, response, result)

    @router.patch(
        "/{job_description_id}/skills/{skill_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_update_skill",
        summary="修改共用技能",
        name="jd_update_skill",
    )
    def update_skill(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        skill_id: HttpId,
        body: UpdateSkillRequest,
    ) -> JobDescriptionResponse:
        result = skills.update_skill(
            workspace_id=workspace_id,
            input=skills.UpdateSkillInput.model_validate(
                {
                    "job_description_id": job_description_id,
                    "skill_id": skill_id,
                    **body.model_dump(exclude_unset=True),
                }
            ),
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    @router.delete(
        "/{job_description_id}/skills/{skill_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_delete_skill",
        summary="刪除共用技能",
        name="jd_delete_skill",
    )
    def delete_skill(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        skill_id: HttpId,
        expected_version: ExpectedVersionQuery,
        correlation_id: CorrelationIdInput | None = None,
    ) -> JobDescriptionResponse:
        result = skills.delete_skill(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            skill_id=skill_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    return router
