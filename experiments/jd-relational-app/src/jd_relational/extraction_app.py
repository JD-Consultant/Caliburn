"""B1 application wiring: the adopted extraction workflow over this App's owner.

This is the existing interview-to-Memory stage, not a JD editor and not another
user-facing page. The workflow, prompt, three output fields, correction
allowance, save and resume rules stay in `caliburn_memory.extraction`; nothing
here re-implements them, adds a parser, an agent loop or a second flow.

Only B1 is bound to OpenAI. The conversation consultant keeps its pinned
Anthropic runtime; there is no app-wide provider switch, fallback or user
choice. B1 is a structured extraction graph, not a tool-calling agent, so the
role budget below is its own and is not the consultant's.
"""

from contextlib import contextmanager
from dataclasses import dataclass
import math
from uuid import UUID

from caliburn_memory import MemoryArtifacts
from caliburn_memory.extraction import ExtractionOutput, ExtractionWorkflow
from caliburn_memory.sources import ExtractionSourceReader, InvalidSourceReference
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver

from .ai_checkpoints import AiCheckpointError
from .conversation_sources import ConversationSourceError, ConversationSourceService
from .memory_sources import MemorySourceReader


# This case's tested B1 profile, not a provider default: explicit visible output
# and effort, verified for this role rather than inherited from the class.
MAX_OUTPUT_TOKENS = 8192
REASONING_EFFORT = "high"


def accepted(raw: AIMessage) -> bool:
    """Terminal evidence for one structured response, from public SDK fields.

    A saved artifact requires a normally completed, unrefused response. The
    official guide names the same three checks an application must make before
    trusting a structured output: the response reached `completed`, no content
    block is a refusal, and the payload matches the schema (the workflow owns
    that last one). `status` is also what reports truncation: a response cut off
    at the output ceiling arrives as `incomplete`, never as a short success.
    HTTP 200 alone, or text that merely parses, is not evidence of any of this.
    """
    refused = raw.additional_kwargs.get("refusal") or any(
        isinstance(block, dict) and (block.get("type") == "refusal" or
            (block.get("type") == "non_standard" and "refusal" in block.get("value", {})))
        for block in raw.content_blocks)
    return not refused and raw.response_metadata.get("status") == "completed"


def build_extraction_model(*, model: str, api_key: str, http_client, base_url: str | None = None,
                           request_timeout: float | None = None,
                           reasoning_effort: str = REASONING_EFFORT) -> ChatOpenAI:
    """Bind B1's own model to the supplied transport; no server-side storage.

    An oversize input must fail loudly rather than arrive shortened. That is
    already the default behaviour — the current reference marks `truncation`
    deprecated and documents `disabled` as its default, under which an input
    past the context window returns a 400 — so this sends no such parameter and
    relies on the source budget plus that 400. Server storage stays off: the
    canonical record is this App's Saver and Memory, never the provider's.
    """
    if request_timeout is not None and (not math.isfinite(request_timeout) or request_timeout <= 0):
        raise ValueError("request_timeout must be positive and finite")
    return ChatOpenAI(
        model=model, api_key=api_key, base_url=base_url, http_client=http_client,
        # LangChain passes this to the SDK explicitly; a timeout set only on the
        # HTTP client is overwritten by request_timeout=None during binding.
        timeout=request_timeout if request_timeout is not None else http_client.timeout,
        use_responses_api=True, output_version="responses/v1", store=False,
        reasoning={"effort": reasoning_effort, "context": "all_turns"},
        model_kwargs={"parallel_tool_calls": False},
    )


@dataclass(frozen=True, slots=True, repr=False)
class ExtractionSourceAdapter(ExtractionSourceReader):
    """One document's completed-window port, over the single source owner.

    Planning, paging, saved-window revalidation and admission all stay with the
    owner; this only binds the document and translates its fixed error codes to
    the package's correctable-address error. No second cursor, no second
    conversation store and no reference format of its own.
    """
    service: ConversationSourceService
    document_id: str

    def __post_init__(self):
        if not isinstance(self.service, ConversationSourceService):
            raise ConversationSourceError("source_not_available")
        try:
            if type(self.document_id) is not str or str(UUID(self.document_id)) != self.document_id:
                raise ValueError()
        except Exception:
            raise ConversationSourceError("invalid_ref") from None

    @staticmethod
    def _address(error: ConversationSourceError):
        if error.code == "invalid_ref":
            return InvalidSourceReference("invalid_source_reference")
        return error

    @contextmanager
    def _owner_errors(self):
        """One boundary: a correctable address, or not available right now.

        A reached ancestor bound or a broken chain surfaces from the owner as
        its own checkpoint error. That is the right signal there — the limit is
        reported rather than read as "no earlier turn" — but it is not part of
        this port's contract, so it maps through the same fixed codes the owner
        already uses for a pinned read. B1 therefore sees an explicit failure,
        never an internal type and never a quietly empty plan.
        """
        try:
            yield
        except ConversationSourceError as error:
            raise self._address(error) from error
        except AiCheckpointError as error:
            raise self._address(ConversationSourceError(
                "invalid_ref" if error.code == "invalid_input" else "source_not_available")) from error

    def validate_reference(self, reference: str) -> None:
        """A completed window only; a turn source can never satisfy B1."""
        with self._owner_errors():
            self.service.validate_window_reference(reference, self.document_id)

    def extraction_windows(self, reference: str, *, max_chars: int, context_chars: int) -> list[dict]:
        """Plan inside the reference's own fixed position, never the latest one.

        The owner is handed the window itself rather than bounds read out of
        it, so the range is proven and every pair is cut where that reference
        was issued. A window pinned to an abandoned branch fails here instead
        of being replanned against whatever is currently canonical.
        """
        with self._owner_errors():
            return list(self.service.plan_saved_windows(
                reference, self.document_id, max_chars=max_chars, context_chars=context_chars))

    def read(self, reference: str, offset: int = 0) -> dict:
        """One page of a window, or the whole disambiguation range.

        A context range is bounded by `context_chars`, so the owner reads it
        whole and there is no next page. Its turn terminals are the owner's,
        passed through unchanged: B1 has to be able to tell a cancelled or
        failed context turn from a successful one. Being readable for
        disambiguation still never makes it an admissible window.
        """
        with self._owner_errors():
            try:
                self.service.validate_window_reference(reference, self.document_id)
            except ConversationSourceError as error:
                if error.code != "invalid_ref":
                    raise
                self.service.validate_context_reference(reference, self.document_id)
                if offset:
                    raise ConversationSourceError("invalid_ref")
                return {**self.service.read_context(reference, self.document_id),
                        "next_offset": None}
            return self.service.read_window(reference, self.document_id, offset)

    def validate_saved_window(self, source_reference: str, context_reference: str | None,
                              *, max_chars: int, context_chars: int) -> None:
        with self._owner_errors():
            self.service.validate_saved_window(source_reference, context_reference, self.document_id,
                                               max_chars=max_chars, context_chars=context_chars)

    def require_new_source_after(self, reference: str, previous: str) -> None:
        with self._owner_errors():
            self.service.follows(reference, previous, self.document_id)


def build_extraction_workflow(*, service: ConversationSourceService, document_id: str, store,
                              model: ChatOpenAI, checkpointer: BaseCheckpointSaver,
                              **options) -> ExtractionWorkflow:
    """Assemble B1 for one document: owner adapter, artifacts, provider binding.

    The extraction artifact validates both of its own references, so this reader
    is granted window and context. C repair and the turn read tools keep their
    source-only defaults; publication still takes a window as `processed_source`
    and never a context range.
    """
    reader = ExtractionSourceAdapter(service, document_id)
    artifacts = MemoryArtifacts(store, document_id, source=MemorySourceReader(
        service, document_id, window_references=True, context_references=True))
    structured = model.with_structured_output(
        ExtractionOutput.model_json_schema(), method="json_schema", strict=True, include_raw=True,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    return ExtractionWorkflow(reader, artifacts, structured, accepted, checkpointer, **options)
