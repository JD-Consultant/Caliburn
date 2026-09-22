"""Offline external-boundary fake for professional consultant runners."""

from __future__ import annotations

from app.professional_consultant.runner import (
    ProviderCallError,
    StructuredOperationRequest,
    StructuredOperationResponse,
)


class ScriptedProvider:
    def __init__(
        self,
        responses: tuple[StructuredOperationResponse | ProviderCallError, ...],
    ) -> None:
        self._responses = responses
        self._index = 0
        self.requests: list[StructuredOperationRequest] = []

    async def generate(
        self, request: StructuredOperationRequest
    ) -> StructuredOperationResponse:
        self.requests.append(request)
        if self._index >= len(self._responses):
            raise AssertionError("scripted provider has no response for this request")
        response = self._responses[self._index]
        self._index += 1
        if isinstance(response, ProviderCallError):
            raise response
        return response
