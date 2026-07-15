"""Domain errors expose stable reason codes, never parser-dependent strings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .reason_codes import ReasonCode


class DomainViolation(ValueError):
    def __init__(
        self,
        reason_code: ReasonCode,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.details = dict(details or {})
