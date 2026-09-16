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

from caliburn_memory.bundle import (
    BUNDLE_SCHEMA_VERSION, CASE_GUIDE_PATH, MANIFEST_PATH, UNDERSTANDING_GUIDE_PATH,
    ArtifactPointer, CaseArtifact, CaseManifestEntry, CaseRead, MemoryBundleManifest,
    Supersession, UnderstandingCaseBinding, UnderstandingManifestEntry,
    WorkUnderstandingArtifact, WorkUnderstandingRead,
)
from caliburn_memory.references import controlled_references
from caliburn_memory.sources import MAX_EVIDENCE_EXCHANGES, EvidenceExchangePage, SourceReader


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


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_id(value: str, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a runtime identity")
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError(f"{field} must be a runtime UUID") from error
    if str(parsed) != value:
        raise ValueError(f"{field} must use canonical UUID form")
    return value


def _case_path(case_id: str) -> str:
    return f"/memory/cases/items/{case_id}.md"


def _understanding_path(understanding_id: str) -> str:
    return f"/memory/understanding/items/{understanding_id}.md"


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

    def _canonical_source_positions(
        self, through_reference: str, references: set[str],
    ) -> dict[str, int]:
        """Prove one lineage and return source-owner order for every reference."""
        if self.source is None:
            raise ValueError("Canonical source reader is not configured")
        if type(through_reference) is not str or not through_reference:
            raise ValueError("Expected a Runtime-fixed evidence history reference")
        positions: dict[str, int] = {}
        offset = 0
        ordinal = 0
        while len(positions) < len(references):
            try:
                page = self.source.history_exchanges(
                    through_reference, offset=offset, limit=MAX_EVIDENCE_EXCHANGES,
                )
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError(
                    "Canonical evidence history is unavailable for this lineage",
                ) from error
            if not isinstance(page, EvidenceExchangePage) or page.order != "oldest_to_newest":
                raise ValueError("Canonical evidence history did not provide owner order")
            for exchange in page.exchanges:
                reference = exchange.source_reference
                if reference in references:
                    if reference in positions:
                        raise ValueError("Canonical evidence history returned a duplicate source")
                    positions[reference] = ordinal
                ordinal += 1
            if len(positions) == len(references):
                break
            if page.next_offset is None:
                raise ValueError(
                    "Canonical evidence history cannot prove the requested source lineage",
                )
            if page.next_offset <= offset:
                raise ValueError("Canonical evidence history paging did not advance")
            offset = page.next_offset
        return positions

    def save_bundle(self, *, base_publication_revision: int,
                    evidence_through_reference: str, case_guide: str,
                    cases: tuple[CaseArtifact, ...], understanding_guide: str,
                    understandings: tuple[WorkUnderstandingArtifact, ...],
                    supersessions: tuple[Supersession, ...] = (),
                    base_version: MemoryVersion | None = None) -> MemoryVersion:
        """Prepare one immutable layered bundle; publication remains separate."""
        if type(base_publication_revision) is not int or base_publication_revision < 0:
            raise ValueError("Expected non-negative base publication revision")
        if (base_publication_revision == 0) != (base_version is None):
            raise ValueError("A nonzero base revision requires its exact Memory bundle version")
        base_manifest = self.bundle_manifest(base_version) if base_version is not None else None
        cases, understandings, supersessions = tuple(cases), tuple(understandings), tuple(supersessions)
        case_guide = _prepare_text(case_guide, guide=True)
        understanding_guide = _prepare_text(understanding_guide, guide=True)
        if cases and not case_guide.strip():
            raise ValueError("Case guide is empty while current cases exist")
        if understandings and not understanding_guide.strip():
            raise ValueError("Understanding guide is empty while current understandings exist")

        source_sets: dict[str, tuple[str, ...]] = {}
        all_sources: set[str] = set()
        for item in cases:
            case_id = _stable_id(item.case_id, field="case_id")
            if case_id in source_sets:
                raise ValueError(f"Duplicate case_id: {case_id}")
            sources = tuple(item.source_references)
            if not sources:
                raise ValueError(f"Case requires at least one canonical source reference: {case_id}")
            if len(set(sources)) != len(sources):
                raise ValueError(f"Case contains duplicate source references: {case_id}")
            for reference in sources:
                self._validate_controlled_reference(reference)
            source_sets[case_id] = sources
            all_sources.update(sources)
        source_positions = self._canonical_source_positions(
            evidence_through_reference, all_sources,
        ) if all_sources else {}

        case_texts: dict[str, str] = {}
        case_entries: list[CaseManifestEntry] = []
        case_digests: dict[str, str] = {}
        for item in cases:
            case_id = _stable_id(item.case_id, field="case_id")
            if case_id in case_texts:
                raise ValueError(f"Duplicate case_id: {case_id}")
            content = _prepare_text(item.content)
            if not content.strip():
                raise ValueError(f"Case content is empty: {case_id}")
            sources = tuple(sorted(
                source_sets[case_id], key=source_positions.__getitem__,
            ))
            path, digest = _case_path(case_id), _digest(content)
            case_texts[case_id], case_digests[case_id] = content, digest
            case_entries.append(CaseManifestEntry(case_id, path, digest, sources))

        understanding_texts: dict[str, str] = {}
        understanding_entries: list[UnderstandingManifestEntry] = []
        bindings: list[UnderstandingCaseBinding] = []
        for item in understandings:
            understanding_id = _stable_id(item.understanding_id, field="understanding_id")
            if understanding_id in understanding_texts:
                raise ValueError(f"Duplicate understanding_id: {understanding_id}")
            content = _prepare_text(item.content)
            if not content.strip():
                raise ValueError(f"Work understanding content is empty: {understanding_id}")
            supporting = tuple(dict.fromkeys(item.supporting_case_ids))
            if not supporting:
                raise ValueError(f"Work understanding requires at least one supporting case: {understanding_id}")
            for case_id in supporting:
                _stable_id(case_id, field="supporting_case_id")
                if case_id not in case_digests:
                    raise ValueError(f"Unknown supporting case_id: {case_id}")
                bindings.append(UnderstandingCaseBinding(understanding_id, case_id, case_digests[case_id]))
            path, digest = _understanding_path(understanding_id), _digest(content)
            understanding_texts[understanding_id] = content
            understanding_entries.append(UnderstandingManifestEntry(understanding_id, path, digest))

        current_by_kind = {"case": set(case_texts), "understanding": set(understanding_texts)}
        retired_seen: set[tuple[str, str]] = set()
        normalized_supersessions: list[Supersession] = []
        for item in supersessions:
            if item.kind not in current_by_kind:
                raise ValueError("Supersession kind must be case or understanding")
            retired_id = _stable_id(item.retired_id, field="retired_id")
            key = (item.kind, retired_id)
            if key in retired_seen or retired_id in current_by_kind[item.kind]:
                raise ValueError("Superseded identity must be unique and absent from the current set")
            current_ids = tuple(dict.fromkeys(item.current_ids))
            for current_id in current_ids:
                _stable_id(current_id, field="supersession current_id")
                if current_id not in current_by_kind[item.kind]:
                    raise ValueError(f"Supersession points to unknown current {item.kind}: {current_id}")
            retired_seen.add(key)
            normalized_supersessions.append(Supersession(item.kind, retired_id, current_ids))

        prior_by_kind = {
            "case": {item.case_id for item in base_manifest.cases} if base_manifest else set(),
            "understanding": ({item.understanding_id for item in base_manifest.understandings}
                              if base_manifest else set()),
        }
        retired_by_kind = {
            kind: {item.retired_id for item in normalized_supersessions if item.kind == kind}
            for kind in current_by_kind
        }
        for kind in current_by_kind:
            removed = prior_by_kind[kind] - current_by_kind[kind]
            if retired_by_kind[kind] != removed:
                raise ValueError(f"Every removed {kind} identity, and only a removed identity, requires supersession")

        case_entries.sort(key=lambda item: item.case_id)
        understanding_entries.sort(key=lambda item: item.understanding_id)
        bindings.sort(key=lambda item: (item.understanding_id, item.case_id))
        normalized_supersessions.sort(key=lambda item: (item.kind, item.retired_id))
        manifest = MemoryBundleManifest(
            BUNDLE_SCHEMA_VERSION,
            self.document_id,
            base_publication_revision,
            base_version.version_id if base_version is not None else None,
            ArtifactPointer(CASE_GUIDE_PATH, _digest(case_guide)),
            tuple(case_entries),
            ArtifactPointer(UNDERSTANDING_GUIDE_PATH, _digest(understanding_guide)),
            tuple(understanding_entries),
            tuple(bindings),
            tuple(normalized_supersessions),
        )
        texts = {
            CASE_GUIDE_PATH: case_guide,
            UNDERSTANDING_GUIDE_PATH: understanding_guide,
            **{_case_path(key): value for key, value in case_texts.items()},
            **{_understanding_path(key): value for key, value in understanding_texts.items()},
        }
        self._validate_guide_routes(manifest, case_guide, understanding_guide)
        self._validate_bundle_links(texts, set(texts))
        version = MemoryVersion(self.document_id, str(uuid4()))
        backend = self._backend("versions", version.version_id)
        for path in sorted(texts):
            self._save(backend, path, texts[path])
        self._save(backend, MANIFEST_PATH, manifest.to_json())
        self._verify_bundle(version)
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

    def _validate_controlled_reference(self, reference: str, *, memory_paths: set[str] | None = None):
        try:
            if not isinstance(reference, str):
                raise ValueError("Expected an existing runtime reference")
            if reference.startswith("conversation:"):
                self.validate_source(reference)
                self.source.read(reference)
                return
            if reference.startswith("/interviews/"):
                if not re.fullmatch(r"/interviews/[0-9a-f-]{36}/(?:summary|candidates)\.md", reference):
                    raise ValueError("Expected an existing runtime interview artifact address")
                if self._backend("interviews").read(reference.removeprefix("/interviews"), limit=1).error:
                    raise ValueError("Artifact is unavailable in this document")
                return
            if reference.startswith("/memory/") and memory_paths is not None and reference in memory_paths:
                return
            raise ValueError("Expected an existing runtime source or Memory artifact address")
        except ValueError as error:
            # No semantic claims or new required evidence. This is the same
            # check for B1/B2 validation, C validation, save and publication.
            raise ValueError(f"Invalid Memory reference {reference[:160]!r}: {error}. "
                             "Read the relevant record and copy its existing address; do not invent or re-encode one.") from error

    def _validate_links(self, knowledge: str, guide: str):
        legacy_paths = {"/memory/knowledge.md", "/memory/guide.md"}
        for reference in sorted(controlled_references(knowledge) | controlled_references(guide)):
            self._validate_controlled_reference(reference, memory_paths=legacy_paths)

    def _validate_bundle_links(self, texts: dict[str, str], memory_paths: set[str]):
        references: set[str] = set()
        for text in texts.values():
            references.update(controlled_references(text))
        for reference in sorted(references):
            self._validate_controlled_reference(reference, memory_paths=memory_paths)

    @staticmethod
    def _validate_guide_routes(manifest: MemoryBundleManifest, case_guide: str,
                               understanding_guide: str):
        case_routes = controlled_references(case_guide)
        understanding_routes = controlled_references(understanding_guide)
        missing_cases = {item.path for item in manifest.cases} - case_routes
        missing_understandings = {item.path for item in manifest.understandings} - understanding_routes
        if missing_cases:
            raise ValueError("Case guide does not route every current case")
        if missing_understandings:
            raise ValueError("Understanding guide does not route every current work understanding")

    def _load_bundle_manifest(self, version: MemoryVersion) -> MemoryBundleManifest:
        result = self._view(version).download_files([MANIFEST_PATH])[0]
        if result.error or result.content is None:
            raise ValueError("Memory bundle manifest is unavailable")
        manifest = MemoryBundleManifest.from_json(result.content.decode("utf-8"))
        if type(manifest.schema_version) is not int or manifest.schema_version != BUNDLE_SCHEMA_VERSION:
            raise ValueError("Unsupported Memory bundle manifest schema")
        if manifest.document_id != self.document_id:
            raise ValueError("Memory bundle belongs to another document")
        if type(manifest.base_publication_revision) is not int or manifest.base_publication_revision < 0:
            raise ValueError("Invalid Memory bundle base publication revision")
        if manifest.base_publication_revision == 0:
            if manifest.base_memory_version_id is not None:
                raise ValueError("Initial Memory bundle cannot name a base version")
        else:
            _stable_id(manifest.base_memory_version_id, field="base_memory_version_id")
        return manifest

    def _bundle_structure(self, manifest: MemoryBundleManifest) -> dict[str, tuple[str, bool]]:
        case_ids: set[str] = set()
        understanding_ids: set[str] = set()
        expected: dict[str, tuple[str, bool]] = {
            manifest.case_guide.path: (manifest.case_guide.digest, True),
            manifest.understanding_guide.path: (manifest.understanding_guide.digest, True),
        }
        if manifest.case_guide.path != CASE_GUIDE_PATH or manifest.understanding_guide.path != UNDERSTANDING_GUIDE_PATH:
            raise ValueError("Memory bundle guide path does not match the supported schema")
        for item in manifest.cases:
            _stable_id(item.case_id, field="case_id")
            if item.case_id in case_ids or item.path != _case_path(item.case_id):
                raise ValueError("Duplicate case identity or invalid case path")
            case_ids.add(item.case_id)
            expected[item.path] = (item.digest, False)
            if not item.source_references:
                raise ValueError(f"Case requires at least one canonical source reference: {item.case_id}")
        for item in manifest.understandings:
            _stable_id(item.understanding_id, field="understanding_id")
            if item.understanding_id in understanding_ids or item.path != _understanding_path(item.understanding_id):
                raise ValueError("Duplicate understanding identity or invalid understanding path")
            understanding_ids.add(item.understanding_id)
            expected[item.path] = (item.digest, False)
        if len(expected) != 2 + len(case_ids) + len(understanding_ids):
            raise ValueError("Memory bundle paths must be unique")

        seen_bindings: set[tuple[str, str]] = set()
        bound_understandings: set[str] = set()
        case_digest_by_id = {item.case_id: item.digest for item in manifest.cases}
        for binding in manifest.understanding_case_bindings:
            key = (binding.understanding_id, binding.case_id)
            if key in seen_bindings or binding.understanding_id not in understanding_ids:
                raise ValueError("Duplicate binding or unknown work understanding")
            if case_digest_by_id.get(binding.case_id) != binding.case_digest:
                raise ValueError("Work understanding binding does not match the selected case artifact")
            seen_bindings.add(key)
            bound_understandings.add(binding.understanding_id)
        if bound_understandings != understanding_ids:
            raise ValueError("Every current work understanding requires at least one supporting case")

        current_by_kind = {"case": case_ids, "understanding": understanding_ids}
        retired_seen: set[tuple[str, str]] = set()
        for item in manifest.supersessions:
            if item.kind not in current_by_kind:
                raise ValueError("Supersession kind must be case or understanding")
            _stable_id(item.retired_id, field="retired_id")
            key = (item.kind, item.retired_id)
            if key in retired_seen or item.retired_id in current_by_kind[item.kind]:
                raise ValueError("Invalid superseded identity")
            for current_id in item.current_ids:
                _stable_id(current_id, field="supersession current_id")
                if current_id not in current_by_kind[item.kind]:
                    raise ValueError("Supersession points outside the current bundle")
            retired_seen.add(key)
        return expected

    def _read_bundle_artifact(self, version: MemoryVersion, *, path: str, digest: str,
                              guide: bool, allowed_paths: set[str]) -> str:
        loaded = self._view(version).download_files([path])[0]
        if loaded.error or loaded.content is None:
            raise ValueError(f"Memory bundle content unavailable: {path}")
        text = loaded.content.decode("utf-8")
        if _prepare_text(text, guide=guide) != text or _digest(text) != digest:
            raise ValueError(f"Memory bundle artifact changed or is invalid: {path}")
        self._validate_bundle_links({path: text}, allowed_paths)
        return text

    def _verify_bundle(self, version: MemoryVersion) -> tuple[MemoryBundleManifest, dict[str, str]]:
        manifest = self._load_bundle_manifest(version)
        expected = self._bundle_structure(manifest)
        for item in manifest.cases:
            for reference in item.source_references:
                self._validate_controlled_reference(reference)

        paths = sorted(expected)
        downloaded = self._view(version).download_files(paths)
        if len(downloaded) != len(paths) or any(item.error or item.content is None for item in downloaded):
            raise ValueError("Memory bundle content unavailable; version cannot be published")
        texts: dict[str, str] = {}
        for path, loaded in zip(paths, downloaded, strict=True):
            text = loaded.content.decode("utf-8")
            digest, guide = expected[path]
            if _prepare_text(text, guide=guide) != text or _digest(text) != digest:
                raise ValueError(f"Memory bundle artifact changed or is invalid: {path}")
            texts[path] = text
        if manifest.cases and not texts[CASE_GUIDE_PATH].strip():
            raise ValueError("Case guide is empty while current cases exist")
        if manifest.understandings and not texts[UNDERSTANDING_GUIDE_PATH].strip():
            raise ValueError("Understanding guide is empty while current understandings exist")
        self._validate_guide_routes(
            manifest, texts[CASE_GUIDE_PATH], texts[UNDERSTANDING_GUIDE_PATH])
        self._validate_bundle_links(texts, set(texts))
        return manifest, {MANIFEST_PATH: manifest.to_json(), **texts}

    def bundle_manifest(self, version: MemoryVersion) -> MemoryBundleManifest:
        manifest = self._load_bundle_manifest(version)
        self._bundle_structure(manifest)
        return manifest

    def bundle_base(self, version: MemoryVersion) -> tuple[int, str | None] | None:
        """Read only runtime lineage; legacy two-file versions return None."""
        result = self._view(version).download_files([MANIFEST_PATH])[0]
        if result.error == "file_not_found":
            return None
        if result.error or result.content is None:
            raise ValueError("Memory content unavailable; version cannot be published")
        manifest = self._load_bundle_manifest(version)
        return manifest.base_publication_revision, manifest.base_memory_version_id

    def bundle_base_revision(self, version: MemoryVersion) -> int | None:
        base = self.bundle_base(version)
        return base[0] if base is not None else None

    def case(self, version: MemoryVersion, case_id: str) -> CaseRead:
        case_id = _stable_id(case_id, field="case_id")
        manifest = self.bundle_manifest(version)
        entry = next((item for item in manifest.cases if item.case_id == case_id), None)
        if entry is None:
            raise ValueError(f"Case is not current in this Memory version: {case_id}")
        for reference in entry.source_references:
            self._validate_controlled_reference(reference)
        allowed_paths = set(self._bundle_structure(manifest))
        content = self._read_bundle_artifact(
            version, path=entry.path, digest=entry.digest, guide=False, allowed_paths=allowed_paths)
        return CaseRead(case_id, content, entry.source_references)

    def understanding(self, version: MemoryVersion, understanding_id: str) -> WorkUnderstandingRead:
        understanding_id = _stable_id(understanding_id, field="understanding_id")
        manifest = self.bundle_manifest(version)
        entry = next((item for item in manifest.understandings if item.understanding_id == understanding_id), None)
        if entry is None:
            raise ValueError(f"Work understanding is not current in this Memory version: {understanding_id}")
        bindings = tuple(item for item in manifest.understanding_case_bindings
                         if item.understanding_id == understanding_id)
        allowed_paths = set(self._bundle_structure(manifest))
        content = self._read_bundle_artifact(
            version, path=entry.path, digest=entry.digest, guide=False, allowed_paths=allowed_paths)
        return WorkUnderstandingRead(understanding_id, content, bindings)

    def verify_version(self, version: MemoryVersion) -> str:
        """Verify prepared bytes before publication; no writes or semantic claims."""
        manifest_result = self._view(version).download_files([MANIFEST_PATH])[0]
        if not manifest_result.error and manifest_result.content is not None:
            _manifest, texts = self._verify_bundle(version)
            return hashlib.sha256(json.dumps(texts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if manifest_result.error != "file_not_found":
            raise ValueError("Memory content unavailable; version cannot be published")
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

    def case_guide(self, version: MemoryVersion) -> str:
        manifest = self.bundle_manifest(version)
        guide = self._read_bundle_artifact(
            version, path=manifest.case_guide.path, digest=manifest.case_guide.digest,
            guide=True, allowed_paths=set(self._bundle_structure(manifest)))
        if {item.path for item in manifest.cases} - controlled_references(guide):
            raise ValueError("Case guide does not route every current case")
        return guide

    def understanding_guide(self, version: MemoryVersion) -> str:
        manifest = self.bundle_manifest(version)
        guide = self._read_bundle_artifact(
            version, path=manifest.understanding_guide.path, digest=manifest.understanding_guide.digest,
            guide=True, allowed_paths=set(self._bundle_structure(manifest)))
        if {item.path for item in manifest.understandings} - controlled_references(guide):
            raise ValueError("Understanding guide does not route every current work understanding")
        return guide
