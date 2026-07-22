"""Deterministic UUIDv5 identities for frames, receipts and materialized evidence.

Every identity a turn interpretation writes is derived, never random, so that a
crashed executor replays to byte-identical state and the eval harness can pin
exact UUID vectors (plan §7.4).

Indices are the model's *original* 1-based positions. Deriving before any
deterministic drop and never renumbering afterwards is what keeps a dropped
proposal from silently shifting its neighbours' identities.

This module is the single authority: reducers, verifier and eval fixtures all
call these functions rather than re-deriving the same formula locally (plan §6).
"""

from __future__ import annotations

from uuid import UUID, uuid5

_MIN_INDEX = 1
_MAX_INDEX = 9999


def _checked_index(value: int, label: str) -> int:
    if not _MIN_INDEX <= value <= _MAX_INDEX:
        raise ValueError(f"{label} must be between {_MIN_INDEX} and {_MAX_INDEX}")
    return value


def derive_proposal_ref(observation_index: int) -> str:
    """Stable label for a literal observation at its original output position.

    Derived from the model's 1-based position *before* any deterministic drop and
    never renumbered, so a dropped proposal cannot shift its neighbours' refs
    (amendment plan §10.1).
    """

    index = _checked_index(observation_index, "observation_index")
    return f"p{index:04d}"


def derive_binding_ref(binding_index: int) -> str:
    """Stable label for an answer binding at its original output position."""

    index = _checked_index(binding_index, "binding_index")
    return f"b{index:04d}"


def question_frame_id(consultant_turn_id: UUID) -> UUID:
    """The frame a consultant question opens."""

    return uuid5(consultant_turn_id, "question-frame")


def turn_interpretation_id(operation_id: UUID) -> UUID:
    """The receipt an interpretation operation leaves behind."""

    return uuid5(operation_id, "turn-interpretation")


def literal_evidence_id(operation_id: UUID, observation_index: int) -> UUID:
    """Evidence materialized from a literal observation at its original position."""

    index = _checked_index(observation_index, "observation_index")
    return uuid5(operation_id, f"literal/{index:04d}")


def contextual_evidence_id(
    operation_id: UUID,
    binding_index: int,
    materialization_index: int,
) -> UUID:
    """Evidence materialized from an answer binding.

    A choice binding materializes one evidence per selected option; those are
    numbered by option ordinal so the identity does not depend on the order the
    model happened to list them in.
    """

    binding = _checked_index(binding_index, "binding_index")
    materialization = _checked_index(materialization_index, "materialization_index")
    return uuid5(operation_id, f"binding/{binding:04d}/materialization/{materialization:04d}")
