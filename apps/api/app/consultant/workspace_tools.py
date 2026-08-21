"""Model-facing virtual workspace tools for the consultant runtime."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from deepagents.backends.utils import file_data_to_string, validate_path
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict
from typing_extensions import override

from app.consultant.workspace_backend import (
    CandidatePolicyBackend,
    ConsultantWorkspaceBackendBinding,
)


WORKSPACE_FILESYSTEM_TOOL_NAMES = frozenset(
    {"ls", "read_file", "grep", "write_file", "edit_file", "delete"}
)
WORKSPACE_MUTATION_TOOL_NAMES = frozenset(
    {"write_file", "edit_file", "delete"}
)
CHECK_CANDIDATE_DOCUMENT_TOOL_NAME = "check_candidate_document"
WORKSPACE_TOOL_NAMES = frozenset(
    {*WORKSPACE_FILESYSTEM_TOOL_NAMES, CHECK_CANDIDATE_DOCUMENT_TOOL_NAME}
)
WORKSPACE_TOOL_DESCRIPTIONS = {
    "ls": "List entries in the scoped virtual JD workspace using an absolute POSIX path.",
    "read_file": "Read one file from the scoped virtual JD workspace.",
    "grep": "Search literal text in the scoped virtual JD workspace.",
    "write_file": "Create one new candidate resource; existing resources must be edited.",
    "edit_file": "Replace one exact unique string in a candidate resource; do not replace all.",
    "delete": "Delete one candidate entity resource; directories and protected resources are not deletable.",
}


class CandidateCheckPort(Protocol):
    """Application-owned semantic check boundary for the candidate after-state."""

    async def check_candidate_document(
        self,
        *,
        document_id: UUID,
        run_id: UUID,
        files: Mapping[str, str],
        tool_call_id: str,
        selected_skill_ids: tuple[str, ...],
        loaded_skill_ids: tuple[str, ...],
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class CandidateCheckToolBinding:
    """Bind the domain check to the one workspace/backend for a run."""

    runtime: CandidateCheckPort
    workspace: ConsultantWorkspaceBackendBinding

    @property
    def port(self) -> CandidateCheckPort:
        """Name the application boundary without duplicating the binding."""

        return self.runtime


class _EmptyCandidateCheckInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )


class _CandidateCheckToolInput(_EmptyCandidateCheckInput):
    """Internal schema that receives LangChain's hidden ToolRuntime."""

    runtime: ToolRuntime[Any, Any]


class _CandidateCheckStructuredTool(StructuredTool):
    """Expose no application or runtime arguments to the model."""

    @property
    def tool_call_schema(self) -> type[_EmptyCandidateCheckInput]:
        return _EmptyCandidateCheckInput


def _current_candidate_files(
    binding: CandidateCheckToolBinding,
    runtime: ToolRuntime[Any, Any],
) -> dict[str, str]:
    state = runtime.state
    if not isinstance(state, Mapping):
        raise RuntimeError("check_candidate_document requires the LangGraph state")
    raw_files = state.get("files")
    if not isinstance(raw_files, Mapping):
        raise RuntimeError(
            "check_candidate_document requires the current workspace files channel"
        )

    files: dict[str, str] = {}
    for raw_path, raw_file in raw_files.items():
        if not isinstance(raw_path, str):
            raise RuntimeError("check_candidate_document found a non-text candidate path")
        try:
            canonical_path = binding.workspace.candidate_backend.validate_candidate_file_path(
                raw_path
            )
        except ValueError as error:
            raise RuntimeError(
                f"check_candidate_document rejected candidate path {raw_path!r}: {error}"
            ) from error
        if canonical_path != raw_path:
            raise RuntimeError(
                f"check_candidate_document requires canonical candidate paths: {raw_path!r}"
            )
        if isinstance(raw_file, str):
            content = raw_file
        elif isinstance(raw_file, bytes):
            content = raw_file.decode("utf-8")
        elif isinstance(raw_file, Mapping):
            content = file_data_to_string(raw_file)
        else:
            raise RuntimeError(
                f"workspace file {raw_path!r} has an unsupported state value"
            )
        files[canonical_path] = content
    return dict(sorted(files.items()))


def _serialize_check_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    from app.consultant.candidate_publication import CandidateCheckResult

    if isinstance(result, CandidateCheckResult):
        payload = {
            "status": result.status,
            "candidate_revision": result.candidate_revision,
            "resource_digest": result.resource_digest,
            "action_handles": [str(action.action_id) for action in result.actions],
            "actions": [
                {
                    "operation": action.operation.value,
                    "path": action.path,
                    "target_key": action.target_key,
                }
                for action in result.actions
            ],
            "issues": list(result.issues),
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    model_dump_json = getattr(result, "model_dump_json", None)
    if callable(model_dump_json):
        return str(model_dump_json())
    model_dump = getattr(result, "model_dump", None)
    if callable(model_dump):
        result = model_dump(mode="json")
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)


def build_check_candidate_document_tool(
    *,
    binding: CandidateCheckToolBinding,
) -> BaseTool:
    """Build the payload-free async-only semantic check Tool for one workspace.

    The production consultant invokes this Tool through ``ainvoke`` because its
    CandidateCheckPort is async-only.
    """

    async def check_candidate_document(
        runtime: ToolRuntime[Any, Any],
    ) -> str:
        if runtime.tool_call_id is None:
            raise RuntimeError(
                "check_candidate_document is missing its provider call ID"
            )
        files = _current_candidate_files(binding, runtime)
        result = await binding.runtime.check_candidate_document(
            document_id=binding.workspace.document_id,
            run_id=binding.workspace.run_id,
            files=files,
            tool_call_id=runtime.tool_call_id,
            selected_skill_ids=binding.workspace.skill_backend.selected_skill_ids,
            loaded_skill_ids=binding.workspace.skill_backend.loaded_skill_ids,
        )
        return _serialize_check_result(result)

    return _CandidateCheckStructuredTool(
        name=CHECK_CANDIDATE_DOCUMENT_TOOL_NAME,
        description=(
            "Check the current candidate workspace after editor observations. "
            "The application reads the current files and returns actionable "
            "issues or a checked candidate receipt."
        ),
        args_schema=_CandidateCheckToolInput,
        coroutine=check_candidate_document,
    )


def _tool_call_path(
    tool_call: Mapping[str, Any],
    candidate_backend: CandidatePolicyBackend,
) -> str | None:
    args = tool_call.get("args")
    if not isinstance(args, Mapping):
        return None
    path = args.get("file_path")
    if not isinstance(path, str) or not path:
        return None
    try:
        canonical_path = validate_path(path)
        return candidate_backend.validate_candidate_file_path(canonical_path)
    except (TypeError, ValueError):
        return None


def _ordered_mutation_paths(
    tool_calls: Sequence[Mapping[str, Any]],
    candidate_backend: CandidatePolicyBackend,
) -> list[tuple[str, str | None]]:
    result: list[tuple[str, str | None]] = []
    for tool_call in sorted(
        tool_calls,
        key=lambda item: str(item.get("id", "")),
    ):
        name = str(tool_call.get("name", ""))
        if name not in WORKSPACE_MUTATION_TOOL_NAMES:
            continue
        result.append(
            (
                str(tool_call.get("id", "")),
                _tool_call_path(tool_call, candidate_backend),
            )
        )
    return result


def analyze_workspace_wave(
    tool_calls: Sequence[Mapping[str, Any]],
    *,
    candidate_backend: CandidatePolicyBackend,
) -> str | None:
    """Return one deterministic rejection for a conflicting complete tool wave."""

    has_check = any(
        str(tool_call.get("name", "")) == CHECK_CANDIDATE_DOCUMENT_TOOL_NAME
        for tool_call in tool_calls
    )
    mutation_paths = _ordered_mutation_paths(tool_calls, candidate_backend)
    invalid_mutation = next(
        (call_id for call_id, path in mutation_paths if path is None),
        None,
    )
    if invalid_mutation is not None:
        return (
            "Tool wave rejected: every candidate mutation must provide a valid "
            "file_path accepted by the virtual filesystem. No call in this wave "
            f"was run (invalid mutation call ID {invalid_mutation!r})."
        )
    if has_check and any(
        str(tool_call.get("name", "")) in WORKSPACE_MUTATION_TOOL_NAMES
        for tool_call in tool_calls
    ):
        return (
            "Tool wave rejected: check_candidate_document cannot run with a "
            "candidate mutation. Retry the mutations first, observe their results, "
            "then call check_candidate_document in a separate sequential wave."
        )

    valid_mutation_paths = [(call_id, path) for call_id, path in mutation_paths if path is not None]
    for index, (left_id, left_path) in enumerate(valid_mutation_paths):
        for right_id, right_path in valid_mutation_paths[index + 1 :]:
            assert left_path is not None and right_path is not None
            left_prefix = left_path.rstrip("/") + "/"
            right_prefix = right_path.rstrip("/") + "/"
            if (
                left_path == right_path
                or right_path.startswith(left_prefix)
                or left_path.startswith(right_prefix)
            ):
                return (
                    "Tool wave rejected: candidate mutation paths "
                    f"{left_path!r} and {right_path!r} "
                    "overlap. Retry overlapping mutations in separate sequential "
                    f"tool calls (call IDs {left_id!r} and {right_id!r})."
                )
    return None


def _last_ai_tool_calls(state: Any) -> Sequence[Mapping[str, Any]]:
    if isinstance(state, Mapping):
        messages = state.get("messages", ())
    else:
        messages = getattr(state, "messages", ())
    if not isinstance(messages, Sequence):
        return ()
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return message.tool_calls
        if isinstance(message, Mapping) and message.get("type") == "ai":
            tool_calls = message.get("tool_calls", ())
            return tool_calls if isinstance(tool_calls, Sequence) else ()
    return ()


def _wave_error_message(
    request: ToolCallRequest,
    candidate_backend: CandidatePolicyBackend,
) -> ToolMessage:
    conflict = analyze_workspace_wave(
        _last_ai_tool_calls(request.state),
        candidate_backend=candidate_backend,
    )
    if conflict is None:
        raise RuntimeError("workspace wave was not conflicting")
    tool_call = request.tool_call
    return ToolMessage(
        name=str(tool_call.get("name", "")),
        tool_call_id=str(tool_call.get("id", "")),
        status="error",
        content=conflict,
    )


class WorkspaceToolWaveMiddleware(AgentMiddleware):
    """Reject a complete conflicting workspace wave before any handler runs."""

    def __init__(self, *, candidate_backend: CandidatePolicyBackend) -> None:
        self._candidate_backend = candidate_backend

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        if (
            analyze_workspace_wave(
                _last_ai_tool_calls(request.state),
                candidate_backend=self._candidate_backend,
            )
            is not None
        ):
            return _wave_error_message(request, self._candidate_backend)
        return await handler(request)

    @override
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        if (
            analyze_workspace_wave(
                _last_ai_tool_calls(request.state),
                candidate_backend=self._candidate_backend,
            )
            is not None
        ):
            return _wave_error_message(request, self._candidate_backend)
        return handler(request)
