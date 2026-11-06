"""Translate the HTTP SDK boundary without leaking transport into application."""

from collections.abc import Iterator
from contextlib import contextmanager
from json import JSONDecodeError

from httpx import RequestError
from pydantic import ValidationError
from qdrant_client.common.client_exceptions import ResourceExhaustedResponse
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from caliburn.modules.occupation_reference.application.errors import (
    ReferenceIndexError,
    ReferenceProviderError,
    ReferenceUnavailableError,
)


@contextmanager
def qdrant_errors() -> Iterator[None]:
    try:
        yield
    except ResourceExhaustedResponse as exc:
        raise ReferenceUnavailableError("reference store is unavailable") from exc
    except JSONDecodeError as exc:
        raise ReferenceProviderError("reference store returned invalid data") from exc
    except ResponseHandlingException as exc:
        if isinstance(exc.source, RequestError):
            raise ReferenceUnavailableError("reference store is unavailable") from exc
        if isinstance(exc.source, ValidationError):
            raise ReferenceProviderError(
                "reference store returned invalid data"
            ) from exc
        raise
    except UnexpectedResponse as exc:
        if exc.status_code == 404:
            raise ReferenceIndexError("reference index does not exist") from exc
        if exc.status_code == 429 or (
            exc.status_code is not None and exc.status_code >= 500
        ):
            raise ReferenceUnavailableError("reference store is unavailable") from exc
        raise ReferenceProviderError("reference store rejected the operation") from exc
