"""Native read tools for an App-supplied, document-scoped Memory backend.

Adopted from analysis-only-agent 033540cef870d1f92baa5c69133a799231c46d48,
analysis_agent/memory_tools.py (CT25 readonly_file_tools/descriptions only).
Verified against the installed MIT Deep Agents 0.7.13 implementation on
2026-09-13: https://github.com/langchain-ai/deepagents/blob/deepagents%3D%3D0.7.13/
libs/deepagents/deepagents/middleware/filesystem.py

FilesystemMiddleware.tools and its public allowlist retain native schemas,
formatting and pagination. BaseTool validation errors use fixed safe feedback
instead of echoing input arguments; other native ToolMessage errors remain.
The middleware itself is never
registered: no model/message hooks, automatic offload, or scrubbing. The App
owns fixed-version selection and the backend owns document scope. This module
does not provide host filesystem access, Skill assets, writers or a provider.
"""
from deepagents.backends.protocol import BackendProtocol
from deepagents.middleware.filesystem import FilesystemMiddleware
from langchain_core.tools import BaseTool


# Both live repair and background editing must retain unaffected knowledge.
# https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#str_replace
# Display gutter contract: deepagents 0.7.13 read_file / format_content_with_line_numbers.
# https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/middleware/filesystem.py
MEMORY_EDIT_GUIDANCE = (
    "Prefer the smallest local change with distinguishing surrounding context. "
    "read_file's line number and two following separator spaces are display only: "
    "'12  - item' has source text '- item'. Preserve actual source indentation, "
    "not that display prefix. After a missing match, re-read the affected range "
    "instead of guessing source lines or changing unrelated text. "
    "Preserve established facts, scope, exceptions, and references that the new "
    "information does not change. Omission from new information is not withdrawal "
    "of an established fact. If replacing a whole sentence, section, or file, "
    "carry unchanged job-relevant details into the replacement; do not summarize "
    "them away. Unrelated chatter and repeated wording may be omitted, but "
    "low-frequency work, responsibility boundaries and meaningful case differences "
    "are not irrelevant merely because they are uncommon."
)

READONLY_TOOL_DESCRIPTIONS = {
    "ls": (
        "Lists files in a directory to discover unknown paths.\n"
        "\n"
        "When the guide or a tool result already provides the relevant file path, use read_file directly. "
        "Listing a directory is not a prerequisite for every read."
    ),
    "read_file": (
        "Reads available text Memory and interview-detail files. A missing path returns an error; "
        "this is not a host-filesystem or general media tool.\n"
        "\n"
        "Usage:\n"
        "- By default, it reads up to 100 lines starting from the beginning of the file. Use "
        "`offset`/`limit` to page through large files instead of reading them whole.\n"
        "- Results are returned with line numbers starting at `offset` + 1 (1 by default), then two spaces, "
        "then the source line. Never include these line-number prefixes when editing.\n"
        "- Lines over 5,000 characters are split with continuation markers (e.g. 5.1, 5.2); `limit` counts "
        "source lines, so continuation rows do not consume the budget.\n"
        "- Use one tool call at a time in this runtime; make further reads only when the preceding result "
        "leaves relevant information missing.\n"
        "- An empty file returns a system-reminder warning in place of contents.\n"
        "- Always read a file before editing it."
    ),
    "grep": (
        "Search for a LITERAL text pattern across files (NOT regex).\n"
        "\n"
        "The pattern is matched verbatim: regex metacharacters are ordinary characters, not operators. To "
        "match any of several strings, run a separate grep for each; `grep(pattern=\"foo|bar\")` searches for "
        "the literal text \"foo|bar\", and `.*` or `\\.` match those characters literally.\n"
        "- No execution tool is available here. For alternatives, use separate literal patterns or read the "
        "relevant file range.\n"
        "\n"
        "Returns matching files or content per `output_mode`."
    ),
}


def readonly_file_tools(backend: BackendProtocol) -> list[BaseTool]:
    """Return official ls/read_file/grep tools, without registering hooks."""
    filesystem = FilesystemMiddleware(
        backend=backend,
        tools=["ls", "grep", "read_file"],
        custom_tool_descriptions=READONLY_TOOL_DESCRIPTIONS,
        human_message_token_limit_before_evict=None,
        tool_token_limit_before_evict=4000,
    )
    # The native read implementation also uses this token budget for pagination;
    # returning only tools keeps that behavior without installing offload hooks.
    for tool in filesystem.tools:
        # Public BaseTool policy catches Pydantic errors before ToolNode's
        # default validation handler would include the complete input kwargs.
        tool.handle_validation_error = (
            "invalid_input: 工具參數不符；請依工具定義修正欄位型別及必填參數後重試。"
        )
    return filesystem.tools
