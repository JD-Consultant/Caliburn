"""Source-owner windows on the existing native conversation, without writes.

One saved Human and its preceding public AI context are selected by the App.
The source has a separate ItsDangerous purpose; it is not a JD or chat cursor.
Checkpoint decoding and public text projection remain with their existing owners.
"""
from dataclasses import dataclass
import hashlib
import json
import re
from threading import Lock
from typing import Literal
from uuid import UUID

from itsdangerous import URLSafeSerializer
from langchain_core.messages import AIMessage, BaseMessageChunk, HumanMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ai_checkpoints import AiCheckpointError, AiRunCheckpoints
from .chat_history import public_chat_text
from .domain import Source
from .reads import ReadError


MAX_REFERENCE_BYTES = 4096
_SALT = "caliburn.jd.conversation-source.v1"
_TOKEN = re.compile(r"[A-Za-z0-9_.-]+\Z")
_INSTRUCTION = (
    "此來源只涵蓋本輪已保存的員工原話及列明的前一則AI公開上下文。"
    "正文仍在對應的原user/assistant訊息中，不在此通知。"
    "AI文字不是已確認的員工事實；來源可讀不表示已支持整項JD內容。"
    "僅在核對完整目標內容後使用source_ref，不猜來源或補造未知；此引用不是全部歷史。"
)


class ConversationSourceError(ValueError):
    def __init__(self, code: str):
        self.code = code if code in {"invalid_ref", "source_not_available"} else "source_not_available"
        super().__init__(self.code)


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError()
    return value


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class _SourcePosition(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, revalidate_instances="always")
    format_version: int = Field(ge=1, le=1)
    purpose: Literal["source"]
    dataset_id: str
    document_id: str
    run_id: str
    root_checkpoint_id: str = Field(min_length=1, max_length=256)
    source_namespace: str = Field(max_length=256)
    source_checkpoint_id: str = Field(min_length=1, max_length=256)
    first: str = Field(min_length=1, max_length=512)
    last: str = Field(min_length=1, max_length=512)

    @field_validator("dataset_id", "document_id", "run_id")
    @classmethod
    def scope(cls, value):
        return _uuid(value)

    @model_validator(mode="after")
    def position(self):
        values = (self.root_checkpoint_id, self.source_namespace, self.source_checkpoint_id, self.first, self.last)
        if (any("\0" in value for value in values)
                or any(not value.strip() for value in (self.root_checkpoint_id, self.source_checkpoint_id, self.first, self.last))
                or self.last != self.run_id
                or (self.source_namespace != "" and not self.source_namespace.startswith("consultant:"))
                or (self.source_namespace == "" and self.source_checkpoint_id != self.root_checkpoint_id)):
            raise ValueError()
        return self

    def root_config(self):
        return {"configurable": {"thread_id": self.document_id, "checkpoint_ns": "",
                                  "checkpoint_id": self.root_checkpoint_id}}

    def source_config(self):
        return {"configurable": {"thread_id": self.document_id, "checkpoint_ns": self.source_namespace,
                                  "checkpoint_id": self.source_checkpoint_id}}


@dataclass(frozen=True, slots=True, repr=False)
class SourceMessage:
    message_id: str
    role: Literal["user", "assistant"]
    text: str


@dataclass(frozen=True, slots=True, repr=False)
class SourceExcerpt:
    source_ref: str
    messages: tuple[SourceMessage, ...]


class ConversationSourceCodec:
    __slots__ = ("_dataset_id", "_serializer")

    def __init__(self, secret_key: bytes, dataset_id: str):
        try:
            _uuid(dataset_id)
            if type(secret_key) is not bytes or len(secret_key) < 32:
                raise ValueError()
            self._dataset_id = dataset_id
            self._serializer = URLSafeSerializer(secret_key, salt=_SALT,
                signer_kwargs={"digest_method": hashlib.sha256},
                serializer_kwargs={"sort_keys": True, "ensure_ascii": False, "allow_nan": False})
        except Exception:
            raise ConversationSourceError("source_not_available") from None

    @property
    def dataset_id(self):
        return self._dataset_id

    @staticmethod
    def _token(value):
        if (type(value) is not str or not 0 < len(value) <= MAX_REFERENCE_BYTES
                or not _TOKEN.fullmatch(value)):
            raise ValueError()

    @staticmethod
    def _bounded(position):
        payload = position.model_dump(mode="json")
        if (4 * len(_json(payload).encode("utf-8")) + 2) // 3 + 44 > MAX_REFERENCE_BYTES:
            raise ValueError()
        return payload

    def _issue(self, position: _SourcePosition) -> str:
        try:
            position = _SourcePosition.model_validate(position, strict=True)
            if position.dataset_id != self.dataset_id:
                raise ValueError()
            token = self._serializer.dumps(self._bounded(position))
            self._token(token)
            return token
        except Exception:
            raise ConversationSourceError("source_not_available") from None

    def _resolve(self, source_ref, document_id) -> _SourcePosition:
        try:
            _uuid(document_id)
            self._token(source_ref)
            position = _SourcePosition.model_validate(self._serializer.loads(source_ref), strict=True)
            self._bounded(position)
            if position.dataset_id != self.dataset_id or position.document_id != document_id:
                raise ValueError()
            return position
        except Exception:
            raise ConversationSourceError("invalid_ref") from None


def _selected(messages, run_id):
    """Never reach past another Human to claim an earlier AI as this answer's context."""
    found = [index for index, message in enumerate(messages) if message.id == run_id]
    if len(found) != 1:
        raise ConversationSourceError("invalid_ref")
    index = found[0]
    human = messages[index]
    if (not isinstance(human, HumanMessage) or isinstance(human, BaseMessageChunk)
            or any(isinstance(message, HumanMessage) for message in messages[index + 1:])):
        raise ConversationSourceError("invalid_ref")
    result = [SourceMessage(human.id, "user", public_chat_text(human))]
    for message in reversed(messages[:index]):
        if isinstance(message, HumanMessage):
            break
        if isinstance(message, AIMessage):
            text = public_chat_text(message)
            if text:
                result.insert(0, SourceMessage(message.id, "assistant", text))
                break
    return tuple(result)


def _visible_in_request(messages, expected):
    try:
        if not isinstance(messages, (list, tuple)):
            raise ValueError()
        positions = []
        for wanted in expected:
            matches = [i for i, message in enumerate(messages) if getattr(message, "id", None) == wanted.message_id]
            if len(matches) != 1:
                raise ValueError()
            index = matches[0]
            actual = messages[index]
            kind = HumanMessage if wanted.role == "user" else AIMessage
            if (not isinstance(actual, kind) or isinstance(actual, BaseMessageChunk)
                    or public_chat_text(actual) != wanted.text):
                raise ValueError()
            positions.append(index)
        if positions != sorted(positions) or any(isinstance(m, HumanMessage) for m in messages[positions[-1] + 1:]):
            raise ValueError()
        # The declared source contains only these public messages. Do not hide
        # another answer or public AI text inserted between the exact endpoints.
        visible = []
        for message in messages[positions[0]:positions[-1] + 1]:
            text = public_chat_text(message)
            if text is not None:
                visible.append(SourceMessage(message.id, "user" if isinstance(message, HumanMessage) else "assistant", text))
        if tuple(visible) != expected:
            raise ValueError()
    except Exception:
        raise ConversationSourceError("invalid_ref") from None


class ConversationSourceService:
    def __init__(self, checkpoints: AiRunCheckpoints, codec: ConversationSourceCodec):
        if not isinstance(checkpoints, AiRunCheckpoints) or not isinstance(codec, ConversationSourceCodec):
            raise ConversationSourceError("source_not_available")
        self._checkpoints, self._codec = checkpoints, codec

    @property
    def dataset_id(self):
        return self._codec.dataset_id

    @staticmethod
    def _scope(document_id, run_id):
        try:
            _uuid(document_id); _uuid(run_id)
        except Exception:
            raise ConversationSourceError("invalid_ref") from None

    def capture(self, document_id, run_id) -> SourceExcerpt:
        self._scope(document_id, run_id)
        try:
            observed = self._checkpoints.discover(document_id, self.dataset_id)
            if observed is None:
                raise ConversationSourceError("source_not_available")
            if observed.record.run_id != run_id:
                raise ConversationSourceError("invalid_ref")
            messages = _selected(observed.messages, run_id)
            root, source = observed.root_config["configurable"], observed.source_config["configurable"]
            position = _SourcePosition(format_version=1, purpose="source", dataset_id=self.dataset_id,
                document_id=document_id, run_id=run_id, root_checkpoint_id=root["checkpoint_id"],
                source_namespace=source["checkpoint_ns"], source_checkpoint_id=source["checkpoint_id"],
                first=messages[0].message_id, last=run_id)
            return SourceExcerpt(self._codec._issue(position), messages)
        except ConversationSourceError:
            raise
        except Exception:
            raise ConversationSourceError("source_not_available") from None

    def read(self, source_ref, document_id) -> SourceExcerpt:
        position = self._codec._resolve(source_ref, document_id)
        try:
            observed = self._checkpoints.observe_at(document_id, position.run_id, self.dataset_id,
                position.root_config(), source_config=position.source_config())
            messages = _selected(observed.messages, position.run_id)
            if messages[0].message_id != position.first or messages[-1].message_id != position.last:
                raise ConversationSourceError("invalid_ref")
            return SourceExcerpt(source_ref, messages)
        except ConversationSourceError:
            raise
        except AiCheckpointError as error:
            # A valid issued position that no longer has its native run is an
            # unavailable source. It must not fall back to another checkpoint.
            code = "invalid_ref" if error.code == "invalid_input" else "source_not_available"
            raise ConversationSourceError(code) from None
        except Exception:
            raise ConversationSourceError("source_not_available") from None

    def resolve(self, source_ref, document_id) -> Source:
        try:
            self.read(source_ref, document_id)
            return Source(document_id, readable=True)
        except ConversationSourceError as error:
            raise ReadError(error.code) from None

    def for_turn(self, document_id, run_id):
        self._scope(document_id, run_id)
        fixed, lock = None, Lock()

        def notice(messages):
            nonlocal fixed
            # This lock is local to one turn's first capture, not a document or
            # global writer gate. The caller owns lifetime/foreground admission.
            with lock:
                if fixed is None:
                    fixed = self.capture(document_id, run_id)
                excerpt = fixed
            _visible_in_request(messages, excerpt.messages)
            return {"type": "conversation_source_notice", "source_ref": excerpt.source_ref,
                "messages": [{"message_id": item.message_id, "role": item.role} for item in excerpt.messages],
                "instruction": _INSTRUCTION}

        return notice
