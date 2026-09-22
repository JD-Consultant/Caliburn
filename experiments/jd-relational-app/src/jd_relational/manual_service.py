"""Human App adapter to the same JD domain and durable operation owner.

It resolves exactly the requested historical base, never silently adopts a new
head. Receipt lookup/recovery never rebuild a command or reread its sources.
HTTP waiters do not own writers. No model loop, automatic retry, or catalog copy.
"""

import json
import math
from uuid import UUID, uuid4

from .generated.manual_http import ManualSaveInput, ManualDocumentState, ManualOperationState
from .intents import bind_edit
from .manual_runtime import ManualRuntime, RuntimeFailure
from .observation_projection import project_observation
from .reads import ReadError, command_context
from .references import ReferenceCodec
from .storage.receipts import WriteObservation
from .transport import REQUEST_LIMIT


class ManualError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


_PUBLIC_ERRORS = frozenset({"invalid_input", "invalid_ref", "target_missing", "stale_view",
    "operation_conflict", "busy", "service_unavailable", "selection_not_available"})


def _failure(error):
    code = getattr(error, "code", None)
    if type(code) is not str:
        code = None
    code = {"document_missing": "target_missing", "revision_missing": "target_missing",
            "document_busy": "busy", "writer_not_stopped": "busy"}.get(code, code)
    return ManualError(code if code in _PUBLIC_ERRORS else "service_unavailable")


def _uuid(value):
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError()
        return UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ManualError("invalid_input") from None


def parse_manual_save(value: dict | str) -> dict:
    def unique(pairs):
        found = {}
        for key, item in pairs:
            if key in found:
                raise ValueError()
            found[key] = item
        return found

    def reject_constant(_):
        raise ValueError()

    try:
        raw = value if type(value) is str else json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(raw.encode("utf-8")) > REQUEST_LIMIT:
            raise ValueError()
        parsed = json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)
        result = ManualSaveInput.model_validate(parsed, strict=True).model_dump(mode="json")
        _uuid(result["operation_id"])
        return result
    except Exception:
        raise ManualError("invalid_input") from None


def _no_sources(token, document):
    raise ReadError("invalid_ref")  # The source owner is not connected yet.


def _document_state(value):
    # Pydantic 2.13.5 accepts 0/1 for Literal[False/True] even in strict mode.
    # These four App-produced flags must retain the SSOT's actual JSON booleans;
    # the generated union then validates writable/blocked state combinations.
    if any(type(value[key]) is not bool for key in ("ready", "archived", "write_blocked", "running")):
        raise ManualError("service_unavailable")
    return ManualDocumentState.model_validate(value, strict=True).model_dump(mode="json")


class ManualService:
    def __init__(self, runtime: ManualRuntime, history, codec: ReferenceCodec, *,
                 source_resolver=None, wait_timeout=0.1):
        if (not isinstance(runtime, ManualRuntime) or not isinstance(codec, ReferenceCodec)
                or type(wait_timeout) not in (int, float) or not math.isfinite(wait_timeout)
                or not 0 <= wait_timeout <= 10
                or source_resolver is not None and not callable(source_resolver)):
            raise ValueError("invalid_manual_service")
        self.runtime, self.history, self.codec = runtime, history, codec
        self.source_resolver = source_resolver or _no_sources
        self.wait_timeout = wait_timeout

    # Manual-only commands name a revision. Over HTTP that is always an issued
    # reference, exactly as base_revision_ref is; the command the writer stores
    # carries the identity that reference named.
    _REVISION_ARGUMENTS = {"restore_revision": ("target_revision_ref", "target_revision_id"),
                           "undo_ai_turn": ("expected_result_ref", "expected_result_revision_id")}

    def _resolved_command(self, document_id: str, command: dict) -> dict:
        """Turn the employee's issued revision reference into its identity."""
        names = self._REVISION_ARGUMENTS.get(command.get("tool"))
        if names is None:
            return command
        reference, identity = names
        arguments = dict(command["arguments"])
        resolved = self.codec.resolve(arguments.pop(reference), document_id=document_id,
                                      roles={"revision"}, purposes={"history", "observation"})
        return {**command, "arguments": {**arguments, identity: resolved.revision_id}}

    def save(self, document_id: str, envelope: dict | str) -> dict:
        _uuid(document_id)
        value = parse_manual_save(envelope)
        try:
            base = self.codec.resolve(value["base_revision_ref"], document_id=document_id,
                roles={"revision"}, purposes={"history", "observation"})
            command = self._resolved_command(document_id, value["command"])
            def prepare():
                original = self.history.read_revision(document_id, UUID(base.revision_id))
                context = command_context(original.domain, command, self.codec,
                                          self.source_resolver, lambda: str(uuid4()))
                return bind_edit(UUID(value["operation_id"]), "manual", None, command, context)
            # The source owner reads the same Saver that host.close drains.
            # Materialize preparation under its existing read lifetime token;
            # submit independently checks writer admission after this read.
            intent = self.runtime.inspect_document(document_id, prepare)
            handle = self.runtime.submit(intent)
            try:
                completion = handle.wait(self.wait_timeout)
                observed = completion.observation
            except TimeoutError:
                observed = None  # Waiting ended; the owned writer was not cancelled.
            if observed is None:
                observed = WriteObservation(document_id, intent.operation_id, None, "unknown")
            # A confirmed receipt remains confirmed even when checkpoint cleanup
            # is pending. The separate document state keeps subsequent edits out.
            return project_observation(observed, self.codec)
        except Exception as error:
            raise _failure(error) from None

    def status(self, document_id: str) -> dict:
        _uuid(document_id)
        try:
            current = self.runtime.storage.read_current(document_id)
            status = self.runtime.status(document_id)
            ready = self.runtime.ready
            error = ("service_unavailable" if not ready or status.error in {
                "checkpoint_unavailable", "checkpoint_conflict"} else
                "busy" if status.running or status.error == "document_busy" else
                "recovery_required" if status.write_blocked else None)
            result = {"ready": ready, "archived": current.archived,
                "write_blocked": not ready or current.archived or status.write_blocked,
                "running": status.running,
                "operation_id": str(status.identity.operation_id) if status.identity else None,
                "error": error}
            return _document_state(result)
        except Exception as error:
            raise _failure(error) from None

    def lookup(self, document_id: str, operation_id: str) -> dict:
        _uuid(document_id)
        operation = _uuid(operation_id)
        try:
            # Query gate first, then the durable receipt. This is an observation
            # for the UI, not a permit to write or proof that a delayed request
            # cannot still arrive. Every actual submit rechecks its own owner.
            state = _document_state(self.status(document_id))
            receipt = self.runtime.storage.get_operation(document_id, operation)
            if receipt is not None:
                observed = WriteObservation(document_id, operation, receipt)
                result, presence = project_observation(observed, self.codec), "observed"
            elif state["operation_id"] == operation_id:
                result = project_observation(WriteObservation(document_id, operation, None, "unknown"), self.codec)
                presence = "pending"
            else:
                result, presence = None, "not_found"
            view = {"operation_id": operation_id, "presence": presence, "result": result, "write_state": state}
            return ManualOperationState.model_validate(view, strict=True).model_dump(mode="json")
        except Exception as error:
            raise _failure(error) from None

    def recover(self, document_id: str, operation_id: str) -> dict:
        _uuid(document_id)
        operation = _uuid(operation_id)
        try:
            # The comparison occurs again inside the runtime's slot lock, not
            # merely in a preceding status request that can be out of date.
            self.runtime.recover(document_id, expected_operation_id=operation, timeout=self.wait_timeout)
        except TimeoutError:
            pass  # A single managed recovery remains in progress.
        except RuntimeFailure as error:
            if error.code != "writer_not_stopped":
                raise _failure(error) from None
        except Exception as error:
            raise _failure(error) from None
        return self.lookup(document_id, operation_id)
