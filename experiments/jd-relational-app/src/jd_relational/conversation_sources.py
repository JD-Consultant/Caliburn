"""Source-owner windows on the existing native conversation, without writes.

One saved Human and its preceding public AI context are selected by the App.
The source has a separate ItsDangerous purpose; it is not a JD or chat cursor.
Checkpoint decoding and public text projection remain with their existing owners.
New addresses use conversation: so Memory's existing reference parser can find
them. Previously issued bare signed v1 addresses remain readable verbatim.
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
_PREFIX = "conversation:"
_SALT = "caliburn.jd.conversation-source.v1"
# A completed interview window shares this owner, key and dataset, but never
# its signature domain: a token issued for one purpose must not verify as the
# other. C repair and the turn read tools stay strictly on `source`.
_WINDOW_PREFIX = "interview-window:"
_WINDOW_SALT = "caliburn.jd.interview-window.v1"
# A window's disambiguation context is a third purpose, not a smaller window:
# it starts on a prior question rather than a turn boundary and must never be
# mistaken for a range still awaiting consolidation.
_CONTEXT_PREFIX = "interview-context:"
_CONTEXT_SALT = "caliburn.jd.interview-context.v1"
# Verified B1 extraction budgets; this case's values, not a provider default.
MAX_WINDOW_CHARACTERS = 6000
MAX_CONTEXT_CHARACTERS = 1500
MAX_PLANNED_WINDOWS = 16
# Visible characters per window page, sized as the verified extraction reader.
MAX_PAGE_CHARACTERS = 3000
MAX_SOURCE_EXCHANGES = 50
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


class WindowBudgetExceeded(ValueError):
    """A complete turn, or the context it needs, does not fit the planned budget.

    Planning fails loudly instead of trimming: the caller raises the budget or
    leaves the range for a later batch. This is not a reference-resolution
    error, so it keeps its own type rather than widening the fixed public
    source error codes.
    """


class _WindowPosition(BaseModel):
    """One completed interview range on the root lineage, spanning whole turns.

    Unlike a turn source this is not pinned to a single run: `last` is the
    range's own final message. The namespace is always the root chain, so a
    window never depends on one turn's consultant child.
    """
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, revalidate_instances="always")
    format_version: int = Field(ge=1, le=1)
    purpose: Literal["window"]
    dataset_id: str
    document_id: str
    root_checkpoint_id: str = Field(min_length=1, max_length=256)
    first: str = Field(min_length=1, max_length=512)
    last: str = Field(min_length=1, max_length=512)
    root_run_id: str
    first_run_id: str
    last_run_id: str

    @field_validator("dataset_id", "document_id", "root_run_id", "first_run_id", "last_run_id")
    @classmethod
    def scope(cls, value):
        return _uuid(value)

    @model_validator(mode="after")
    def position(self):
        values = (self.root_checkpoint_id, self.first, self.last)
        if (any("\0" in value or not value.strip() for value in values)
                # A window starts on a turn boundary. Run identity is currently
                # the HumanMessage id; if that changes this must fail loudly
                # rather than silently accept a mid-turn start.
                or self.first != self.first_run_id):
            raise ValueError()
        return self

    def root_config(self):
        return {"configurable": {"thread_id": self.document_id, "checkpoint_ns": "",
                                  "checkpoint_id": self.root_checkpoint_id}}


class _ContextPosition(BaseModel):
    """One window's disambiguation range: a prior question through a turn end.

    It carries no range run bounds and has its own signature domain, so it can
    never be admitted as a range still awaiting consolidation. `root_run_id`
    is only the pinned position's own identity, needed to read it back.

    `source_first`/`source_last` name the window this range was cut for, so the
    pair itself is the proof: two contexts planned at one root for neighbouring
    windows are both legitimate, and recombining them would disambiguate the
    wrong speech. Version 2 adds that proof; a version 1 address carries none
    and is refused rather than trusted.
    """
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, revalidate_instances="always")
    format_version: int = Field(ge=2, le=2)
    purpose: Literal["context"]
    dataset_id: str
    document_id: str
    root_checkpoint_id: str = Field(min_length=1, max_length=256)
    root_run_id: str
    first: str = Field(min_length=1, max_length=512)
    last: str = Field(min_length=1, max_length=512)
    source_first: str = Field(min_length=1, max_length=512)
    source_last: str = Field(min_length=1, max_length=512)

    @field_validator("dataset_id", "document_id", "root_run_id")
    @classmethod
    def scope(cls, value):
        return _uuid(value)

    @model_validator(mode="after")
    def position(self):
        if any("\0" in value or not value.strip()
               for value in (self.root_checkpoint_id, self.first, self.last,
                             self.source_first, self.source_last)):
            raise ValueError()
        return self

    def root_config(self):
        return {"configurable": {"thread_id": self.document_id, "checkpoint_ns": "",
                                  "checkpoint_id": self.root_checkpoint_id}}


@dataclass(frozen=True, slots=True, repr=False)
class SourceMessage:
    message_id: str
    role: Literal["user", "assistant"]
    text: str


@dataclass(frozen=True, slots=True, repr=False)
class SourceExcerpt:
    source_ref: str
    messages: tuple[SourceMessage, ...]


@dataclass(frozen=True, slots=True, repr=False)
class SourceMessageMetadata:
    message_id: str
    role: Literal["user", "assistant"]


@dataclass(frozen=True, slots=True, repr=False)
class SourceRecord:
    source_ref: str
    messages: tuple[SourceMessageMetadata, ...]


class ConversationSourceCodec:
    __slots__ = ("_dataset_id", "_serializer", "_window_serializer", "_context_serializer")

    def __init__(self, secret_key: bytes, dataset_id: str):
        try:
            _uuid(dataset_id)
            if type(secret_key) is not bytes or len(secret_key) < 32:
                raise ValueError()
            self._dataset_id = dataset_id
            def domain(salt):
                return URLSafeSerializer(secret_key, salt=salt,
                    signer_kwargs={"digest_method": hashlib.sha256},
                    serializer_kwargs={"sort_keys": True, "ensure_ascii": False, "allow_nan": False})
            self._serializer = domain(_SALT)
            self._window_serializer = domain(_WINDOW_SALT)
            self._context_serializer = domain(_CONTEXT_SALT)
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
    def _bounded(position, prefix_bytes=0):
        payload = position.model_dump(mode="json")
        if prefix_bytes + (4 * len(_json(payload).encode("utf-8")) + 2) // 3 + 44 > MAX_REFERENCE_BYTES:
            raise ValueError()
        return payload

    def _issue(self, position: _SourcePosition) -> str:
        try:
            position = _SourcePosition.model_validate(position, strict=True)
            if position.dataset_id != self.dataset_id:
                raise ValueError()
            token = self._serializer.dumps(self._bounded(position, len(_PREFIX)))
            self._token(token)
            reference = _PREFIX + token
            if len(reference) > MAX_REFERENCE_BYTES:
                raise ValueError()
            return reference
        except Exception:
            raise ConversationSourceError("source_not_available") from None

    def _issue_window(self, position: _WindowPosition) -> str:
        return self._issue_purpose(position, _WindowPosition, self._window_serializer, _WINDOW_PREFIX)

    def _issue_context(self, position: _ContextPosition) -> str:
        return self._issue_purpose(position, _ContextPosition, self._context_serializer, _CONTEXT_PREFIX)

    def _resolve_context(self, context_ref, document_id) -> _ContextPosition:
        return self._resolve_purpose(context_ref, document_id, _ContextPosition,
                                     self._context_serializer, _CONTEXT_PREFIX)

    def _issue_purpose(self, position, model, serializer, prefix):
        try:
            position = model.model_validate(position, strict=True)
            if position.dataset_id != self.dataset_id:
                raise ValueError()
            token = serializer.dumps(self._bounded(position, len(prefix)))
            self._token(token)
            reference = prefix + token
            if len(reference) > MAX_REFERENCE_BYTES:
                raise ValueError()
            return reference
        except Exception:
            raise ConversationSourceError("source_not_available") from None

    def _resolve_purpose(self, reference, document_id, model, serializer, prefix):
        try:
            _uuid(document_id)
            if (type(reference) is not str or not 0 < len(reference) <= MAX_REFERENCE_BYTES
                    or not reference.startswith(prefix)):
                raise ValueError()
            token = reference.removeprefix(prefix)
            self._token(token)
            position = model.model_validate(serializer.loads(token), strict=True)
            self._bounded(position, len(reference) - len(token))
            if position.dataset_id != self.dataset_id or position.document_id != document_id:
                raise ValueError()
            return position
        except Exception:
            raise ConversationSourceError("invalid_ref") from None

    def _resolve_window(self, window_ref, document_id) -> _WindowPosition:
        return self._resolve_purpose(window_ref, document_id, _WindowPosition,
                                     self._window_serializer, _WINDOW_PREFIX)

    def _resolve(self, source_ref, document_id) -> _SourcePosition:
        try:
            _uuid(document_id)
            if type(source_ref) is not str or not 0 < len(source_ref) <= MAX_REFERENCE_BYTES:
                raise ValueError()
            token = source_ref.removeprefix(_PREFIX)
            self._token(token)
            position = _SourcePosition.model_validate(self._serializer.loads(token), strict=True)
            self._bounded(position, len(source_ref) - len(token))
            if position.dataset_id != self.dataset_id or position.document_id != document_id:
                raise ValueError()
            return position
        except Exception:
            raise ConversationSourceError("invalid_ref") from None


def _visible(messages):
    """Saved public question/answer text only, reporting what was left out.

    Tool and system messages, and any non-text content block, are canonical but
    are not the employee's words. They are named in the omitted kinds rather
    than silently dropped.
    """
    visible, omitted = [], set()
    for message in messages:
        if isinstance(message, BaseMessageChunk) or not isinstance(message, (HumanMessage, AIMessage)):
            omitted.add(getattr(message, "type", "unknown"))
            continue
        parts = [message.content] if isinstance(message.content, str) else message.content
        texts = []
        for part in parts:
            if isinstance(part, str):
                texts.append(part)
            elif (isinstance(part, dict) and part.get("type") in {"text", "output_text"}
                    and isinstance(part.get("text"), str)):
                texts.append(part["text"])
            else:
                omitted.add(part.get("type", "unknown") if isinstance(part, dict) else "unknown")
        visible.append((message.id, "user" if isinstance(message, HumanMessage) else "assistant",
                        "".join(texts)))
    return visible, omitted


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
                from .ai_history import AiRunHistory
                observed = AiRunHistory(self._checkpoints).find(
                    document_id, run_id, self.dataset_id)
                if observed is None:
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

    @staticmethod
    def _record(excerpt: SourceExcerpt) -> SourceRecord:
        return SourceRecord(
            source_ref=excerpt.source_ref,
            messages=tuple(SourceMessageMetadata(
                message_id=message.message_id, role=message.role)
                for message in excerpt.messages),
        )

    def window_exchanges(self, window_ref, document_id) -> tuple[SourceRecord, ...]:
        """Issue one fixed turn source per settled turn in this saved window.

        `_pinned_range` proves the window on the current canonical lineage and
        returns its turns in native message order.  Source tokens remain
        addresses only; their bytes are never used to sort the result.
        """
        _, _, turns, first = self._pinned_range(window_ref, document_id)
        return tuple(self._record(self.capture(document_id, turn["input_id"]))
                     for turn in turns[first:])

    def history_exchanges(self, through_reference, document_id, *, offset: int = 0,
                          limit: int = MAX_SOURCE_EXCHANGES) -> dict:
        """Page safe historical exchanges at one already fixed window root.

        The window is the upper bound, so conversation activity after it was
        issued cannot enlarge a resumed page.  `offset` is an application
        cursor over this owner-proven ordered list; it is never a model field
        or a persistent citation.
        """
        if (type(offset) is not int or offset < 0 or type(limit) is not int
                or not 1 <= limit <= MAX_SOURCE_EXCHANGES):
            raise ConversationSourceError("invalid_ref")
        _, _, turns, _ = self._pinned_range(through_reference, document_id)
        if offset > len(turns):
            raise ConversationSourceError("invalid_ref")
        end = min(len(turns), offset + limit)
        exchanges = tuple(self._record(self.capture(document_id, turn["input_id"]))
                          for turn in turns[offset:end])
        return {"order": "oldest_to_newest", "exchanges": exchanges,
                "next_offset": end if end < len(turns) else None}

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

    def read_source_page(self, source_ref, document_id, offset: int = 0) -> dict:
        """Read public text from one exact source using an application cursor."""
        if type(offset) is not int or offset < 0:
            raise ConversationSourceError("invalid_ref")
        excerpt = self.read(source_ref, document_id)
        total = sum(len(message.text) for message in excerpt.messages)
        if offset > total:
            raise ConversationSourceError("invalid_ref")
        segments, seen, remaining = [], 0, MAX_PAGE_CHARACTERS
        for message in excerpt.messages:
            begin = max(0, offset - seen)
            if begin < len(message.text) and remaining:
                fragment = message.text[begin:begin + remaining]
                segments.append({"message_id": message.message_id, "role": message.role,
                                 "text": fragment, "text_offset": begin})
                remaining -= len(fragment)
            seen += len(message.text)
        end_offset = offset + MAX_PAGE_CHARACTERS - remaining
        return {"reference": source_ref, "segments": segments,
                "next_offset": end_offset if end_offset < total else None}

    def validate_reference(self, source_ref, document_id) -> None:
        """Verify the original signed locator and scope without storage I/O.

        This makes no claim that the checkpoint still exists or that its public
        text supports a Memory statement. read() owns the actual fixed read.
        """
        self._codec._resolve(source_ref, document_id)

    def safe_turns(self, document_id) -> tuple[dict, ...]:
        """This document's settled turns, each verified at its own terminal.

        A turn is settled only when its own run record is non-running and its
        observation is closed, which `_settle` writes after confirming every JD
        receipt and C result. The walk stops at the first unsettled turn: a
        later terminal never releases an earlier one, and a settled
        `failed`/`cancelled` turn still keeps the employee's saved words.
        """
        return self._settled(document_id)[2]

    def _settled(self, document_id):
        """One pinned read of this document, with its settled turns."""
        try:
            _uuid(document_id)
            observed = self._checkpoints.discover(document_id, self.dataset_id)
        except AiCheckpointError:
            raise
        except Exception:
            raise ConversationSourceError("source_not_available") from None
        if observed is None:
            return None, (), ()
        return observed, observed.messages, self._settled_turns(document_id, observed.messages)

    def _cursor_boundary(self, document_id, reference, observed, turns):
        """Resolve a published cursor at its own position, on this lineage.

        A valid signature is not a position. The cursor is read where it was
        issued; its own root must be a real ancestor of the conversation being
        planned, and its range must end exactly on a settled turn. A shared
        identifier is never accepted as proof, and a cursor stopping inside a
        turn is refused rather than moving admission past that turn's speech.
        """
        position = self._codec._resolve_window(reference, document_id)
        cursor = self._pinned(document_id, position.root_run_id, position.root_config())
        # IDs are stable addresses, not proof that the saved prefix has the
        # same content. Native message updates can retain an ID, so compare
        # the complete immutable message values before using the cursor to
        # advance admission.
        cursor_messages = cursor.messages
        if cursor_messages != observed.messages[:len(cursor_messages)]:
            raise ConversationSourceError("invalid_ref")
        saved = [message.id for message in cursor_messages]
        order = [message.id for message in observed.messages]
        if (position.first not in saved or position.last not in saved
                or saved.index(position.first) > saved.index(position.last)
                or saved != order[:len(saved)]):
            raise ConversationSourceError("invalid_ref")
        if not self._on_lineage(document_id, position.root_checkpoint_id, observed):
            raise ConversationSourceError("invalid_ref")
        if position.last not in {turn["last"] for turn in turns}:
            raise ConversationSourceError("invalid_ref")
        return order.index(position.last)

    def _on_lineage(self, document_id, checkpoint_id, observed):
        """Whether a pinned root really lies on this observed position's chain.

        The position itself first, then the same bounded public parent walk
        `find` uses. A sibling branch still reads back at its own root, so
        being readable is never taken as proof of being on this chain.
        """
        from .ai_history import AiRunHistory
        root = observed.root_config["configurable"]["checkpoint_id"]
        return checkpoint_id == root or AiRunHistory(self._checkpoints).ancestor_of(
            document_id, checkpoint_id, observed.root_config)

    def _after_cursor(self, observed, messages, turns, after_reference, document_id):
        """First settled turn the published cursor has not covered.

        `after_reference` may only be the publication head's own completed
        window. A turn source, or a cursor that cannot be proven on this
        lineage at a complete boundary, stops admission: it is never reset and
        never read as "nothing done".
        """
        if after_reference is None:
            return 0
        boundary = self._cursor_boundary(document_id, after_reference, observed, turns)
        order = [message.id for message in messages]
        for index, turn in enumerate(turns):
            if order.index(turn["first"]) > boundary:
                return index
        return len(turns)

    def pending_windows(self, document_id, after_reference=None) -> tuple[dict, ...]:
        """Settled turns that explicitly asked for background consolidation.

        This is a trigger list, not a menu of topics: it answers only which
        turn asked to be scheduled. What a dispatcher may actually process is
        `unprocessed_source`, whose contiguous range also carries settled turns
        that never asked. A turn after an unsettled one is not listed at all.
        """
        from caliburn_memory.requests import has_saved_request
        observed, messages, turns = self._settled(document_id)
        order = [message.id for message in messages]
        requested = []
        for turn in turns[self._after_cursor(observed, messages, turns, after_reference, document_id):]:
            spoken = messages[order.index(turn["first"]):order.index(turn["last"]) + 1]
            if has_saved_request(spoken):
                requested.append(dict(turn))
        return tuple(requested)

    def unprocessed_source(self, document_id, after_reference=None,
                           through_reference=None) -> dict | None:
        """The contiguous settled range after the published cursor, or None.

        Quiet settled turns stay inside the range; the range ends at the first
        unsettled turn, so a later request can never jump an open gap. Given a
        fixed target the range is read inside that target and ends where it
        does: speech saved after admission waits for an admission of its own
        rather than quietly enlarging work already under way.
        """
        if through_reference is None:
            observed, messages, turns = self._settled(document_id)
            start = self._after_cursor(observed, messages, turns, after_reference, document_id)
        else:
            start, turns = self._target_start(document_id, through_reference, after_reference)[:2]
            if start is None:
                return None
        remaining = turns[start:]
        if not remaining:
            return None
        return {"first_run_id": remaining[0]["input_id"],
                "last_run_id": remaining[-1]["input_id"]}

    def _settled_turns(self, document_id, messages):
        from .ai_history import AiRunHistory
        history = AiRunHistory(self._checkpoints)
        order = [message.id for message in messages]
        turns = []
        for message in messages:
            if not isinstance(message, HumanMessage):
                continue
            terminal = history.find(document_id, message.id, self.dataset_id)
            if terminal is None or not terminal.closed or terminal.record.status == "running":
                break
            saved = [item.id for item in terminal.messages]
            # Lineage, not identity: this turn's own terminal view must be an
            # exact prefix of the pinned conversation we are planning over.
            if not saved or saved != order[:len(saved)]:
                raise ConversationSourceError("invalid_ref")
            status = terminal.record.status
            turns.append({"input_id": message.id, "status": status,
                          "answer_succeeded": status == "completed",
                          "first": message.id, "last": saved[-1]})
        return tuple(turns)

    def capture_window(self, document_id, *, first_run_id, last_run_id) -> str:
        """Issue one completed-window reference over whole settled turns.

        Both bounds must be settled turns of this document in order; the range
        is therefore contiguous by construction. The reference is pinned to the
        last turn's own terminal root, so it never depends on what is latest.
        """
        turns = self.safe_turns(document_id)
        identifiers = [turn["input_id"] for turn in turns]
        try:
            start, end = identifiers.index(first_run_id), identifiers.index(last_run_id)
            if start > end:
                raise ValueError()
        except Exception:
            raise ConversationSourceError("invalid_ref") from None
        from .ai_history import AiRunHistory
        terminal = AiRunHistory(self._checkpoints).find(document_id, last_run_id, self.dataset_id)
        try:
            position = _WindowPosition(format_version=1, purpose="window",
                dataset_id=self.dataset_id, document_id=document_id,
                root_checkpoint_id=terminal.root_config["configurable"]["checkpoint_id"],
                first=first_run_id, last=turns[end]["last"],
                root_run_id=last_run_id, first_run_id=first_run_id, last_run_id=last_run_id)
        except Exception:
            raise ConversationSourceError("source_not_available") from None
        return self._codec._issue_window(position)

    def read_window(self, window_ref, document_id, offset: int = 0) -> dict:
        """Read one page of a completed window at its own fixed position.

        Paging cuts visible text only: every page lists the window's whole
        turns, so a caller never has to assemble pages to learn a terminal.
        Offsets count Unicode code points over the concatenated visible text
        with no separator inserted.
        """
        position = self._codec._resolve_window(window_ref, document_id)
        if type(offset) is not int or type(offset) is bool or offset < 0:
            raise ConversationSourceError("invalid_ref")
        try:
            observed = self._checkpoints.observe_at(document_id, position.root_run_id,
                self.dataset_id, position.root_config())
        except AiCheckpointError as error:
            raise ConversationSourceError(
                "invalid_ref" if error.code == "invalid_input" else "source_not_available") from None
        messages = observed.messages
        order = [message.id for message in messages]
        try:
            start, end = order.index(position.first), order.index(position.last)
            if start > end:
                raise ValueError()
        except Exception:
            raise ConversationSourceError("invalid_ref") from None
        turns = [turn for turn in self._settled_turns(document_id, messages[:end + 1])
                 if turn["input_id"] in order[start:end + 1]]
        if not turns or turns[0]["input_id"] != position.first_run_id or turns[-1]["last"] != position.last:
            raise ConversationSourceError("invalid_ref")
        visible, omitted = _visible(messages[start:end + 1])
        total = sum(len(text) for _, _, text in visible)
        if offset > total:
            raise ConversationSourceError("invalid_ref")
        segments, seen, remaining = [], 0, MAX_PAGE_CHARACTERS
        for message_id, role, text in visible:
            begin = max(0, offset - seen)
            if begin < len(text) and remaining:
                fragment = text[begin:begin + remaining]
                segments.append({"message_id": message_id, "role": role,
                                 "text": fragment, "text_offset": begin})
                remaining -= len(fragment)
            seen += len(text)
        end_offset = offset + MAX_PAGE_CHARACTERS - remaining
        return {"reference": window_ref, "segments": segments, "turns": turns,
                "omitted_content_types": sorted(omitted),
                "next_offset": end_offset if end_offset < total else None}

    @staticmethod
    def _budgets(max_chars, context_chars):
        if (type(max_chars) is not int or type(max_chars) is bool or not 1 <= max_chars <= 24000
                or type(context_chars) is not int or type(context_chars) is bool
                or not 0 <= context_chars < max_chars):
            raise ConversationSourceError("invalid_ref")

    def _groups(self, messages, turns):
        order = [message.id for message in messages]
        return [messages[order.index(turn["first"]):order.index(turn["last"]) + 1] for turn in turns]

    @staticmethod
    def _size(messages):
        return sum(len(text) for _, _, text in _visible(messages)[0])

    @staticmethod
    def _between(messages, first, last):
        order = [message.id for message in messages]
        try:
            start, end = order.index(first), order.index(last)
            if start > end:
                raise ValueError()
        except Exception:
            raise ConversationSourceError("invalid_ref") from None
        return messages[start:end + 1]

    def _window_root(self, document_id, last_run_id):
        """The pinned root is that last turn's own terminal, never the latest."""
        from .ai_history import AiRunHistory
        terminal = AiRunHistory(self._checkpoints).find(document_id, last_run_id, self.dataset_id)
        if terminal is None:
            raise ConversationSourceError("invalid_ref")
        return terminal.root_config["configurable"]["checkpoint_id"]

    def _pinned(self, document_id, run_id, root_config):
        try:
            return self._checkpoints.observe_at(document_id, run_id, self.dataset_id, root_config)
        except AiCheckpointError as error:
            raise ConversationSourceError(
                "invalid_ref" if error.code == "invalid_input" else "source_not_available") from None

    def _issue_window_between(self, root, root_run_id, document_id, first_turn, last_turn):
        try:
            position = _WindowPosition(format_version=1, purpose="window",
                dataset_id=self.dataset_id, document_id=document_id, root_checkpoint_id=root,
                first=first_turn["first"], last=last_turn["last"],
                root_run_id=root_run_id, first_run_id=first_turn["input_id"], last_run_id=last_turn["input_id"])
        except Exception:
            raise ConversationSourceError("source_not_available") from None
        return self._codec._issue_window(position)

    def _issue_context_between(self, root, root_run_id, document_id, first, last,
                               *, source_first, source_last):
        try:
            position = _ContextPosition(format_version=2, purpose="context",
                dataset_id=self.dataset_id, document_id=document_id,
                root_checkpoint_id=root, root_run_id=root_run_id, first=first, last=last,
                source_first=source_first, source_last=source_last)
        except Exception:
            raise ConversationSourceError("source_not_available") from None
        return self._codec._issue_context(position)

    def plan_windows(self, document_id, *, first_run_id, last_run_id,
                     max_chars: int = MAX_WINDOW_CHARACTERS,
                     context_chars: int = MAX_CONTEXT_CHARACTERS) -> tuple[dict, ...]:
        """Plan whole-turn windows, each with the context needed to read it.

        Ported from the verified extraction planner: an oversize turn fails
        rather than losing its middle, and a disambiguation prefix that cannot
        fit is reported instead of being trimmed. Context must reach back to
        the nearest prior visible question and include the answers between.
        """
        self._budgets(max_chars, context_chars)
        _, messages, turns = self._settled(document_id)
        first, last = self._bounds(turns, first_run_id, last_run_id)
        return self._plan(document_id, messages, turns, first, last,
                          root=self._window_root(document_id, last_run_id), root_run_id=last_run_id,
                          max_chars=max_chars, context_chars=context_chars)

    def plan_saved_windows(self, window_ref, document_id, *,
                           max_chars: int = MAX_WINDOW_CHARACTERS,
                           context_chars: int = MAX_CONTEXT_CHARACTERS) -> tuple[dict, ...]:
        """Plan inside one already issued window, at that window's own position.

        The reference decides where this reads. Its own pinned root must lie on
        this document's chain and still carry the exact range it names as whole
        settled turns; every pair is then cut from that one fixed snapshot. A
        range that cannot be proven there fails rather than being replanned
        against whatever is latest, so a window issued on an abandoned branch
        can never hand B1 another branch's work under the saved reference.
        """
        self._budgets(max_chars, context_chars)
        position, pinned, turns, first = self._pinned_range(window_ref, document_id)
        return self._plan(document_id, pinned.messages, turns, first, len(turns) - 1,
                          root=position.root_checkpoint_id, root_run_id=position.root_run_id,
                          max_chars=max_chars, context_chars=context_chars)

    def _pinned_range(self, window_ref, document_id):
        """One issued window, read where it was issued, with its settled turns.

        The reference decides the position: its own pinned root must lie on
        this document's chain and still carry the exact range it names as whole
        settled turns. The turns stop at that range's end, so nothing saved
        after the reference was issued can be planned under it.
        """
        position = self._codec._resolve_window(window_ref, document_id)
        current, _, _ = self._settled(document_id)
        pinned = self._pinned(document_id, position.root_run_id, position.root_config())
        if current is None or not self._on_lineage(document_id, position.root_checkpoint_id, current):
            raise ConversationSourceError("invalid_ref")
        turns = self._settled_turns(document_id, pinned.messages)
        first, last = self._bounds(turns, position.first_run_id, position.last_run_id)
        if position.first != turns[first]["first"] or position.last != turns[last]["last"]:
            raise ConversationSourceError("invalid_ref")
        return position, pinned, turns[:last + 1], first

    def _target_start(self, document_id, through_reference, after_reference):
        """Where admission resumes inside a fixed target, or None when covered.

        A cursor already reaching past the target leaves it nothing to do, but
        that is only true when the target really lies inside the published
        range on the cursor's own chain: the cursor is read where it was issued
        and the target proven there, never inferred from a longer window or a
        shared identifier. A cursor stopping before the target begins is
        refused rather than closed over; whether a new range may be admitted
        at all stays with `follows`, which is the one rule for that.
        """
        position, pinned, turns, first = self._pinned_range(through_reference, document_id)
        if after_reference is None:
            return first, turns, position, pinned
        cursor = self._codec._resolve_window(after_reference, document_id)
        published = self._pinned(document_id, cursor.root_run_id, cursor.root_config())
        if len(published.messages) <= len(pinned.messages):
            start = self._after_cursor(pinned, pinned.messages, turns, after_reference, document_id)
            # Turns sitting between the cursor and the target's own start are
            # unconsolidated. Planning the target anyway would hand B1 a batch
            # that jumps them, and publishing it would carry the cursor past
            # that speech for good, so the gap fails here instead.
            if start < first:
                raise ConversationSourceError("invalid_ref")
            return start, turns, position, pinned
        covered = self._cursor_boundary(document_id, after_reference, published,
                                        self._settled_turns(document_id, published.messages))
        order = [message.id for message in published.messages]
        if (not self._on_lineage(document_id, position.root_checkpoint_id, published)
                or position.last not in order or order.index(position.last) > covered):
            raise ConversationSourceError("invalid_ref")
        return None, turns, position, pinned

    def plan_saved_batch(self, target_reference, document_id, *, after_reference=None,
                         max_chars: int = MAX_WINDOW_CHARACTERS,
                         context_chars: int = MAX_CONTEXT_CHARACTERS,
                         max_windows: int = MAX_PLANNED_WINDOWS) -> dict:
        """Cut one bounded batch out of an already fixed target.

        B1 takes a single window, so the batch is issued as one at the target's
        own root: no caller assembles a token out of bounds, and no batch is
        replanned against whatever is latest. The published cursor decides
        where this batch begins and the target where it may end, so a long
        target keeps its tail for a later batch without needing a new request.
        `covers_whole_range` reports planning coverage only, never that the
        batch was saved or published. A batch covering an untouched target is
        that target, so an unchanged range keeps its input identity.
        """
        self._budgets(max_chars, context_chars)
        if type(max_windows) is not int or type(max_windows) is bool or max_windows < 1:
            raise ConversationSourceError("invalid_ref")
        start, turns, position, pinned = self._target_start(
            document_id, target_reference, after_reference)
        if start is None or start >= len(turns):
            return {"source_reference": None, "covers_whole_range": True}
        planned = self._plan(document_id, pinned.messages, turns, start, len(turns) - 1,
                             root=position.root_checkpoint_id, root_run_id=position.root_run_id,
                             max_chars=max_chars, context_chars=context_chars)
        batch = planned[:max_windows]
        edge = self._codec._resolve_window(batch[-1]["source_reference"], document_id)
        return {"source_reference": self._issue_window_between(
                    position.root_checkpoint_id, position.root_run_id, document_id, turns[start],
                    next(turn for turn in turns if turn["input_id"] == edge.last_run_id)),
                "covers_whole_range": len(planned) <= max_windows}

    @staticmethod
    def _bounds(turns, first_run_id, last_run_id):
        identifiers = [turn["input_id"] for turn in turns]
        try:
            first, last = identifiers.index(first_run_id), identifiers.index(last_run_id)
            if first > last:
                raise ValueError()
        except Exception:
            raise ConversationSourceError("invalid_ref") from None
        return first, last

    def _plan(self, document_id, messages, turns, first, last, *, root, root_run_id,
              max_chars, context_chars):
        """Cut every pair from one fixed snapshot, at one fixed root."""
        groups = self._groups(messages, turns)
        sizes = [self._size(group) for group in groups]
        if any(size > max_chars for size in sizes[first:last + 1]):
            raise WindowBudgetExceeded("window_budget_exceeded")
        planned, index = [], first
        while index <= last:
            span, used = None, 0
            if index:
                prior = groups[index - 1]
                question = next((message for group in reversed(groups[:index])
                                 for message in reversed(group)
                                 if isinstance(message, AIMessage) and self._size([message])), None)
                if question is not None:
                    required = self._between(messages, question.id, prior[-1].id)
                    used = self._size(required)
                    if used > context_chars or used + sizes[index] > max_chars:
                        raise WindowBudgetExceeded("window_budget_exceeded")
                    span = (question.id, prior[-1].id)
                # A whole prior turn is allowed only when it still carries the
                # required question; it never replaces an older one.
                if ((question is None or any(m.id == question.id for m in prior))
                        and sizes[index - 1] <= context_chars
                        and sizes[index - 1] + sizes[index] <= max_chars):
                    span = (prior[0].id, prior[-1].id)
                    used = sizes[index - 1]
            end = index
            while end <= last and used + sizes[end] <= max_chars:
                used += sizes[end]
                end += 1
            # The window is issued first so its context can name it: the pair is
            # its own proof, and neighbouring pairs can never be recombined.
            planned.append({"source_reference": self._issue_window_between(
                root, root_run_id, document_id, turns[index], turns[end - 1]),
                "context_reference": None if span is None else self._issue_context_between(
                    root, root_run_id, document_id, *span,
                    source_first=turns[index]["first"], source_last=turns[end - 1]["last"])})
            index = end
        return tuple(planned)

    def plan_batch(self, document_id, *, first_run_id, last_run_id,
                   max_chars: int = MAX_WINDOW_CHARACTERS,
                   context_chars: int = MAX_CONTEXT_CHARACTERS,
                   max_windows: int = MAX_PLANNED_WINDOWS) -> dict:
        """Bound one B1 batch without consuming or dropping the remaining tail.

        The tail needs no extra state: the published cursor decides where the
        next batch starts. `covers_whole_range` exists so a caller can never
        take a prefix and report the whole range as done.
        """
        if type(max_windows) is not int or type(max_windows) is bool or max_windows < 1:
            raise ConversationSourceError("invalid_ref")
        planned = self.plan_windows(document_id, first_run_id=first_run_id,
                                    last_run_id=last_run_id, max_chars=max_chars,
                                    context_chars=context_chars)
        return {"windows": planned[:max_windows],
                "covers_whole_range": len(planned) <= max_windows}

    def validate_saved_window(self, source_reference, context_reference, document_id, *,
                              max_chars: int = MAX_WINDOW_CHARACTERS,
                              context_chars: int = MAX_CONTEXT_CHARACTERS) -> None:
        """Re-check one already planned pair; never widen or replan it.

        Re-extraction reads the window it was given. A budget change must fail
        loudly rather than quietly select a different range.
        """
        self._budgets(max_chars, context_chars)
        page = self.read_window(source_reference, document_id)
        position = self._codec._resolve_window(source_reference, document_id)
        # One batch pins every window on the same root, so the position is read
        # by the identity that root belongs to, not by this window's own last
        # turn: only the final window of a batch shares the two.
        observed = self._pinned(document_id, position.root_run_id, position.root_config())
        source_size = self._size(self._between(observed.messages, position.first, position.last))
        context_size = 0
        if context_reference is not None:
            self.validate_window_pair(source_reference, context_reference, document_id)
            context = self._codec._resolve_context(context_reference, document_id)
            context_size = self._size(self._between(observed.messages, context.first, context.last))
        if context_size > context_chars or context_size + source_size > max_chars:
            raise WindowBudgetExceeded("window_budget_exceeded")
        if not page["turns"]:
            raise ConversationSourceError("invalid_ref")

    def source_progress(self, reference, previous, document_id) -> Literal["covered", "next"]:
        """Classify one fixed range against the published cursor.

        Both references are resolved at their own immutable positions and then
        proven against one current canonical snapshot.  Reaching the target's
        complete terminal means it is already covered; otherwise only the
        first whole settled turn after the cursor may begin new work.  Partial
        overlap, a gap, an abandoned branch or an unprovable position fails
        closed instead of becoming an implicit retry.
        """
        current, messages, turns = self._settled(document_id)
        if current is None:
            raise ConversationSourceError("invalid_ref")
        # Validate each issued range at its own fixed position before comparing
        # their cumulative terminal boundaries on the canonical snapshot.
        target, _, _, _ = self._pinned_range(reference, document_id)
        self._pinned_range(previous, document_id)
        target_boundary = self._cursor_boundary(document_id, reference, current, turns)
        previous_boundary = self._cursor_boundary(document_id, previous, current, turns)
        if previous_boundary >= target_boundary:
            return "covered"
        order = [message.id for message in messages]
        following = [turn for turn in turns if order.index(turn["first"]) > previous_boundary]
        if following and following[0]["first"] == target.first:
            return "next"
        raise ConversationSourceError("invalid_ref")

    def follows(self, reference, previous, document_id) -> None:
        """Admit a new range only directly after the published one.

        Each reference is checked at its own pinned position: the candidate
        must sit on this document's canonical chain, and the published cursor
        must be an ancestor of that very position, not merely of whatever is
        latest. Order then comes from the candidate's own saved conversation,
        never identifiers or timestamps. An overlapping, earlier, turn-skipping
        or side-branch range is refused rather than treated as an implicit
        retry: history that still reads back is not an admissible new input.
        """
        if self.source_progress(reference, previous, document_id) != "next":
            raise ConversationSourceError("invalid_ref")

    def read_context(self, context_ref, document_id) -> dict:
        """Read a window's disambiguation range at its own fixed position.

        A context range is never a new source and never an admission boundary,
        but the terminals it does cover stay provable: a settled turn whose
        input lies inside the range is reported with its own status, so a
        cancelled or failed answer can never be read as a successful one. A
        range holding only a leading question reports no turns because it
        contains none — that is a fact about the range, not a default.
        """
        position = self._codec._resolve_context(context_ref, document_id)
        observed = self._pinned(document_id, position.root_run_id, position.root_config())
        covered = self._between(observed.messages, position.first, position.last)
        visible, omitted = _visible(covered)
        order = [message.id for message in observed.messages]
        inside = {message.id for message in covered}
        turns = [turn for turn in self._settled_turns(
                     document_id, observed.messages[:order.index(position.last) + 1])
                 if turn["input_id"] in inside]
        return {"reference": context_ref,
                "segments": [{"message_id": message_id, "role": role, "text": text}
                             for message_id, role, text in visible if text],
                "turns": turns,
                "omitted_content_types": sorted(omitted)}

    def validate_context_reference(self, context_ref, document_id) -> None:
        """Shape, signature domain and scope only, with no storage I/O."""
        self._codec._resolve_context(context_ref, document_id)

    def validate_window_pair(self, source_reference, context_reference, document_id) -> None:
        """Prove this context was issued for exactly this window, with no I/O.

        Same owner, same document, same fixed root, and the window bounds the
        context itself records. Two contexts planned at one root for adjacent
        windows are both valid addresses and both fit the same budget, so
        neither of those is evidence of belonging together; re-extraction has
        to continue on the prefix its own window was planned with.
        """
        position = self._codec._resolve_window(source_reference, document_id)
        context = self._codec._resolve_context(context_reference, document_id)
        if (context.root_checkpoint_id != position.root_checkpoint_id
                or context.source_first != position.first
                or context.source_last != position.last):
            raise ConversationSourceError("invalid_ref")

    def validate_window_reference(self, window_ref, document_id) -> None:
        """Verify a completed-window locator issued by this same owner.

        Shape, signature domain and scope only, with no storage I/O — the same
        boundary `validate_reference` keeps for a turn source. Publication may
        record this reference before its content is read, and a turn source can
        never satisfy it.
        """
        self._codec._resolve_window(window_ref, document_id)

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
