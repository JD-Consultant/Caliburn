"""Immutable-by-construction artifact I/O, not the B/C publication authority."""

from dataclasses import dataclass
import re
from uuid import uuid4

from deepagents.backends import CompositeBackend, StoreBackend
from deepagents.backends.protocol import BackendProtocol, LsResult
from langgraph.config import get_config
from langgraph.store.base import BaseStore

from analysis_agent.sources import parse_reference


@dataclass(frozen=True)
class ExtractionFiles:
    summary_path: str
    candidates_path: str


@dataclass(frozen=True)
class MemoryVersion:
    document_id: str
    version_id: str


def _prepare_text(text: str, *, guide: bool = False) -> str:
    if not isinstance(text, str):
        raise ValueError("Memory content must be text")
    # Backend slice uses splitlines, while native grep/formatter use LF. Unify
    # generated artifact line boundaries before both validation and persistence.
    # Canonical conversation text is NOT changed by this normalization.
    text = re.sub(r"\r\n|[\r\v\f\x1c-\x1e\x85\u2028\u2029]", "\n", text)
    if any(len(line) > 2000 for line in text.split("\n")):
        raise ValueError("Memory line exceeds 2000 characters; split into lines without removing detail")
    if guide and len(text) > 4000:
        raise ValueError("Memory guide exceeds 4000 characters; move details to knowledge")
    return text


class ReadOnlyFiles(BackendProtocol):
    """Reuse public backend results/pagination; expose no write implementation.

    This is not a filesystem on the user's computer. The official tool formatter
    bounds model-visible pages; direct runtime reads return the requested window.
    """

    def __init__(self, backend: BackendProtocol, document_id: str):
        self._backend = backend
        self.document_id = document_id

    def _check_scope(self):
        try:
            config = get_config()
        except RuntimeError:
            return  # trusted run-external loader; no graph context exists
        if config.get("configurable", {}).get("thread_id") != self.document_id:
            raise ValueError("Memory read belongs to another document")

    def read(self, file_path: str, offset: int = 0, limit: int = 2000):
        self._check_scope()
        return self._backend.read(file_path, offset=offset, limit=min(limit, 2000))

    def ls(self, path: str):
        self._check_scope()
        result = self._backend.ls(path)
        if result.entries and len(result.entries) > 100:
            return LsResult(error="Directory has over 100 entries. Read a known link or search a narrower path; this is not a complete inventory.")
        return result

    def grep(self, pattern: str, path: str | None = None, glob: str | None = None, *, max_count: int | None = None):
        self._check_scope()
        return self._backend.grep(pattern, path, glob, max_count=min(max_count, 4) if max_count is not None else 4)


class MemoryArtifacts:
    def __init__(self, store: BaseStore, document_id: str):
        if not document_id or any(c in document_id for c in ("*", ".", "/", "\\")):
            raise ValueError("Expected runtime document identity, not a path")
        self.store = store
        self.document_id = document_id

    def _backend(self, *suffix: str):
        namespace = ("q019-memory", self.document_id, *suffix)
        return StoreBackend(store=self.store, namespace=lambda _rt: namespace)

    @staticmethod
    def _save(backend: BackendProtocol, path: str, content: str):
        content = _prepare_text(content)
        result = backend.write(path, content)
        if result.error:
            raise RuntimeError(f"Artifact save failed: {result.error}")
        loaded = backend.download_files([path])[0]
        if loaded.error or loaded.content != content.encode("utf-8"):
            raise RuntimeError("Artifact save could not be verified; not ready for handoff")

    def save_extraction(self, *, summary: str, candidates: str, slug: str, source_reference: str) -> ExtractionFiles:
        parse_reference(source_reference, self.document_id)
        summary = _prepare_text(summary)
        candidates = _prepare_text(candidates)
        name = re.sub(r"[^\w -]", "", slug, flags=re.UNICODE).strip()[:80] or "訪談詳記"
        batch = str(uuid4())
        backend = self._backend("interviews")
        header = f"# {name}\n\nSource: {source_reference}\nSource scope: complete input range, not per-sentence attribution.\n\n"
        summary_path = f"/{batch}/summary.md"
        candidates_path = f"/{batch}/candidates.md"
        self._save(backend, summary_path, header + summary)
        self._save(backend, candidates_path, f"Summary: /interviews{summary_path}\n" + header + candidates)
        return ExtractionFiles("/interviews" + summary_path, "/interviews" + candidates_path)

    def save_memory(self, *, knowledge: str, guide: str) -> MemoryVersion:
        """Return a prepared version only. Selecting/publishing current is separate."""
        knowledge = _prepare_text(knowledge)
        guide = _prepare_text(guide, guide=True)
        interviews = self._backend("interviews")
        # Addresses are runtime-issued literal ASCII paths, not arbitrary URLs.
        # Validate their occurrences regardless of Markdown presentation (inline,
        # reference-style, code or bare path); this is not a Markdown parser.
        for path in set(re.findall(r"/interviews/[A-Za-z0-9_./-]+", knowledge + "\n" + guide)):
            # Issued filenames end in .md, never a period. A bare address can
            # be followed by sentence punctuation without changing its target.
            path = path.rstrip(".")
            if interviews.read(path.removeprefix("/interviews"), limit=1).error:
                raise ValueError("Memory reference is unavailable in this document")
        version = MemoryVersion(self.document_id, str(uuid4()))
        backend = self._backend("versions", version.version_id)
        self._save(backend, "/memory/knowledge.md", knowledge)
        self._save(backend, "/memory/guide.md", guide)
        return version

    def _view(self, version: MemoryVersion):
        if version.document_id != self.document_id:
            raise ValueError("Memory version belongs to another document")
        return CompositeBackend(default=self._backend("versions", version.version_id), routes={"/interviews/": self._backend("interviews")})

    def reader(self, version: MemoryVersion) -> ReadOnlyFiles:
        return ReadOnlyFiles(self._view(version), self.document_id)

    def guide(self, version: MemoryVersion) -> str:
        result = self._view(version).download_files(["/memory/guide.md"])[0]
        if result.error or result.content is None:
            raise ValueError("Memory guide is unavailable; this version is not ready")
        guide = result.content.decode("utf-8")
        return _prepare_text(guide, guide=True)
