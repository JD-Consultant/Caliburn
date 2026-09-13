"""Immutable-by-construction artifact I/O, not the B/C publication authority."""

from dataclasses import dataclass
import hashlib
import json
import re
from uuid import UUID, uuid4

from deepagents.backends import CompositeBackend, StoreBackend
from deepagents.backends.protocol import BackendProtocol, LsResult
from langgraph.config import get_config
from langgraph.store.base import BaseStore

from caliburn_memory.references import controlled_references
from caliburn_memory.sources import SourceReader


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

    def __init__(self, backend: BackendProtocol, document_id: str, *, thread_id: str | None = None):
        self._backend = backend
        self.document_id = document_id
        self._thread_id = thread_id or document_id

    def _check_scope(self):
        try:
            config = get_config()
        except RuntimeError:
            return  # trusted run-external loader; no graph context exists
        if config.get("configurable", {}).get("thread_id") != self._thread_id:
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
    def __init__(self, store: BaseStore, document_id: str, *, source: SourceReader | None = None):
        if not document_id or any(c in document_id for c in ("*", ".", "/", "\\")):
            raise ValueError("Expected runtime document identity, not a path")
        self.store = store
        self.document_id = document_id
        if source is not None and source.document_id != document_id:
            raise ValueError("Memory source reader belongs to another document")
        self.source = source

    def validate_source(self, reference: str) -> None:
        """Validate through the source owner without reading its storage.

        Publication may look up an original receipt after this shape/scope
        check, even when the original content is temporarily unavailable.
        """
        if self.source is None:
            raise ValueError("Canonical source reader is not configured")
        if self.source.document_id != self.document_id:
            raise ValueError("Memory source reader belongs to another document")
        self.source.validate_reference(reference)

    def validate_pair(self, source_reference: str, context_reference: str) -> None:
        """An extraction artifact records the pair it was planned as.

        Both addresses being valid, at one root and inside one budget, does not
        make them one pair; the owner proves that. Saving or reading back a
        recombined pair would hand re-extraction the wrong prefix.
        """
        if self.source is None:
            raise ValueError("Canonical source reader is not configured")
        self.source.validate_pair(source_reference, context_reference)

    def _backend(self, *suffix: str):
        namespace = ("q019-memory", self.document_id, *suffix)
        return StoreBackend(store=self.store, namespace=lambda _rt: namespace)

    def interview_backend(self) -> BackendProtocol:
        """Runtime composition only; model-facing callers wrap this as read-only."""
        return self._backend("interviews")

    def read_text(self, path: str, version: MemoryVersion | None = None) -> str:
        if version is None:
            if not path.startswith("/interviews/"):
                raise ValueError("Expected an interview artifact address")
            backend, key = self.interview_backend(), path.removeprefix("/interviews")
        else:
            if path not in ("/memory/knowledge.md", "/memory/guide.md"):
                raise ValueError("Expected a memory artifact address")
            backend, key = self._view(version), path
        loaded = backend.download_files([key])[0]
        if loaded.error or loaded.content is None:
            raise ValueError(f"Artifact unavailable: {path}")
        return loaded.content.decode("utf-8")

    def validate_texts(self, knowledge: str, guide: str) -> dict[str, str]:
        knowledge, guide = _prepare_text(knowledge), _prepare_text(guide, guide=True)
        self._validate_links(knowledge, guide)
        return {"knowledge": knowledge, "guide": guide}

    @staticmethod
    def _save(backend: BackendProtocol, path: str, content: str):
        content = _prepare_text(content)
        result = backend.write(path, content)
        if result.error:
            raise RuntimeError(f"Artifact save failed: {result.error}")
        loaded = backend.download_files([path])[0]
        if loaded.error or loaded.content != content.encode("utf-8"):
            raise RuntimeError("Artifact save could not be verified; not ready for handoff")

    def save_extraction(self, *, summary: str, candidates: str, slug: str, source_reference: str, context_reference: str | None = None) -> ExtractionFiles:
        self.validate_source(source_reference)
        if context_reference is not None:
            self.validate_source(context_reference)
            self.validate_pair(source_reference, context_reference)
        summary = _prepare_text(summary)
        candidates = _prepare_text(candidates)
        name = re.sub(r"[^\w -]", "", slug, flags=re.UNICODE).strip()[:80] or "訪談詳記"
        batch = str(uuid4())
        backend = self._backend("interviews")
        header = f"<!-- q019-extraction-source:v1 -->\n# {name}\n\nSource: {source_reference}\nSource scope: complete input range, not per-sentence attribution.\n\n"
        # Explicit empty value and terminator separate runtime metadata from
        # arbitrary generated prose, even when prose resembles our old header.
        header += f"Context only (not new source): {context_reference or 'none'}\nEnd source metadata.\n\n"
        summary_path = f"/{batch}/summary.md"
        candidates_path = f"/{batch}/candidates.md"
        self._save(backend, summary_path, header + summary)
        self._save(backend, candidates_path, f"Summary: /interviews{summary_path}\n" + header + candidates)
        return ExtractionFiles("/interviews" + summary_path, "/interviews" + candidates_path)

    def save_memory(self, *, knowledge: str, guide: str) -> MemoryVersion:
        """Return a prepared version only. Selecting/publishing current is separate."""
        knowledge = _prepare_text(knowledge)
        guide = _prepare_text(guide, guide=True)
        self._validate_links(knowledge, guide)
        version = MemoryVersion(self.document_id, str(uuid4()))
        backend = self._backend("versions", version.version_id)
        self._save(backend, "/memory/knowledge.md", knowledge)
        self._save(backend, "/memory/guide.md", guide)
        return version

    def source_window(self, summary_path: str) -> dict:
        """Recover runtime-written source metadata, not model-authored attribution.

        Published artifacts remain immutable. A new extraction gets new paths;
        this address still identifies the old snapshot, never a mutable case.
        """
        match = re.fullmatch(r"/interviews/([0-9a-f-]+)/summary\.md", summary_path)
        if not match or str(UUID(match[1])) != match[1]:
            raise ValueError("Expected a runtime interview summary address")
        text = self.read_text(summary_path)
        header = re.match(
            r"\A<!-- q019-extraction-source:v1 -->\n# [^\n]*\n\nSource: ([^\n]+)\n"
            r"Source scope: complete input range, not per-sentence attribution\.\n\n"
            r"Context only \(not new source\): ([^\n]+)\nEnd source metadata\.\n\n", text)
        if header is None:
            raise ValueError("Unambiguous runtime source header unavailable; read the historical artifact, but do not guess its source")
        source, context = header.groups()
        context = None if context == "none" else context
        self.validate_source(source)
        if context is not None:
            self.validate_source(context)
            self.validate_pair(source, context)
        return {"source_reference": source, "context_reference": context}

    def extraction_window(self, summary_path: str) -> dict:
        """Re-extraction requires the paired candidates; pure source reads do not."""
        window = self.source_window(summary_path)
        self.read_text(summary_path.removesuffix("summary.md") + "candidates.md")
        return window

    def _validate_links(self, knowledge: str, guide: str):
        interviews = self._backend("interviews")
        for reference in sorted(controlled_references(knowledge) | controlled_references(guide)):
            try:
                if reference.startswith('conversation:'):
                    self.validate_source(reference)
                    self.source.read(reference)
                else:
                    if not re.fullmatch(r'/interviews/[0-9a-f-]{36}/(?:summary|candidates)\.md', reference):
                        raise ValueError('Expected an existing runtime interview artifact address')
                    if interviews.read(reference.removeprefix('/interviews'), limit=1).error:
                        raise ValueError('Artifact is unavailable in this document')
            except ValueError as error:
                # No semantic claims or new required evidence. This is the same
                # check for B2 validation, C validation, save and publication.
                raise ValueError(f'Invalid Memory reference {reference[:160]!r}: {error}. '
                                 'Read the relevant record and copy its existing address; do not invent or re-encode one.') from error

    def verify_version(self, version: MemoryVersion) -> str:
        """Verify prepared bytes before publication; no writes or semantic claims."""
        paths = ["/memory/knowledge.md", "/memory/guide.md"]
        downloaded = self._view(version).download_files(paths)
        if len(downloaded) != 2 or any(r.error or r.content is None for r in downloaded):
            raise ValueError("Memory content unavailable; version cannot be published")
        texts = [r.content.decode("utf-8") for r in downloaded]
        for index, text in enumerate(texts):
            if _prepare_text(text, guide=index == 1) != text:
                raise ValueError("Memory content is not normalized; prepare a new version")
        self._validate_links(*texts)
        return hashlib.sha256(json.dumps(dict(zip(paths, texts)), ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def _view(self, version: MemoryVersion):
        if version.document_id != self.document_id:
            raise ValueError("Memory version belongs to another document")
        return CompositeBackend(default=self._backend("versions", version.version_id), routes={"/interviews/": self._backend("interviews")})

    def reader(self, version: MemoryVersion | None) -> ReadOnlyFiles:
        # No head means no published knowledge. No placeholder files are saved.
        view = self._view(version) if version else CompositeBackend(
            default=self._backend("unpublished"), routes={"/interviews/": self.interview_backend()})
        return ReadOnlyFiles(view, self.document_id)

    def guide(self, version: MemoryVersion) -> str:
        result = self._view(version).download_files(["/memory/guide.md"])[0]
        if result.error or result.content is None:
            raise ValueError("Memory guide is unavailable; this version is not ready")
        guide = result.content.decode("utf-8")
        return _prepare_text(guide, guide=True)
