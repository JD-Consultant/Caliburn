"""Public chat projection at one native root/source position, without writes.

LangChain Core's public message.text property extracts strings and text blocks;
the complete native messages remain authoritative in the checkpointer. A named
ItsDangerous salt separates these cursors from JD locators. The trusted host
injects the same durable key/dataset; tokens contain positions, never messages.
"""

import hashlib
import json
import re
from typing import Literal
from uuid import UUID

from itsdangerous import URLSafeSerializer
from langchain_core.messages import AIMessage, BaseMessageChunk, HumanMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ai_checkpoints import AiCheckpointError, AiRunCheckpoints


MAX_PAGE_BYTES = 1024 * 1024
MAX_PAGE_MESSAGES = 50
MAX_CURSOR_BYTES = 4096
_SALT = "caliburn.jd.chat-history.v2"
_TOKEN = re.compile(r"[A-Za-z0-9_.-]+\Z")


class ChatHistoryError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError()
    return value


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class _Position(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, revalidate_instances="always")
    format_version: Literal[2]
    purpose: Literal["anchor", "cursor"]
    dataset_id: str
    document_id: str
    run_id: str
    root_checkpoint_id: str = Field(min_length=1, max_length=256)
    source_namespace: str = Field(max_length=256)
    source_checkpoint_id: str = Field(min_length=1, max_length=256)
    # Anchor uses zero; a cursor is the exclusive end of its next older page.
    offset: int = Field(ge=0, le=2**63 - 1)

    @field_validator("format_version", mode="before")
    @classmethod
    def exact_version(cls, value):
        if type(value) is not int or value != 2:
            raise ValueError()
        return value

    @field_validator("dataset_id", "document_id", "run_id")
    @classmethod
    def scope(cls, value):
        return _uuid(value)

    @model_validator(mode="after")
    def position(self):
        if (any("\0" in value for value in (self.root_checkpoint_id, self.source_namespace, self.source_checkpoint_id))
                or not self.root_checkpoint_id.strip() or not self.source_checkpoint_id.strip()
                or (self.source_namespace != "" and not self.source_namespace.startswith("consultant:"))
                or (self.source_namespace == "" and self.source_checkpoint_id != self.root_checkpoint_id)
                or (self.purpose == "anchor" and self.offset != 0)
                or (self.purpose == "cursor" and self.offset == 0)):
            raise ValueError()
        return self

    def root_config(self):
        return {"configurable": {"thread_id": self.document_id, "checkpoint_ns": "",
                                  "checkpoint_id": self.root_checkpoint_id}}

    def source_config(self):
        return {"configurable": {"thread_id": self.document_id, "checkpoint_ns": self.source_namespace,
                                  "checkpoint_id": self.source_checkpoint_id}}


class ChatHistoryCodec:
    __slots__ = ("_dataset_id", "_serializer")

    def __init__(self, secret_key: bytes, dataset_id: str):
        try:
            _uuid(dataset_id)
            if type(secret_key) is not bytes or len(secret_key) < 32:
                raise ValueError()
        except Exception:
            raise ChatHistoryError("invalid_input") from None
        self._dataset_id = dataset_id
        self._serializer = URLSafeSerializer(secret_key, salt=_SALT,
            signer_kwargs={"digest_method": hashlib.sha256},
            serializer_kwargs={"sort_keys": True, "ensure_ascii": False, "allow_nan": False})

    @property
    def dataset_id(self):
        return self._dataset_id

    @staticmethod
    def _token(value):
        if (type(value) is not str or not 0 < len(value) <= MAX_CURSOR_BYTES
                or not _TOKEN.fullmatch(value)):
            raise ValueError()

    def _issue(self, value: _Position) -> str:
        try:
            position = _Position.model_validate(value, strict=True)
            if position.dataset_id != self.dataset_id:
                raise ValueError()
            payload = position.model_dump(mode="json")
            # Bound uncompressed admission, independent of zlib ratio.
            if (4 * len(_json(payload).encode("utf-8")) + 2) // 3 + 44 > MAX_CURSOR_BYTES:
                raise ValueError()
            token = self._serializer.dumps(payload)
            self._token(token)
            return token
        except Exception:
            raise ChatHistoryError("invalid_checkpoint") from None

    def _resolve(self, token: str, document_id: str) -> _Position:
        try:
            self._token(token)
            position = _Position.model_validate(self._serializer.loads(token), strict=True)
            if (position.purpose != "cursor" or position.dataset_id != self.dataset_id
                    or position.document_id != document_id):
                raise ValueError()
            return position
        except Exception:
            raise ChatHistoryError("invalid_cursor") from None


def public_chat_text(message) -> str | None:
    """Original Human text or native public AI text; never infer hidden content.

    This is a display-only projection. Tool/system messages and AI messages with
    no public text yield None; a partial chunk is never a complete saved reply.
    """
    try:
        if isinstance(message, BaseMessageChunk):
            raise ValueError()
        if isinstance(message, HumanMessage):
            if type(message.content) is not str:
                raise ValueError()
            return message.content
        if isinstance(message, AIMessage):
            # Core 1.6.3 BaseMessage.text, a public property (not deprecated text()).
            value = str(message.text)
            return value if value else None
        return None
    except Exception:
        raise ChatHistoryError("invalid_checkpoint") from None


def _public_messages(observed):
    result, run_id = [], None
    for message in observed.messages:
        if isinstance(message, HumanMessage):
            run_id = _uuid(message.id)
        text = public_chat_text(message)
        if text is None:
            continue
        if (run_id is None or type(message.id) is not str or not message.id
                or "\0" in message.id):
            raise ValueError()
        result.append({"message_id": message.id, "run_id": run_id,
                       "role": "user" if isinstance(message, HumanMessage) else "assistant", "text": text})
    if run_id != observed.record.run_id:
        raise ValueError()
    return result


class ChatHistoryService:
    def __init__(self, checkpoints: AiRunCheckpoints, codec: ChatHistoryCodec):
        if not isinstance(checkpoints, AiRunCheckpoints) or not isinstance(codec, ChatHistoryCodec):
            raise ChatHistoryError("invalid_input")
        self._checkpoints, self._codec = checkpoints, codec

    def read(self, document_id: str, *, cursor: str | None = None, limit: int = MAX_PAGE_MESSAGES) -> dict:
        try:
            _uuid(document_id)
            if type(limit) is not int or not 1 <= limit <= MAX_PAGE_MESSAGES:
                raise ValueError()
        except Exception:
            raise ChatHistoryError("invalid_input") from None
        dataset_id = self._codec.dataset_id
        position = self._codec._resolve(cursor, document_id) if cursor is not None else None
        try:
            if position is None:
                observed = self._checkpoints.discover(document_id, dataset_id)
                if observed is None:
                    return {"dataset_id": dataset_id, "document_id": document_id,
                            "anchor": None, "anchor_run_id": None, "messages": [], "next_cursor": None}
                position = _Position(format_version=2, purpose="anchor", dataset_id=dataset_id,
                    document_id=document_id, run_id=observed.record.run_id,
                    root_checkpoint_id=observed.root_config["configurable"]["checkpoint_id"],
                    source_namespace=observed.source_config["configurable"]["checkpoint_ns"],
                    source_checkpoint_id=observed.source_config["configurable"]["checkpoint_id"], offset=0)
            else:
                observed = self._checkpoints.observe_at(document_id, position.run_id, dataset_id,
                    position.root_config(), source_config=position.source_config())
            messages = _public_messages(observed)
            end = len(messages) if position.purpose == "anchor" else position.offset
            if not 0 < end <= len(messages):
                raise ChatHistoryError("invalid_cursor")
            anchor = self._codec._issue(position.model_copy(update={"purpose": "anchor", "offset": 0}))
            count = min(limit, end)
            # Initial page is the latest window; cursors move to older windows.
            # Keep the newest whole rows when shrinking to the byte limit, and
            # serialize each candidate row only once. Page order stays forward.
            suffix_bytes = [0]
            for row in reversed(messages[end - count:end]):
                suffix_bytes.append(suffix_bytes[-1] + len(_json(row).encode("utf-8")))
            while count > 0:
                start = end - count
                next_cursor = self._codec._issue(position.model_copy(update={"purpose": "cursor", "offset": start})) \
                    if start > 0 else None
                page = {"dataset_id": dataset_id, "document_id": document_id, "anchor": anchor,
                        "anchor_run_id": position.run_id, "messages": [], "next_cursor": next_cursor}
                byte_size = len(_json(page).encode("utf-8")) + suffix_bytes[count] + count - 1
                if byte_size <= MAX_PAGE_BYTES:
                    page["messages"] = messages[start:end]
                    return page
                count -= 1  # Whole messages only; never truncate a body.
            raise ChatHistoryError("history_page_too_large")
        except ChatHistoryError:
            raise
        except AiCheckpointError as error:
            raise ChatHistoryError("checkpoint_unavailable" if error.code == "checkpoint_unavailable"
                                   else "invalid_checkpoint") from None
        except Exception:
            raise ChatHistoryError("invalid_checkpoint") from None
