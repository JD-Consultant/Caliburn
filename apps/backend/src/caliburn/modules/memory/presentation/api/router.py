"""固定發布版的唯讀 HTTP，不需要啟動 Agent。"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request, Response

from caliburn.modules.memory.application.errors import (
    MemoryDataError,
    MemoryQueryError,
    MemoryVersionNotFoundError,
    WorkspaceNotFoundError,
)
from caliburn.modules.memory.application.persistence import MemoryQueries
from caliburn.modules.memory.domain.items import WorkSituation
from caliburn.modules.memory.domain.snapshot import MAX_MEMORY_VERSION, MemorySnapshot
from caliburn.modules.memory.presentation.api.schemas import (
    MemoryItemResponse,
    MemoryMapEntryResponse,
    MemoryMapResponse,
)
from caliburn.shared.presentation.api.diagnostics import log_http_failure
from caliburn.shared.presentation.api.schemas import ErrorResponse
from caliburn.shared.presentation.api.values import HttpId

type VersionPath = Annotated[int, Path(ge=1, le=MAX_MEMORY_VERSION)]


def build_memory_router(queries: MemoryQueries) -> APIRouter:
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/memory",
        tags=["memory"],
        responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )

    @router.get(
        "", response_model=MemoryMapResponse, operation_id="get_published_memory"
    )
    def get_latest(
        workspace_id: HttpId, request: Request, response: Response
    ) -> MemoryMapResponse:
        with _query_errors(request):
            current = queries.get_current(workspace_id=workspace_id)
            snapshot = queries.get_published(
                workspace_id=workspace_id, published_version=current.published_version
            )
        response.headers["Cache-Control"] = "no-store"
        return _map(workspace_id, snapshot)

    @router.get(
        "/versions/{version}",
        response_model=MemoryMapResponse,
        operation_id="get_memory_version",
    )
    def get_version(
        workspace_id: HttpId, version: VersionPath, request: Request, response: Response
    ) -> MemoryMapResponse:
        with _query_errors(request):
            snapshot = queries.get_published(
                workspace_id=workspace_id, published_version=version
            )
            if snapshot is None:
                raise MemoryDataError("指定發布版不應回空基準")
        response.headers["Cache-Control"] = "no-store"
        return _map(workspace_id, snapshot)

    @router.get(
        "/versions/{version}/items/{item_id}",
        response_model=MemoryItemResponse,
        operation_id="get_memory_item",
    )
    def get_item(
        workspace_id: HttpId,
        version: VersionPath,
        item_id: HttpId,
        request: Request,
        response: Response,
    ) -> MemoryItemResponse:
        with _query_errors(request):
            snapshot = queries.get_published(
                workspace_id=workspace_id, published_version=version
            )
            if snapshot is None:
                raise MemoryDataError("指定發布版不應回空基準")
        item = next((item for item in snapshot.items if item.id == item_id), None)
        if item is None:
            raise HTTPException(404, detail={"code": "memory_item_not_found"})
        response.headers["Cache-Control"] = "no-store"
        return MemoryItemResponse(
            workspace_id=workspace_id,
            published_version=snapshot.version,
            item_id=item.id,
            kind=item.kind,
            title=item.content.title,
            description=item.content.description,
            body=item.content.body,
            source_ids=list(
                item.interview_message_ids
                if isinstance(item, WorkSituation)
                else item.situation_ids
            ),
            changed_version=item.changed_version,
        )

    return router


def _map(workspace_id: UUID, snapshot: MemorySnapshot | None) -> MemoryMapResponse:
    return MemoryMapResponse(
        workspace_id=workspace_id,
        published_version=snapshot.version if snapshot is not None else None,
        covered_through_message_id=(
            snapshot.covered_through_message_id if snapshot is not None else None
        ),
        items=[
            MemoryMapEntryResponse(
                item_id=item.id,
                kind=item.kind,
                title=item.content.title,
                description=item.content.description,
                changed_version=item.changed_version,
            )
            for item in (snapshot.items if snapshot is not None else ())
        ],
    )


@contextmanager
def _query_errors(request: Request) -> Iterator[None]:
    try:
        yield
    except WorkspaceNotFoundError as error:
        raise HTTPException(404, detail={"code": "workspace_not_found"}) from error
    except MemoryVersionNotFoundError as error:
        raise HTTPException(404, detail={"code": "memory_version_not_found"}) from error
    except (MemoryDataError, MemoryQueryError) as error:
        request_id = log_http_failure(request, error, status_code=503)
        raise HTTPException(
            503,
            detail={"code": "memory_unavailable"},
            headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
        ) from error
