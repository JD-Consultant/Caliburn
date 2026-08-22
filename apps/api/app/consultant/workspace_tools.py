"""Model-facing virtual workspace tools for the consultant runtime."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from deepagents.backends.utils import validate_path
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command
from typing_extensions import override

from app.consultant.workspace_backend import WorkspacePolicyBackend


WORKSPACE_FILESYSTEM_TOOL_NAMES = frozenset(
    {"ls", "read_file", "grep", "write_file", "edit_file", "delete"}
)
WORKSPACE_MUTATION_TOOL_NAMES = frozenset(
    {"write_file", "edit_file", "delete"}
)
WORKSPACE_TOOL_NAMES = WORKSPACE_FILESYSTEM_TOOL_NAMES
WORKSPACE_TOOL_DESCRIPTIONS = {
    "ls": "List entries in the scoped virtual JD workspace using an absolute POSIX path.",
    "read_file": "Read one file from the scoped virtual JD workspace.",
    "grep": "Search literal text in the scoped virtual JD workspace.",
    "write_file": (
        "Create one new JSON resource below /workspace/; edit existing "
        "resources instead. Choose the next unused zero-padded handle and replace "
        "all example values. Each JSONL example means file_path is the workspace "
        "root plus path, and content is JSON.stringify(content). Workspace evidence "
        "uses occurrence=null for a unique quote or a positive 1-based occurrence "
        "when repeated. OPKS alternatives: opks/p/p-###.json kind=indicator, "
        "opks/k/k-###.json kind=knowledge, opks/s/s-###.json kind=skill.\n"
        'CREATE_EXAMPLE {"path":"duties/duty-002.json","content":{"handle":"duty-002","statement":"管理供應商交期"}}\n'
        'CREATE_EXAMPLE {"path":"tasks/task-002.json","content":{"handle":"task-002","duty_handle":"duty-002","statement":"核對供應商交期","action":"核對","object":"供應商交期"}}\n'
        'CREATE_EXAMPLE {"path":"opks/o/o-001.json","content":{"handle":"o-001","kind":"output","text":"已核對的供應商交期","task_handles":["task-002"],"evidence":[{"source_handle":"source-002","quote":"目前內容第一行。","occurrence":null,"skill_ids":["output"]}]}}'
    ),
    "edit_file": "Replace one exact unique string in a workspace resource; do not replace all.",
    "delete": "Delete one workspace entity resource; directories and the header are not deletable.",
}


def _tool_call_path(
    tool_call: Mapping[str, Any],
    workspace_backend: WorkspacePolicyBackend,
) -> str | None:
    args = tool_call.get("args")
    if not isinstance(args, Mapping):
        return None
    path = args.get("file_path")
    if not isinstance(path, str) or not path:
        return None
    try:
        canonical_path = validate_path(path)
        return workspace_backend.validate_workspace_file_path(canonical_path)
    except (TypeError, ValueError):
        return None


def _ordered_mutation_paths(
    tool_calls: Sequence[Mapping[str, Any]],
    workspace_backend: WorkspacePolicyBackend,
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
                _tool_call_path(tool_call, workspace_backend),
            )
        )
    return result


def analyze_workspace_wave(
    tool_calls: Sequence[Mapping[str, Any]],
    *,
    workspace_backend: WorkspacePolicyBackend,
) -> str | None:
    """Return one deterministic rejection for a conflicting complete tool wave."""

    mutation_paths = _ordered_mutation_paths(tool_calls, workspace_backend)
    invalid_mutation = next(
        (call_id for call_id, path in mutation_paths if path is None),
        None,
    )
    if invalid_mutation is not None:
        return (
            "Tool wave rejected: every workspace mutation must provide a valid "
            "file_path accepted by the virtual filesystem. No call in this wave "
            f"was run (invalid mutation call ID {invalid_mutation!r})."
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
                    "Tool wave rejected: workspace mutation paths "
                    f"{left_path!r} and {right_path!r} "
                    "overlap. Retry overlapping mutations in separate sequential "
                    f"tool calls (call IDs {left_id!r} and {right_id!r})."
                )
    return None


def last_ai_tool_calls(state: Any) -> Sequence[Mapping[str, Any]]:
    """Return the latest complete model wave using framework message state."""

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
    workspace_backend: WorkspacePolicyBackend,
) -> ToolMessage:
    conflict = analyze_workspace_wave(
        last_ai_tool_calls(request.state),
        workspace_backend=workspace_backend,
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

    def __init__(self, *, workspace_backend: WorkspacePolicyBackend) -> None:
        self._workspace_backend = workspace_backend

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        if (
            analyze_workspace_wave(
                last_ai_tool_calls(request.state),
                workspace_backend=self._workspace_backend,
            )
            is not None
        ):
            return _wave_error_message(request, self._workspace_backend)
        return await handler(request)

    @override
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        if (
            analyze_workspace_wave(
                last_ai_tool_calls(request.state),
                workspace_backend=self._workspace_backend,
            )
            is not None
        ):
            return _wave_error_message(request, self._workspace_backend)
        return handler(request)
