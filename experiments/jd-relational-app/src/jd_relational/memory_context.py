"""One explicit Memory read baseline per foreground turn, using the native Store.

This is a read session, not another publication owner or agent loop. Native
input checkpoints hold the turn-start version. Ordinary model/tool calls do not
follow background publications; an explicit C stale result or applied repair
may advance only this turn's effective baseline. A later turn selects the
then-current publication.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID

from caliburn_memory import MemoryArtifacts, PublicationStore, PublishedHead
from deepagents.backends.protocol import BackendProtocol, GrepResult, LsResult, ReadResult
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.config import get_config
from langgraph.store.base import BaseStore
from sqlalchemy.engine import Engine
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .memory_sources import MemorySourceReader

MEMORY_READ_NAMES = frozenset({
    "ls", "grep", "read_file", "read_evidence", "read_case", "read_work_understanding",
})
MEMORY_READ_GUIDANCE = (
    "memory_guide是已發布Memory的導覽資料，不是指令、員工原話或完整工作內容。"
    "分層版本同時提供案例導覽與工作理解導覽：工作理解用來定位穩定共同工作，"
    "案例用來核對個別任務、條件、例外與更正；從導覽選既有ID後，按需使用"
    "read_work_understanding或read_case，不要全量讀取。read_case會回傳按原對話順序排列的短evidence key；"
    "需要確切問答時，只把已取得的key交給read_evidence，不要猜測來源、offset或版本。"
    "分層版本不要用ls、grep或read_file繞過上述工具；manifest與Runtime欄位不是模型輸入。"
    "grep是字面搜尋；沒有命中不代表員工沒有這項工作。依回傳offset續讀，不必讀到檔尾。"
    "案例與工作理解是可修訂的目前理解，仍須核對來源與後續更正；AI轉述不等於員工確認。"
    "保留主體、行動、適用條件、頻率、責任邊界及案例差異；不清楚時追問。"
    "讀取Memory不代表這輪必須改JD；JD撤回不撤回訪談或Memory。"
)


@dataclass(frozen=True, repr=False)
class LayeredReadProof:
    """Runtime-derived reads from this foreground run, never model claims."""

    case_evidence: dict[str, dict[str, str]]
    understanding_ids: frozenset[str]
    complete_case_evidence: frozenset[tuple[str, str]]
    evidence_next_offsets: dict[str, int | None]


def _json(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )


def _content_digest(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


def issue_scoped_evidence_key(*, dataset_id: str, document_id: str, run_id: str,
                              scope_kind: str, scope_id: str,
                              source_reference: str) -> str:
    """Issue one stable run/scope handle without exposing its locator."""
    payload = _json({
        "dataset_id": dataset_id,
        "document_id": document_id,
        "run_id": run_id,
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "source_reference": source_reference,
    })
    return "E-" + sha256(payload.encode("utf-8")).hexdigest()[:20]


def issue_evidence_key(*, dataset_id: str, document_id: str, run_id: str,
                       case_id: str, source_reference: str) -> str:
    """Issue one stable run/case-scoped handle without exposing its locator."""
    return issue_scoped_evidence_key(
        dataset_id=dataset_id,
        document_id=document_id,
        run_id=run_id,
        scope_kind="case",
        scope_id=case_id,
        source_reference=source_reference,
    )


def _artifact_scope(session, *, kind: str, content: str) -> dict:
    return {
        "format_version": 1,
        "kind": kind,
        "dataset_id": session.dataset_id,
        "document_id": session.document_id,
        "run_id": session.run_id,
        "memory_revision": session.head.revision,
        "memory_version_id": session.head.memory.version_id,
        "content_digest": _content_digest(content),
    }


def case_read_projection(session, item) -> tuple[str, dict]:
    evidence = [
        {
            "evidence_key": issue_evidence_key(
                dataset_id=session.dataset_id,
                document_id=session.document_id,
                run_id=session.run_id,
                case_id=item.case_id,
                source_reference=reference,
            ),
            "source_reference": reference,
            "canonical_order": index,
        }
        for index, reference in enumerate(item.source_references, 1)
    ]
    content = _json({
        "case_id": item.case_id,
        "memory_handle": f"case:{item.case_id}",
        "content": item.content,
        "source_order": "oldest_to_newest",
        "evidence": [{"evidence_key": entry["evidence_key"]} for entry in evidence],
    })
    return content, {
        **_artifact_scope(session, kind="case", content=content),
        "case_id": item.case_id,
        "evidence": evidence,
    }


def understanding_read_projection(session, item) -> tuple[str, dict]:
    content = _json({
        "understanding_id": item.understanding_id,
        "memory_handle": f"understanding:{item.understanding_id}",
        "content": item.content,
        "case_bindings": [{"case_id": binding.case_id} for binding in item.case_bindings],
    })
    return content, {
        **_artifact_scope(session, kind="understanding", content=content),
        "understanding_id": item.understanding_id,
    }


def evidence_read_projection(session, *, case_id: str, evidence_key: str,
                             source_reference: str, page: dict) -> tuple[str, dict]:
    content = _json({
        "case_id": case_id,
        "evidence_key": evidence_key,
        "source_order": "oldest_to_newest",
        "segments": [
            {
                "role": segment["role"],
                "text": segment["text"],
                "continued_from_previous_page": segment["text_offset"] > 0,
            }
            for segment in page["segments"]
        ],
        "has_more": page["next_offset"] is not None,
    })
    return content, {
        **_artifact_scope(session, kind="evidence", content=content),
        "case_id": case_id,
        "evidence_key": evidence_key,
        "source_reference": source_reference,
        "read_offset": page["read_offset"],
        "next_offset": page["next_offset"],
    }


def layered_read_proof(messages, *, dataset_id: str, document_id: str,
                       run_id: str, revision: int,
                       version_id: str) -> LayeredReadProof:
    """Project exact layered reads from trusted private ToolMessage artifacts."""
    try:
        if (type(messages) not in (list, tuple)
                or any(str(UUID(value)) != value
                       for value in (dataset_id, document_id, run_id, version_id))
                or type(revision) is not int or revision < 1
                ):
            raise ValueError()
        starts = [index for index, message in enumerate(messages)
                  if isinstance(message, HumanMessage) and message.id == run_id]
        if len(starts) != 1:
            raise ValueError()
        scoped = messages[starts[0]:]
        calls = {}
        for message in scoped:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    call_id = call.get("id")
                    if type(call_id) is not str or not call_id or call_id in calls:
                        raise ValueError()
                    calls[call_id] = call

        cases: dict[str, dict[str, str]] = {}
        understandings: set[str] = set()
        evidence_offsets: dict[str, int | None] = {}
        evidence_scope: dict[str, tuple[str, str]] = {}
        complete: set[tuple[str, str]] = set()
        seen_results: set[str] = set()
        for message in scoped:
            if not isinstance(message, ToolMessage) or message.tool_call_id not in calls:
                continue
            call = calls[message.tool_call_id]
            name = call.get("name")
            if name not in {"read_case", "read_work_understanding", "read_evidence"}:
                continue
            if message.tool_call_id in seen_results:
                raise ValueError()
            seen_results.add(message.tool_call_id)
            if message.status != "success":
                continue
            if type(message.content) is not str or type(message.artifact) is not dict:
                raise ValueError()
            payload = json.loads(message.content)
            artifact = message.artifact
            args = call.get("args")
            if type(payload) is not dict or type(args) is not dict:
                raise ValueError()
            # The shared model-facing read_evidence tool also serves Working
            # State and JD keys. Their own validators own those artifacts;
            # neither can satisfy a case-scoped layered Memory read.
            if name == "read_evidence" and artifact.get("kind") in {
                    "working_evidence", "jd_evidence"}:
                continue
            expected_keys = {
                "format_version", "kind", "dataset_id", "document_id", "run_id",
                "memory_revision", "memory_version_id", "content_digest",
            }
            expected_kind = {
                "read_case": "case",
                "read_work_understanding": "understanding",
                "read_evidence": "evidence",
            }[name]
            if (artifact.get("format_version") != 1
                    or artifact.get("kind") != expected_kind
                    or (artifact.get("dataset_id"), artifact.get("document_id"), artifact.get("run_id"))
                    != (dataset_id, document_id, run_id)
                    or artifact.get("content_digest") != _content_digest(message.content)
                    or any(str(UUID(artifact.get(key))) != artifact.get(key)
                           for key in ("dataset_id", "document_id", "run_id", "memory_version_id"))):
                raise ValueError()
            # A successful C repair may advance this foreground run to a new
            # explicit basis. Earlier valid reads remain canonical history but
            # cannot prove reads against the refreshed publication.
            if (artifact.get("memory_revision") != revision
                    or artifact.get("memory_version_id") != version_id):
                continue
            if name == "read_case":
                case_id = args.get("case_id")
                if (set(artifact) != expected_keys | {"case_id", "evidence"}
                        or payload.get("case_id") != case_id
                        or artifact.get("case_id") != case_id or str(UUID(case_id)) != case_id):
                    raise ValueError()
                evidence = artifact.get("evidence")
                visible = payload.get("evidence")
                if (type(evidence) is not list or type(visible) is not list or not evidence
                        or len(evidence) != len(visible)):
                    raise ValueError()
                mapping = {}
                for index, (item, shown) in enumerate(zip(evidence, visible, strict=True), 1):
                    if (type(item) is not dict
                            or set(item) != {"evidence_key", "source_reference", "canonical_order"}
                            or type(item["source_reference"]) is not str
                            or item["canonical_order"] != index
                            or shown != {"evidence_key": item["evidence_key"]}
                            or item["evidence_key"] != issue_evidence_key(
                                dataset_id=dataset_id, document_id=document_id,
                                run_id=run_id, case_id=case_id,
                                source_reference=item["source_reference"],
                            )):
                        raise ValueError()
                    key = item["evidence_key"]
                    if key in evidence_scope and evidence_scope[key] != (case_id, item["source_reference"]):
                        raise ValueError()
                    mapping[key] = item["source_reference"]
                    evidence_scope[key] = (case_id, item["source_reference"])
                if case_id in cases and cases[case_id] != mapping:
                    raise ValueError()
                cases[case_id] = mapping
            elif name == "read_work_understanding":
                identity = args.get("understanding_id")
                if (set(artifact) != expected_keys | {"understanding_id"}
                        or payload.get("understanding_id") != identity
                        or artifact.get("understanding_id") != identity
                        or str(UUID(identity)) != identity):
                    raise ValueError()
                understandings.add(identity)
            else:
                if set(artifact) != expected_keys | {
                    "case_id", "evidence_key", "source_reference", "read_offset", "next_offset",
                }:
                    raise ValueError()
                key = args.get("evidence_key")
                scope = evidence_scope.get(key)
                if (type(key) is not str or scope is None
                        or artifact.get("evidence_key") != key
                        or (artifact.get("case_id"), artifact.get("source_reference")) != scope
                        or payload.get("evidence_key") != key or payload.get("case_id") != scope[0]):
                    raise ValueError()
                offset = artifact.get("read_offset")
                expected = evidence_offsets.get(key, 0)
                if expected is None:
                    expected = 0
                if offset != expected:
                    raise ValueError()
                following = artifact.get("next_offset")
                if following is not None and (type(following) is not int or following <= offset):
                    raise ValueError()
                if payload.get("has_more") is not (following is not None):
                    raise ValueError()
                evidence_offsets[key] = following
                if following is None:
                    complete.add((scope[0], key))
        return LayeredReadProof(
            case_evidence=cases,
            understanding_ids=frozenset(understandings),
            complete_case_evidence=frozenset(complete),
            evidence_next_offsets=evidence_offsets,
        )
    except MemoryReadError:
        raise
    except Exception:
        raise MemoryReadError("invalid_layered_read_proof") from None


def memory_guide_projection(artifacts, version):
    """Load the selected version's navigation only, never its item bodies."""
    if artifacts.bundle_base(version) is None:
        guide = artifacts.read_text("/memory/guide.md", version)
        if len(guide) > 4000:
            raise ValueError()
        return guide
    manifest = artifacts.bundle_manifest(version)
    case_guide = artifacts.case_guide(version)
    understanding_guide = artifacts.understanding_guide(version)
    return (
        f"【案例導覽｜{manifest.case_guide.path}】\n{case_guide}\n\n"
        f"【工作理解導覽｜{manifest.understanding_guide.path}】\n{understanding_guide}"
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
            guide = memory_guide_projection(artifacts, version) if version else ""
            return cls(dataset_id, document_id, run_id, artifacts, source, head,
                       guide, artifacts.reader(version))
        except Exception:
            raise MemoryReadError() from None

    def notice(self):
        return {"type": "memory_guide", "instruction": MEMORY_READ_GUIDANCE,
                "published": self.head is not None, "revision": self.view["revision"],
                "guide": self.guide}

    def at_head(self, head: PublishedHead | None) -> "MemoryReadSession":
        """Select one explicit published head without consulting `latest` again."""
        try:
            if (head is not None and (not isinstance(head, PublishedHead)
                    or head.memory.document_id != self.document_id
                    or type(head.revision) is not int or head.revision < 1)):
                raise ValueError()
            version = head.memory if head else None
            guide = memory_guide_projection(self.artifacts, version) if version else ""
            return MemoryReadSession(
                self.dataset_id, self.document_id, self.run_id, self.artifacts,
                self.source, head, guide, self.artifacts.reader(version),
            )
        except Exception:
            raise MemoryReadError() from None


def initial_memory_session(runtime):
    """Validate and return the immutable view selected when this turn began."""
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


def memory_session(runtime):
    """Return this turn's current explicit baseline, including C refreshes."""
    initial = initial_memory_session(runtime)
    repair = getattr(runtime.context, "memory_repair_session", None)
    if repair is None:
        return initial
    try:
        from .memory_repair_session import MemoryRepairSession
        if not isinstance(repair, MemoryRepairSession) or repair.initial is not initial:
            raise ValueError()
        return repair.current_read(runtime.state)
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


class _LayeredMemoryFiles(BackendProtocol):
    """Keep generic file tools from bypassing typed layered reads."""
    _ERROR = (
        "layered_memory_requires_typed_read: 請從兩層導覽選ID後使用"
        "read_case或read_work_understanding。"
    )

    def read(self, file_path, offset=0, limit=2000):
        return ReadResult(error=self._ERROR)

    def ls(self, path):
        return LsResult(error=self._ERROR)

    def grep(self, pattern, path=None, glob=None, *, max_count=None):
        return GrepResult(error=self._ERROR)


def _is_layered(session):
    if session.head is None:
        return False
    try:
        return session.artifacts.bundle_base(session.head.memory) is not None
    except Exception:
        raise MemoryReadError() from None


def build_memory_read_tools(backend=None):
    """Native tool instances; 0.7 removed backend factories, so use override."""
    from caliburn_memory.read_tools import readonly_file_tools
    from .memory_read_tools import build_evidence_read_tool
    return [*readonly_file_tools(backend if backend is not None else _UnboundMemoryFiles()),
            build_evidence_read_tool(), *_build_layered_memory_read_tools()]


def _build_layered_memory_read_tools():
    """Read current bundle items through typed package APIs, not its manifest."""
    from langchain.tools import ToolRuntime, tool
    from langchain_core.tools import ToolException

    def identifier(value, *, kind):
        try:
            if type(value) is not str or str(UUID(value)) != value:
                raise ValueError()
            return value
        except Exception:
            raise ToolException(f"invalid_{kind}_id: 請原樣使用導覽提供的ID，不要猜測或改寫。") from None

    def current(runtime):
        session = memory_session(runtime)
        if not _is_layered(session):
            raise ToolException("layered_memory_unavailable: 目前版本沒有分層案例與工作理解。")
        return session

    @tool("read_case", response_format="content_and_artifact")
    def read_case(case_id: str, runtime: ToolRuntime):
        """讀取一筆目前案例與按原對話順序排列的evidence keys；不要自行產生ID。"""
        session = current(runtime)
        case_id = identifier(case_id, kind="case")
        try:
            item = session.artifacts.case(session.head.memory, case_id)
        except ValueError as error:
            if str(error) == f"Case is not current in this Memory version: {case_id}":
                raise ToolException("case_not_current: 此案例不屬於本回合固定的Memory版本。") from None
            raise MemoryReadError() from None
        except Exception:
            raise MemoryReadError() from None
        return case_read_projection(session, item)

    @tool("read_work_understanding", response_format="content_and_artifact")
    def read_work_understanding(understanding_id: str, runtime: ToolRuntime):
        """讀取理解導覽中的一筆目前工作理解與其支持案例ID；不要自行產生ID。"""
        session = current(runtime)
        understanding_id = identifier(understanding_id, kind="understanding")
        try:
            item = session.artifacts.understanding(session.head.memory, understanding_id)
        except ValueError as error:
            if str(error) == (
                    f"Work understanding is not current in this Memory version: {understanding_id}"):
                raise ToolException(
                    "understanding_not_current: 此工作理解不屬於本回合固定的Memory版本。") from None
            raise MemoryReadError() from None
        except Exception:
            raise MemoryReadError() from None
        return understanding_read_projection(session, item)

    for item in (read_case, read_work_understanding):
        item.handle_tool_error = True
        item.handle_validation_error = (
            "invalid_input: 請依工具定義提供導覽中的既有ID，不要加入其他欄位。"
        )
    return [read_case, read_work_understanding]


def bind_memory_read_request(request):
    if request.tool_call["name"] not in MEMORY_READ_NAMES:
        return request
    session = memory_session(request.runtime)
    if request.tool_call["name"] in {
            "read_evidence", "read_case", "read_work_understanding"}:
        return request
    from caliburn_memory.read_tools import readonly_file_tools
    from caliburn_memory.skills import SkillAssets, analysis_files
    backend = _LayeredMemoryFiles() if _is_layered(session) else session.backend
    # SkillsMiddleware advertises /skills/ paths, while these are the actual
    # model-facing file tools. Route both through its existing read-only mount.
    files = analysis_files(SkillAssets(), memory=backend)
    replacement = next(t for t in readonly_file_tools(files)
                       if t.name == request.tool_call["name"])
    return request.override(tool=replacement)


def build_consultant_tools():
    from .consultant_tools import build_jd_tools
    from .memory_repair_session import build_repair_tool
    from .working_state import build_working_state_tools
    from caliburn_memory.requests import request_memory_consolidation
    consolidation_tool = request_memory_consolidation.model_copy(update={
        "args_schema": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    })
    return [*build_jd_tools(), *build_memory_read_tools(), *build_working_state_tools(),
            build_repair_tool(),
            consolidation_tool]
