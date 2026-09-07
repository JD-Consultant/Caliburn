"""Official virtual filesystem tools over a private attempt's staged files."""
from deepagents.backends import CompositeBackend, StateBackend
from deepagents.backends.protocol import WriteResult
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain_core.tools import ToolException, tool

from analysis_agent.memory import MemoryArtifacts, ReadOnlyFiles
from analysis_agent.memory_tools import MEMORY_EDIT_GUIDANCE
from analysis_agent.memory_patch import PATHS, PATCH_GUIDANCE, MemoryPatchError, apply_staged_patch


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
    # Check the actual pair only after downloading both files. Per-file
    # validation above deliberately supplies an empty placeholder for its peer.
    if values["knowledge"].strip() and not values["guide"].strip():
        raise StagedMemoryValidationError(
            "/memory/guide.md is empty while /memory/knowledge.md contains knowledge. "
            "Write a concise topic guide pointing to the knowledge; preserve the body.")
    return values


def consolidation_tools(artifacts: MemoryArtifacts, thread_id: str):
    backend = StagedFiles(CompositeBackend(default=StateBackend(), routes={
        "/interviews/": artifacts.interview_backend()}), artifacts.document_id, thread_id=thread_id)
    filesystem = FilesystemMiddleware(backend=backend,
        tools=["ls", "grep", "read_file", "write_file"],
        custom_tool_descriptions={
            "ls": "List files in a directory when the file address is unknown. "
                  "Runtime-provided MEMORY_FILES and summary_path addresses are already valid; "
                  "read them directly without listing their directories first.",
            "write_file": "Write the complete contents of a staged memory file, replacing it entirely. "
                          "Use for a short file whose complete current contents are visible and whose "
                          "complete updated contents fit the output budget. Preserve unchanged details "
                          "and references. Read any existing content not already visible first; "
                          "a paged or truncated read is not the whole file. For large or partially "
                          "read files use apply_memory_patch. Never copy read_file line-number prefixes. "
                          + MEMORY_EDIT_GUIDANCE},
        human_message_token_limit_before_evict=None, tool_token_limit_before_evict=4000)

    @tool
    def apply_memory_patch(file_path: str, diff: str) -> str:
        """Patch an existing staged Memory file using a V4A diff (max 12000 characters).

        Read the affected range first. This stages changes, not publication.
        For initialization or a short fully visible file, write_file remains available.
        """
        backend._check_scope()
        try:
            changed = apply_staged_patch(file_path, diff)
        except MemoryPatchError as error:
            raise ToolException(str(error)) from error
        return f"{file_path}: {'Patch applied to staging' if changed else 'Content unchanged'}. Not yet published."

    apply_memory_patch.description += "\n\n" + PATCH_GUIDANCE + "\n\n" + MEMORY_EDIT_GUIDANCE
    apply_memory_patch.handle_tool_error = True

    @tool
    def validate_memory() -> str:
        """Optional preflight for staged format, size, references and a nonempty body's guide.

        Runtime always checks again at final completion. Does not check semantic truth.
        On error fix the named file; calling this tool again is optional, not publication.
        """
        backend._check_scope()
        try:
            staged_texts(artifacts)
        except StagedMemoryValidationError as error:
            raise ToolException(str(error)) from error
        return "Both staged files passed format/reference and guide-presence checks. Not yet published."

    validate_memory.handle_tool_error = True
    # Only tools, not generic message-eviction/summarization middleware hooks.
    return [*filesystem.tools, apply_memory_patch, validate_memory]
