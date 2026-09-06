"""Official virtual filesystem tools over a private attempt's staged files."""
from deepagents.backends import CompositeBackend, StateBackend
from deepagents.backends.protocol import EditResult, WriteResult
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain_core.tools import ToolException, tool

from analysis_agent.memory import MemoryArtifacts, ReadOnlyFiles


PATHS = {"knowledge": "/memory/knowledge.md", "guide": "/memory/guide.md"}


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
        values[name] = result.content.decode("utf-8")
    return artifacts.validate_texts(**values)


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
        except ValueError as error:
            raise ToolException(str(error)) from error
        return "Both staged files passed format/reference checks. Not yet published."

    validate_memory.handle_tool_error = True
    # Only tools, not generic message-eviction/summarization middleware hooks.
    return [*filesystem.tools, validate_memory]
