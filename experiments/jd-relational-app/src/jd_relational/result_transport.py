"""Validate an App-observed result; this adapter never establishes durability."""

import json

from pydantic import ValidationError

from .generated.results import MutationResult


class ResultValidationError(ValueError):
    pass


def validate_result(result: dict) -> dict:
    try:
        value = MutationResult.model_validate(result, strict=True).model_dump(mode="json")
        # JSON text may otherwise contain a lone surrogate rejected at the wire.
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        return value
    except (ValidationError, ValueError, TypeError, UnicodeError, RecursionError):
        raise ResultValidationError("invalid_result") from None
