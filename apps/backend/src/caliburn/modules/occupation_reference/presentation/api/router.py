"""Query pinned references without Agent or concrete storage dependencies."""

from collections.abc import Callable
from functools import partial

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from indexer_contract.references import (
    OccupationReference,
    ReferenceSearchRequest,
    ReferenceSearchResponse,
    ReferenceTaskDetail,
)

from caliburn.modules.occupation_reference.application.execution import SearchRunner
from caliburn.modules.occupation_reference.application.search import ReferenceSearch
from caliburn.modules.occupation_reference.presentation.api.errors import (
    reference_errors,
)
from caliburn.modules.occupation_reference.presentation.api.projection import (
    project_reference,
    project_search,
    project_task,
)


def build_reference_router(
    get_service: Callable[[], ReferenceSearch],
    get_runner: Callable[[], SearchRunner],
) -> APIRouter:
    router = APIRouter(tags=["occupation-references"])

    @router.post(
        "/occupation-references:search",
        response_model=ReferenceSearchResponse,
        operation_id="search_occupation_references",
    )
    async def search(
        body: ReferenceSearchRequest, request: Request
    ) -> ReferenceSearchResponse:
        with reference_errors(request):
            service = get_service()
            result = await get_runner().run(
                partial(service.search, body.query, limit=body.limit)
            )
            return project_search(result, service)

    @router.get(
        "/occupation-references/{reference_id}",
        response_model=OccupationReference,
        operation_id="read_occupation_reference",
    )
    async def read(reference_id: str, request: Request) -> OccupationReference:
        with reference_errors(request):
            document = await run_in_threadpool(get_service().read, reference_id)
            return project_reference(document)

    @router.get(
        "/occupation-references/{reference_id}/tasks/{task_id}",
        response_model=ReferenceTaskDetail,
        operation_id="read_reference_task",
    )
    async def read_task(
        reference_id: str, task_id: str, request: Request
    ) -> ReferenceTaskDetail:
        with reference_errors(request):
            result = await run_in_threadpool(
                get_service().read_task, reference_id, task_id
            )
            return project_task(result)

    return router
