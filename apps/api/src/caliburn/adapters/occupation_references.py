"""Validated HTTP reads; no employee state, client ownership, retries, or model wiring."""

import re

import httpx2
from pydantic import TypeAdapter, ValidationError

from caliburn.adapters.occupation_reference_models import (
    OccupationReference,
    ReferenceSearchResult,
    ReferenceTaskDetail,
)

_SEARCH_RESULT = TypeAdapter(ReferenceSearchResult)
_REFERENCE = TypeAdapter(OccupationReference)
_TASK_DETAIL = TypeAdapter(ReferenceTaskDetail)
_PATH_LOCATOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_HTTP_ERRORS = {
    404: "reference_not_found",
    409: "reference_index_incompatible",
    422: "reference_query_invalid",
    502: "reference_provider_invalid_response",
    503: "reference_service_unavailable",
}


class ReferenceClientError(Exception):
    """A bounded external-reference failure without upstream text."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OccupationReferenceClient:
    """Borrow a configured AsyncClient; its creator owns the base URL, timeout, and close."""

    def __init__(self, client: httpx2.AsyncClient) -> None:
        self.client = client

    async def search(self, query: str, *, limit: int = 5) -> ReferenceSearchResult:
        """Keep raw query text and the full catalog, including tasks with no retrieval hit."""
        if (
            not isinstance(query, str)
            or not query.strip()
            or len(query) > 12_000
            or type(limit) is not int
            or not 1 <= limit <= 5
        ):
            raise ReferenceClientError("invalid_arguments")
        result = await self._request(
            "POST",
            "/occupation-references:search",
            _SEARCH_RESULT,
            body={"query": query, "limit": limit},
        )
        references = result.references
        if len(references) != min(limit, result.retrieval_policy.candidate_count) or len(
            {hit.reference.reference_id for hit in references}
        ) != len(references):
            raise ReferenceClientError("invalid_response")
        for hit in references:
            _validate_reference(hit.reference)
            task_ids = {task.task_id for unit in hit.reference.units for task in unit.tasks}
            matched = hit.retrieval_evidence.matched_task_ids
            if len(set(matched)) != len(matched) or not set(matched) <= task_ids:
                raise ReferenceClientError("invalid_response")
        return result

    async def read(self, reference_id: str) -> OccupationReference:
        """Read the requested fixed source without accepting a substitute identity."""
        _require_path_locator(reference_id)
        result = await self._request("GET", f"/occupation-references/{reference_id}", _REFERENCE)
        if result.reference_id != reference_id:
            raise ReferenceClientError("invalid_response")
        _validate_reference(result)
        return result

    async def read_task(self, reference_id: str, task_id: str) -> ReferenceTaskDetail:
        """Read one full task group, preserving shared names and all competency blocks."""
        _require_path_locator(reference_id)
        _require_path_locator(task_id)
        result = await self._request(
            "GET",
            f"/occupation-references/{reference_id}/tasks/{task_id}",
            _TASK_DETAIL,
        )
        if (
            result.reference_id != reference_id
            or result.task_id != task_id
            or result.task_id.partition("-t")[0] != result.unit_id
        ):
            raise ReferenceClientError("invalid_response")
        return result

    async def _request[T](
        self,
        method: str,
        path: str,
        parser: TypeAdapter[T],
        *,
        body: dict[str, str | int] | None = None,
    ) -> T:
        try:
            response = await self.client.request(
                method,
                path,
                json=body,
                follow_redirects=False,
            )
        except httpx2.TimeoutException:
            # The boundary deliberately omits causes containing query or upstream body text.
            raise ReferenceClientError("timeout") from None
        except httpx2.HTTPError:
            raise ReferenceClientError("reference_service_unavailable") from None
        if response.status_code != 200:
            fallback = (
                "reference_service_unavailable"
                if response.status_code >= 500
                else "invalid_response"
            )
            raise ReferenceClientError(_HTTP_ERRORS.get(response.status_code, fallback))
        try:
            return parser.validate_json(response.content, strict=True)
        except ValidationError:
            raise ReferenceClientError("invalid_response") from None


def _require_path_locator(value: str) -> None:
    if not isinstance(value, str) or _PATH_LOCATOR.fullmatch(value) is None:
        raise ReferenceClientError("invalid_arguments")


def _validate_reference(reference: OccupationReference) -> None:
    units = reference.units
    if len({unit.unit_id for unit in units}) != len(units):
        raise ReferenceClientError("invalid_response")
    task_ids = []
    for unit in units:
        for task in unit.tasks:
            if task.task_id.partition("-t")[0] != unit.unit_id:
                raise ReferenceClientError("invalid_response")
            task_ids.append(task.task_id)
    if len(set(task_ids)) != len(task_ids):
        raise ReferenceClientError("invalid_response")
