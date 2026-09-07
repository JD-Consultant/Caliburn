"""One-file SDK patch over staged StateBackend, never over published Memory.

Only the public apply_diff function is used; no SDK Runner/client or network.
Matcher semantics and known first-match limits: CT10 research, SDK 0.22.0.
"""
from agents import apply_diff
from deepagents.backends import StateBackend


PATHS = {"knowledge": "/memory/knowledge.md", "guide": "/memory/guide.md"}
MAX_PATCH_CHARACTERS = 12000

PATCH_GUIDANCE = (
    "Provide a V4A diff body for one existing file, not a full patch envelope. "
    "Use @@ to start a hunk; prefix unchanged context lines with one space, "
    "removed lines with -, added lines with +. Include complete source lines "
    "and real surrounding context that identifies the intended section. Example: "
    "@@\n # Case B\n-Old fact\n+Corrected fact\n Unchanged detail\n"
    "Do not use numeric unified-diff headers, markdown fences, *** Begin Patch, "
    "or file operation headers. A terminal *** End Patch is optional. "
    "Do not copy read_file's line-number gutter. "
    "Repeated text needs distinguishing actual context lines, not just an @@ label: "
    "the SDK uses the first match and a single label alone is not a strict guard. "
    "On a mismatch, read the affected range and revise the patch, not guessed content. "
    "After a successful change, use the latest staged text for subsequent patches."
)


class MemoryPatchError(ValueError):
    """Model-correctable patch error, not a storage/infrastructure exception."""


def apply_staged_patch(file_path: str, diff: str) -> bool:
    """Return whether content changed; queue a write only after full SDK success.

    The caller enforces its existing graph/document scope. This boundary accepts
    only the SDK's single-file diff body: the SDK otherwise stops at operation
    delimiters and could ignore trailing content while appearing successful.
    """
    if file_path not in PATHS.values():
        raise MemoryPatchError("Patch denied: only the two existing /memory files are editable")
    if not diff.strip() or len(diff) > MAX_PATCH_CHARACTERS:
        raise MemoryPatchError("Provide a nonempty diff, at most 12000 characters")
    lines = diff.rstrip('\r\n').splitlines()
    terminal_sequences = {('*** End Patch',), ('*** End of File',),
                          ('*** End of File', '*** End Patch')}
    if any(line.startswith('***') and tuple(lines[index:]) not in terminal_sequences
           for index, line in enumerate(lines)):
        raise MemoryPatchError("Provide only one file's diff body; omit patch/file operation headers")
    if not any(line.startswith(('+', '-')) for line in lines):
        raise MemoryPatchError("Diff must include added or removed source lines")
    backend = StateBackend()
    source = backend.download_files([file_path])[0]
    if source.error == 'file_not_found':
        raise MemoryPatchError(f"File not found: {file_path}; read existing Memory first")
    if source.error or source.content is None:
        raise RuntimeError(f"Unable to read staged Memory: {source.error}")
    original = source.content.decode('utf-8')
    try:
        revised = apply_diff(original, diff)
    except ValueError as error:
        raise MemoryPatchError(f"{file_path}: {str(error)[:1000]}. Read the affected range and revise the diff; nothing from this patch was written.") from error
    if revised == original:
        return False
    result = backend.write(file_path, revised)
    if result.error:
        raise RuntimeError(f"Unable to write staged Memory: {result.error}")
    return True
