"""Shared preparation boundary. Diagnostics are never durable operation receipts."""

import logging
from time import perf_counter
from uuid import UUID, uuid4

from .domain import CommandContext, DomainError, build_candidate, validate_content
from .snapshots import domain_from_snapshot


LOG = logging.getLogger("caliburn.jd.commands")
# Diagnostic allowlists deliberately fail closed; they do not validate commands.
_COMMAND_LABELS = frozenset({"jd_create_task", "jd_revise_work", "jd_set_text", "jd_insert_item",
    "jd_delete_item", "jd_move_item", "jd_set_task_capability", "jd_replace_selection",
    "restore_revision", "undo_ai_turn"})
_ERROR_LABELS = frozenset({"invalid_input", "target_missing", "stale_view", "relationship_conflict", "dependent_items"})


def prepare_edit(snapshot: dict, command: dict, context: CommandContext, *, request_id: UUID | None = None) -> dict:
    """Build exactly one candidate; preserve errors and perform no retry or save.

    Transport owns shape validation before this call. The host owns handlers,
    retention and export of logs. Only allowlisted diagnostic metadata is logged;
    no arguments, raw exceptions, source refs, JD text or model messages.
    """
    if request_id is not None and not isinstance(request_id, UUID):
        raise TypeError("request_id must be an App-provided UUID")
    started = perf_counter()
    name = command.get("tool")
    label = name if isinstance(name, str) and name in _COMMAND_LABELS else "unrecognized"
    metadata = {"event_name": "jd.command.prepare", "request_id": str(request_id or uuid4()),
                "document_id": context.document_id, "command_kind": label}

    def record(level: int, outcome: str, error_code: str | None):
        try:
            LOG.log(level, "JD command preparation", extra={**metadata, "outcome": outcome,
                "error_code": error_code, "duration_ms": round((perf_counter() - started) * 1000, 3)})
        except Exception:
            # Diagnostic sink failure cannot replace a candidate or domain error.
            # Do not retry or recursively report through the same broken handler.
            pass

    try:
        candidate = build_candidate(snapshot, command, context)
    except DomainError as error:
        code = error.code if error.code in _ERROR_LABELS else "unrecognized_error"
        record(logging.INFO, "rejected", code)
        raise
    except Exception:
        # Exception strings/chains can contain user content or driver parameters.
        record(logging.ERROR, "failed", "internal_error")
        raise
    record(logging.INFO, "prepared", None)
    return candidate


def prepare_restore(current: dict, stored: dict) -> dict:
    """Build the candidate that puts this document back to one of its revisions.

    The content is historical; the rules are today's, so a revision that no
    longer satisfies them is refused whole rather than partly applied. Stable
    identities come back as themselves and recorded source links come back as
    recorded: this restores existing basis, it does not re-approve it against
    newer interviews. Nothing here saves, retries or decides eligibility.
    """
    restored = domain_from_snapshot(stored, current["revision"])
    validate_content(restored, current["document_id"])
    return restored
