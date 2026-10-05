"""Explicit target settings; never load a legacy dotenv or infer its database."""

import math
import os
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import httpx2
from openai.types.shared.reasoning_effort import ReasoningEffort

from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.adapters.openai_models import model_profile


@dataclass(frozen=True, slots=True)
class ModelSettings:
    """Researched direct model and bounded operational defaults; no provider fallback."""

    api_key: str = field(repr=False)
    model: str = "gpt-6-luna"
    reasoning_effort: ReasoningEffort = "high"
    max_output_tokens: int = 16_384
    max_model_steps: int = 64
    max_tool_calls_per_step: int = 32
    max_attempts_per_request: int = 8
    max_outbound_attempts: int = 512
    max_compactions: int = 4
    turn_timeout_seconds: int = 1_800
    request_timeout_seconds: float = 120.0
    # Product entrypoints leave this unset. Paid evaluation harnesses may opt in.
    max_cost_usd: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("Configure an OpenAI key")
        profile = model_profile(self.model)
        if self.reasoning_effort not in profile.reasoning_efforts:
            raise ValueError("Unsupported reasoning effort")
        for value in (
            self.max_output_tokens,
            self.max_model_steps,
            self.max_tool_calls_per_step,
            self.max_attempts_per_request,
            self.max_outbound_attempts,
            self.max_compactions,
            self.turn_timeout_seconds,
        ):
            if type(value) is not int or value < 1:
                raise ValueError("Model limits must be positive integers")
        if (
            self.max_output_tokens > profile.max_output_tokens
            or not 0 < self.request_timeout_seconds <= 900
        ):
            raise ValueError("Model output or timeout exceeds the configured capacity")
        if self.max_cost_usd is not None and (
            not self.max_cost_usd.is_finite() or self.max_cost_usd <= 0
        ):
            raise ValueError("An explicit evaluation cost budget must be finite and positive")


@dataclass(frozen=True, slots=True)
class PdfSettings:
    font_path: Path
    executable_path: Path | None = None


@dataclass(frozen=True, slots=True)
class OccupationReferenceSettings:
    """Explicit external service origin and bounded request duration; disabled by omission."""

    base_url: str
    request_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        message = "Reference service must use an explicit HTTP(S) origin without credentials"
        if re.fullmatch(r"https?://[A-Za-z0-9._:\[\]-]+/?", self.base_url) is None:
            raise ValueError(message)
        try:
            origin = httpx2.URL(self.base_url)
        except httpx2.InvalidURL:
            raise ValueError(message) from None
        if (
            not origin.host
            or self.base_url.removesuffix("/").endswith(":")
            or (origin.port is not None and not 1 <= origin.port <= 65_535)
        ):
            raise ValueError(message)
        if (
            type(self.request_timeout_seconds) not in (int, float)
            or not math.isfinite(self.request_timeout_seconds)
            or self.request_timeout_seconds <= 0
        ):
            raise ValueError("Reference request timeout must be finite and positive")


@dataclass(frozen=True, slots=True)
class Settings:
    database: DatabaseSettings | None = None
    model: ModelSettings | None = None
    pdf: PdfSettings | None = None
    dev_origin: str | None = None
    web_build_directory: Path | None = None
    occupation_references: OccupationReferenceSettings | None = None

    def __post_init__(self) -> None:
        if self.web_build_directory is not None and not self.web_build_directory.is_absolute():
            raise ValueError("Web build directory must be an explicit absolute path")
        if self.dev_origin is None:
            return
        match = re.fullmatch(
            r"http://(?:127\.0\.0\.1|localhost|\[::1\]):([1-9][0-9]{0,4})",
            self.dev_origin,
        )
        if match is None or int(match[1]) > 65_535:
            raise ValueError("Dev origin must be one exact loopback HTTP origin with a port")

    @classmethod
    def from_environment(cls) -> Settings:
        database_url = os.environ.get("CALIBURN_DATABASE_URL")
        openai_key = os.environ.get("OPENAI_API_KEY")
        pdf_font = os.environ.get("CALIBURN_PDF_FONT_PATH")
        pdf_browser = os.environ.get("CALIBURN_PDF_CHROMIUM_PATH")
        web_build = os.environ.get("CALIBURN_WEB_BUILD_DIRECTORY")
        reference_url = os.environ.get("CALIBURN_OCCUPATION_REFERENCE_URL")
        return cls(
            dev_origin=os.environ.get("CALIBURN_DEV_ORIGIN"),
            web_build_directory=Path(web_build) if web_build is not None else None,
            database=DatabaseSettings(
                url=database_url,
                schema=os.environ.get("CALIBURN_DATABASE_SCHEMA", "caliburn"),
            )
            if database_url
            else None,
            model=ModelSettings(api_key=openai_key) if openai_key else None,
            pdf=PdfSettings(
                font_path=Path(pdf_font),
                executable_path=Path(pdf_browser) if pdf_browser else None,
            )
            if pdf_font
            else None,
            occupation_references=OccupationReferenceSettings(
                base_url=reference_url,
                request_timeout_seconds=float(
                    os.environ.get("CALIBURN_OCCUPATION_REFERENCE_REQUEST_TIMEOUT_SECONDS", "30")
                ),
            )
            if reference_url is not None
            else None,
        )
