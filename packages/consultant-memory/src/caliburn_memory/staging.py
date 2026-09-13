"""Validate the two existing native staged Memory files, without publishing.

Extracted from the verified consolidation_tools.py. Only known content errors
are model-correctable; unknown backend/source exceptions must stop execution.
"""
from deepagents.backends import StateBackend

from .memory import MemoryArtifacts
from .patch import PATHS
from .sources import InvalidSourceReference


class StagedMemoryValidationError(ValueError):
    """Known content/format/reference failure, never infrastructure failure."""


def _correctable(error):
    if type(error) is not ValueError:
        return False
    if str(error) in {
        "Memory line exceeds 2000 characters; split into lines without removing detail",
        "Memory guide exceeds 4000 characters; move details to knowledge",
    }:
        return True
    cause = error.__cause__
    return str(error).startswith("Invalid Memory reference ") and (
        isinstance(cause, InvalidSourceReference)
        or type(cause) is ValueError and str(cause) in {
            "Expected an existing runtime interview artifact address",
            "Artifact is unavailable in this document",
        })


def staged_texts(artifacts: MemoryArtifacts) -> dict[str, str]:
    values = {}
    for name, result in zip(PATHS, StateBackend().download_files(list(PATHS.values())), strict=True):
        if result.error == "file_not_found":
            raise StagedMemoryValidationError(f"Missing staged {name}; create both memory files")
        if result.error or result.content is None:
            raise RuntimeError("Staged Memory unavailable")
        content = result.content.decode("utf-8")
        try:
            values[name] = artifacts.validate_texts(**{
                key: content if key == name else "" for key in PATHS})[name]
        except ValueError as error:
            if not _correctable(error):
                raise
            # Path and actionable guidance only, never wrapped source I/O text.
            detail = ("Invalid Memory reference; copy an existing address from a read result."
                      if str(error).startswith("Invalid Memory reference ") else str(error))
            raise StagedMemoryValidationError(f"{PATHS[name]}: {detail}") from error
    if values["knowledge"].strip() and not values["guide"].strip():
        raise StagedMemoryValidationError("/memory/guide.md is empty while knowledge contains work; write a concise guide.")
    return values
