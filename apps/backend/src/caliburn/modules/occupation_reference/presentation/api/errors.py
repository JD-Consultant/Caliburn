"""Translate owned failures without exposing source paths or query content."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException, Request

from caliburn.modules.occupation_reference.application.errors import (
    ReferenceIndexError,
    ReferenceNotFoundError,
    ReferenceProviderError,
    ReferenceQueryError,
    ReferenceUnavailableError,
    RetrievalBusy,
    RetrievalUnavailable,
)
from caliburn.shared.presentation.api.diagnostics import log_http_failure


@contextmanager
def reference_errors(request: Request) -> Iterator[None]:
    try:
        yield
    except ReferenceNotFoundError as error:
        raise HTTPException(404, detail={"code": "reference_not_found"}) from error
    except ReferenceIndexError as error:
        raise HTTPException(
            409, detail={"code": "reference_index_incompatible"}
        ) from error
    except ReferenceQueryError as error:
        raise HTTPException(422, detail={"code": "reference_query_invalid"}) from error
    except ReferenceProviderError as error:
        request_id = log_http_failure(request, error, status_code=502)
        raise HTTPException(
            502,
            detail={"code": "reference_provider_invalid_response"},
            headers={"X-Request-ID": request_id},
        ) from error
    except RetrievalBusy as error:
        raise HTTPException(503, detail={"code": "retrieval_busy"}) from error
    except RetrievalUnavailable as error:
        raise HTTPException(503, detail={"code": "retrieval_unavailable"}) from error
    except ReferenceUnavailableError as error:
        request_id = log_http_failure(request, error, status_code=503)
        raise HTTPException(
            503,
            detail={"code": "reference_service_unavailable"},
            headers={"X-Request-ID": request_id},
        ) from error
