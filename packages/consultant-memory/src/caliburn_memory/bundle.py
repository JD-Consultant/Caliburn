"""Runtime-owned structure for one immutable layered Memory bundle.

Agents author case/work-understanding prose and select already-visible semantic
identities.  They never author this manifest, storage paths, digests, document
scope, or publication revisions.
"""

from dataclasses import asdict, dataclass
import json
from typing import Literal


BUNDLE_SCHEMA_VERSION = 1
MANIFEST_PATH = "/memory/manifest.json"
CASE_GUIDE_PATH = "/memory/cases/guide.md"
UNDERSTANDING_GUIDE_PATH = "/memory/understanding/guide.md"


@dataclass(frozen=True)
class CaseArtifact:
    case_id: str
    content: str
    source_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkUnderstandingArtifact:
    understanding_id: str
    content: str
    supporting_case_ids: tuple[str, ...]


@dataclass(frozen=True)
class Supersession:
    kind: Literal["case", "understanding"]
    retired_id: str
    current_ids: tuple[str, ...]


@dataclass(frozen=True)
class ArtifactPointer:
    path: str
    digest: str


@dataclass(frozen=True)
class CaseManifestEntry:
    case_id: str
    path: str
    digest: str
    source_references: tuple[str, ...]


@dataclass(frozen=True)
class UnderstandingManifestEntry:
    understanding_id: str
    path: str
    digest: str


@dataclass(frozen=True)
class UnderstandingCaseBinding:
    understanding_id: str
    case_id: str
    case_digest: str


@dataclass(frozen=True)
class MemoryBundleManifest:
    schema_version: int
    document_id: str
    base_publication_revision: int
    base_memory_version_id: str | None
    case_guide: ArtifactPointer
    cases: tuple[CaseManifestEntry, ...]
    understanding_guide: ArtifactPointer
    understandings: tuple[UnderstandingManifestEntry, ...]
    understanding_case_bindings: tuple[UnderstandingCaseBinding, ...]
    supersessions: tuple[Supersession, ...] = ()

    def to_json(self) -> str:
        """Canonical bytes used for persistence and bundle fingerprinting."""
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "MemoryBundleManifest":
        try:
            raw = json.loads(text)
            if not isinstance(raw, dict):
                raise TypeError("manifest root must be an object")
            expected = {
                "schema_version", "document_id", "base_publication_revision", "base_memory_version_id",
                "case_guide", "cases",
                "understanding_guide", "understandings", "understanding_case_bindings", "supersessions",
            }
            if set(raw) != expected:
                raise ValueError("manifest fields do not match the supported schema")
            return cls(
                schema_version=raw["schema_version"],
                document_id=raw["document_id"],
                base_publication_revision=raw["base_publication_revision"],
                base_memory_version_id=raw["base_memory_version_id"],
                case_guide=ArtifactPointer(**raw["case_guide"]),
                cases=tuple(CaseManifestEntry(
                    case_id=item["case_id"], path=item["path"], digest=item["digest"],
                    source_references=tuple(item["source_references"]),
                ) for item in raw["cases"]),
                understanding_guide=ArtifactPointer(**raw["understanding_guide"]),
                understandings=tuple(UnderstandingManifestEntry(**item) for item in raw["understandings"]),
                understanding_case_bindings=tuple(
                    UnderstandingCaseBinding(**item) for item in raw["understanding_case_bindings"]),
                supersessions=tuple(Supersession(
                    kind=item["kind"], retired_id=item["retired_id"],
                    current_ids=tuple(item["current_ids"]),
                ) for item in raw["supersessions"]),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid Memory bundle manifest: {error}") from error


@dataclass(frozen=True)
class CaseRead:
    case_id: str
    content: str
    source_references: tuple[str, ...]


@dataclass(frozen=True)
class WorkUnderstandingRead:
    understanding_id: str
    content: str
    case_bindings: tuple[UnderstandingCaseBinding, ...]
