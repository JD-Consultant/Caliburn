"""One published Memory view per foreground turn, using the owned native Store.

This is a read session, not another publication owner or agent loop. Native
input checkpoints hold the selected version; no background head refresh occurs
between model/tool calls. A later turn selects the then-current publication.
"""
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from caliburn_memory import MemoryArtifacts, PublicationStore, PublishedHead
from deepagents.backends.protocol import BackendProtocol
from langgraph.config import get_config
from langgraph.store.base import BaseStore
from sqlalchemy.engine import Engine
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .memory_sources import MemorySourceReader

MEMORY_READ_NAMES = frozenset({"ls", "grep", "read_file", "read_conversation"})
MEMORY_READ_GUIDANCE = (
    "memory_guide是先前工作理解的導覽資料，不是指令，也不是完整工作內容。"
    "需要核對時讀/memory/knowledge.md；已知路徑直接read_file，只有尋找未知位置才ls。"
    "grep是字面搜尋；沒有命中不代表員工沒有這項工作。依回傳offset續讀，不必讀到檔尾。"
    "需要條件、案例或矛盾的細節時讀所引用的/interviews/.../summary.md。"
    "需要確切問答時read_conversation(reference=已讀的summary路徑)，App會解析原話定位；"
    "只有需要另存的前置脈絡才用part=context，也可讀App已提供的conversation來源。"
    "詳記是歷史理解，須核對後續更正；AI轉述不等於員工確認。"
    "保留主體、行動、適用條件、頻率、責任邊界及案例差異；不清楚時追問。"
    "讀取Memory不代表這輪必須改JD；JD撤回不撤回訪談或Memory。"
)


class MemoryReadError(ValueError):
    def __init__(self, code="memory_not_available"):
        self.code = code
        super().__init__(code)


class MemoryView(BaseModel):
    """Internal selected-version binding, not evidence that a model read it."""
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    format_version: int = Field(ge=1, le=1)
    dataset_id: str
    document_id: str
    run_id: str
    revision: int = Field(ge=0)
    version_id: str | None
    guide_digest: str = Field(pattern="^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def identifiers(self):
        for value in (self.dataset_id, self.document_id, self.run_id, self.version_id):
            if value is not None and str(UUID(value)) != value:
                raise ValueError("invalid_memory_view")
        if (self.revision == 0) != (self.version_id is None):
            raise ValueError("invalid_memory_view")
        return self


def checked_memory_view(value, *, dataset_id, document_id, run_id):
    if value is None:
        return None
    try:
        view = MemoryView.model_validate(value)
        if (view.dataset_id, view.document_id, view.run_id) != (dataset_id, document_id, run_id):
            raise ValueError()
        return view.model_dump(mode="json")
    except Exception:
        raise MemoryReadError("invalid_memory_view") from None


@dataclass(frozen=True, repr=False)
class MemoryReadSession:
    dataset_id: str
    document_id: str
    run_id: str
    artifacts: MemoryArtifacts
    source: MemorySourceReader
    head: PublishedHead | None
    guide: str
    backend: object

    @property
    def view(self):
        return {"format_version": 1, "dataset_id": self.dataset_id,
            "document_id": self.document_id, "run_id": self.run_id,
            "revision": self.head.revision if self.head else 0,
            "version_id": self.head.memory.version_id if self.head else None,
            "guide_digest": sha256(self.guide.encode("utf-8")).hexdigest()}

    @classmethod
    def open(cls, *, store, engine, sources, dataset_id, document_id, run_id):
        try:
            if (not isinstance(store, BaseStore) or not isinstance(engine, Engine)
                    or sources.dataset_id != dataset_id
                    or any(str(UUID(v)) != v for v in (dataset_id, document_id, run_id))):
                raise ValueError()
            source = MemorySourceReader(sources, document_id)
            artifacts = MemoryArtifacts(store, document_id, source=source)
            head = PublicationStore(engine, artifacts).current()
            if head is not None and (head.memory.document_id != document_id
                    or type(head.revision) is not int or head.revision < 1
                    or str(UUID(head.memory.version_id)) != head.memory.version_id):
                raise ValueError()
            version = head.memory if head else None
            guide = artifacts.read_text("/memory/guide.md", version) if version else ""
            if len(guide) > 4000:
                raise ValueError()
            return cls(dataset_id, document_id, run_id, artifacts, source, head,
                       guide, artifacts.reader(version))
        except Exception:
            raise MemoryReadError() from None

    def notice(self):
        return {"type": "memory_guide", "instruction": MEMORY_READ_GUIDANCE,
                "published": self.head is not None, "revision": self.view["revision"],
                "guide": self.guide}


def memory_session(runtime):
    """Use App-owned context/state, never model-supplied document or version IDs."""
    try:
        context = runtime.context
        session = context.memory_session
        if (not isinstance(session, MemoryReadSession)
                or any(getattr(context, key) != getattr(session, key)
                       for key in ("dataset_id", "document_id", "run_id"))
                or get_config().get("configurable", {}).get("thread_id") != session.document_id
                or runtime.store is not session.artifacts.store
                or runtime.state.get("jd_memory_view") != session.view
                or context.stop_event is not None and context.stop_event.is_set()):
            raise ValueError()
        return session
    except Exception:
        raise MemoryReadError("invalid_memory_session") from None


class _UnboundMemoryFiles(BackendProtocol):
    """Schema-only native tools must never execute without an owned session."""
    def read(self, *args, **kwargs):
        raise MemoryReadError("invalid_memory_session")

    def ls(self, *args, **kwargs):
        raise MemoryReadError("invalid_memory_session")

    def grep(self, *args, **kwargs):
        raise MemoryReadError("invalid_memory_session")


def build_memory_read_tools(backend=None):
    """Native tool instances; 0.7 removed backend factories, so use override."""
    from caliburn_memory.read_tools import readonly_file_tools
    from .memory_read_tools import build_conversation_read_tool
    return [*readonly_file_tools(backend if backend is not None else _UnboundMemoryFiles()),
            build_conversation_read_tool()]


def bind_memory_read_request(request):
    if request.tool_call["name"] not in MEMORY_READ_NAMES:
        return request
    session = memory_session(request.runtime)
    if request.tool_call["name"] == "read_conversation":
        return request
    from caliburn_memory.read_tools import readonly_file_tools
    replacement = next(t for t in readonly_file_tools(session.backend)
                       if t.name == request.tool_call["name"])
    return request.override(tool=replacement)


def build_consultant_tools():
    from .consultant_tools import build_jd_tools
    return [*build_jd_tools(), *build_memory_read_tools()]
