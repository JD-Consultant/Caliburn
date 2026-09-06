"""Official virtual filesystem tools over a private attempt's staged files."""
from deepagents.backends import CompositeBackend, StateBackend
from deepagents.backends.protocol import EditResult, WriteResult
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain_core.tools import ToolException, tool

from analysis_agent.memory import MemoryArtifacts, ReadOnlyFiles


PATHS = {"knowledge": "/memory/knowledge.md", "guide": "/memory/guide.md"}


class StagedMemoryValidationError(ValueError):
    """Known model-correctable content error, never an arbitrary backend failure."""


def _correctable(error: ValueError) -> bool:
    # The shared validator predates typed errors. Fail closed on new/unknown
    # reasons, including infrastructure ValueErrors wrapped as reference errors.
    if str(error) in {
        "Memory line exceeds 2000 characters; split into lines without removing detail",
        "Memory guide exceeds 4000 characters; move details to knowledge",
    }:
        return True
    return str(error).startswith("Invalid Memory reference ") and str(error.__cause__) in {
        "Expected an existing runtime interview artifact address",
        "Artifact is unavailable in this document",
        "Invalid conversation reference; copy it from the interview record",
        "Conversation reference belongs to another document",
        "Conversation source is unavailable; do not substitute latest text",
        "Conversation source checkpoint does not match",
        "Conversation source message range is unavailable",
    }


class StagedFiles(ReadOnlyFiles):
    def write(self, file_path: str, content: str):
        self._check_scope()
        if file_path not in PATHS.values():
            return WriteResult(error="Write denied: only /memory/knowledge.md and /memory/guide.md are editable")
        return self._backend.write(file_path, content)

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False):
        self._check_scope()
        if file_path not in PATHS.values():
            return EditResult(error="Edit denied: only the two staged memory files are editable")
        return self._backend.edit(file_path, old_string, new_string, replace_all)


def staged_texts(artifacts: MemoryArtifacts) -> dict[str, str]:
    """Called in graph context, using public backend download semantics."""
    values = {}
    for name, result in zip(PATHS, StateBackend().download_files(list(PATHS.values())), strict=True):
        if result.error or result.content is None:
            raise ValueError(f"Missing staged {name}; create both memory files")
        content = result.content.decode("utf-8")
        try:
            # Reuse the same validator per file to attach the failing location;
            # this does not introduce different format/reference rules for B2.
            values[name] = artifacts.validate_texts(**{key: content if key == name else "" for key in PATHS})[name]
        except ValueError as error:
            if not _correctable(error):
                raise
            raise StagedMemoryValidationError(f"{PATHS[name]}: {error}") from error
    return values


def consolidation_tools(artifacts: MemoryArtifacts, thread_id: str):
    backend = StagedFiles(CompositeBackend(default=StateBackend(), routes={
        "/interviews/": artifacts.interview_backend()}), artifacts.document_id, thread_id=thread_id)
    filesystem = FilesystemMiddleware(backend=backend,
        tools=["ls", "grep", "read_file", "write_file", "edit_file"],
        human_message_token_limit_before_evict=None, tool_token_limit_before_evict=4000)

    @tool
    def validate_memory() -> str:
        """Check both staged memory files for readable format, size and existing references.

        Does not check semantic truth. On error edit the staged files then validate again.
        """
        backend._check_scope()
        try:
            staged_texts(artifacts)
        except StagedMemoryValidationError as error:
            raise ToolException(str(error)) from error
        return "Both staged files passed format/reference checks. Not yet published."

    validate_memory.handle_tool_error = True
    # Only tools, not generic message-eviction/summarization middleware hooks.
    return [*filesystem.tools, validate_memory]
