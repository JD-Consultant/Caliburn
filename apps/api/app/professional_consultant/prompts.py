"""Versioned R1 operation prompts, independent of provider wire formats."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from .contracts import ConsultantContract, Identifier, SourceText


class OperationName(StrEnum):
    TASK_DISCOVERY = "task.discover"
    TURN_UNDERSTAND = "turn.understand"
    WORK_RECONCILE_DECIDE = "work.reconcile_decide"


class PromptProfile(StrEnum):
    MINIMAL = "minimal"
    FULL = "full"


class PromptArtifact(ConsultantContract):
    prompt_id: Identifier
    operation: OperationName
    profile: PromptProfile
    content: SourceText


_ASSET_ROOT = Path(__file__).with_name("prompt_assets")
_PROMPTS = {
    (OperationName.TASK_DISCOVERY, PromptProfile.MINIMAL): (
        "task-discover.minimal.v1",
        "task-discover.minimal.v1.txt",
    ),
    (OperationName.TASK_DISCOVERY, PromptProfile.FULL): (
        "task-discover.full.v1",
        "task-discover.full.v1.txt",
    ),
    (OperationName.TURN_UNDERSTAND, PromptProfile.FULL): (
        "turn-understand.full.v1",
        "turn-understand.full.v1.txt",
    ),
    (OperationName.WORK_RECONCILE_DECIDE, PromptProfile.FULL): (
        "work-reconcile-decide.full.v1",
        "work-reconcile-decide.full.v1.txt",
    ),
}


def prompt_for(
    operation: OperationName, profile: PromptProfile
) -> PromptArtifact:
    """Load one committed prompt artifact by its semantic coordinates."""

    try:
        prompt_id, filename = _PROMPTS[(operation, profile)]
    except KeyError as exc:
        raise ValueError(
            f"no prompt for operation={operation.value} profile={profile.value}"
        ) from exc
    content = (_ASSET_ROOT / filename).read_text(encoding="utf-8")
    return PromptArtifact(
        prompt_id=prompt_id,
        operation=operation,
        profile=profile,
        content=content,
    )
