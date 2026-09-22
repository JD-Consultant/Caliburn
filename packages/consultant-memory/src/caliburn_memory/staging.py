"""The staged Memory pair: its validation, and the tools that edit it.

Adopted from the verified consolidation_tools.py. Only known content errors are
model-correctable; unknown backend/source exceptions must stop execution. The
editable surface is exactly the two staged files: interview details stay
readable and every other path is denied a writer rather than being absent.
"""
from deepagents.backends import CompositeBackend, StateBackend
from deepagents.backends.protocol import WriteResult
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain_core.tools import ToolException, tool

from .memory import MemoryArtifacts, ReadOnlyFiles
from .patch import PATCH_GUIDANCE, PATHS, MemoryPatchError, apply_staged_patch
from .read_tools import MEMORY_EDIT_GUIDANCE
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


class StagedFiles(ReadOnlyFiles):
    """Reads reach the details; writes reach only the two staged Memory files."""

    def write(self, file_path: str, content: str):
        self._check_scope()
        if file_path not in PATHS.values():
            return WriteResult(error="Write denied: only /memory/knowledge.md and /memory/guide.md are editable")
        return self._backend.write(file_path, content)


def consolidation_tools(artifacts: MemoryArtifacts, thread_id: str):
    """Official virtual filesystem tools over one private attempt's staged files.

    Only the tools are taken from the middleware: no model or message hook, no
    automatic offload and no summarisation. Staging is not publication, and the
    interview details routed in here stay read-only.
    """
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
                          "complete updated contents fit the output budget; prefer this for changes across several passages. "
                          "Minimal semantic changes do not require a patch. Preserve unchanged details "
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
