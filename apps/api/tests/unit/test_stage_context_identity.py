"""Persisted stage identity syntax stays separate from each consumer's eligibility rules."""

from uuid import UUID

import pytest

from caliburn.diagnostics.projection import role_for_thread
from caliburn.features.executions.history import _belongs_to_completed_role
from caliburn.features.executions.history_models import (
    AgentRole,
    HistoryWindowKind,
    StageContextIdentity,
    context_thread_id,
    parse_stage_thread_id,
    stage_thread_id,
)
from caliburn.features.executions.models import ExecutionKind, ExecutionScope

FILE_ID = UUID("10000000-0000-4000-8000-000000000001")
EXECUTION_ID = UUID("20000000-0000-4000-8000-000000000002")
GENERATION_ID = UUID("abcdef00-0000-4000-8000-000000000003")
STAGE_ID = UUID("fedcba00-0000-4000-8000-000000000004")
SCOPE = ExecutionScope(FILE_ID, EXECUTION_ID, ExecutionKind.MEMORY_BATCH)
PREFIX = f"{FILE_ID}:{EXECUTION_ID}:"
ROOT = PREFIX + "work_situation_analyst:completed_work"
SAVED_THREAD = (
    ROOT + ":stage:abcdef00-0000-4000-8000-000000000003:fedcba00-0000-4000-8000-000000000004"
)


def test_existing_native_stage_spelling_is_unchanged():
    assert stage_thread_id(ROOT, GENERATION_ID, STAGE_ID) == SAVED_THREAD
    assert parse_stage_thread_id(SAVED_THREAD) == StageContextIdentity(
        ROOT, GENERATION_ID, STAGE_ID
    )
    assert _belongs_to_completed_role(SCOPE, AgentRole.WORK_SITUATION_ANALYST, SAVED_THREAD)
    assert role_for_thread(SAVED_THREAD, PREFIX) == "work_situation_analyst"


@pytest.mark.parametrize(
    "thread",
    [
        ROOT,
        ROOT + ":stage:",
        ROOT + ":stage:bad:bad",
        SAVED_THREAD + ":context",
        SAVED_THREAD + ":compact:request",
        SAVED_THREAD + ":stage:" + str(GENERATION_ID),
    ],
)
def test_non_stage_and_malformed_suffixes_are_not_stage_identities(thread):
    assert parse_stage_thread_id(thread) is None


def test_history_requires_exact_owner_and_canonical_stage_but_diagnostics_only_identifies_role():
    role = AgentRole.WORK_SITUATION_ANALYST
    assert not _belongs_to_completed_role(SCOPE, AgentRole.WORK_UNDERSTANDING_ANALYST, SAVED_THREAD)
    other_scope = ExecutionScope(FILE_ID, STAGE_ID, ExecutionKind.MEMORY_BATCH)
    assert not _belongs_to_completed_role(other_scope, role, SAVED_THREAD)
    consultant_scope = ExecutionScope(FILE_ID, EXECUTION_ID, ExecutionKind.CONSULTANT_TURN)
    assert not _belongs_to_completed_role(consultant_scope, role, SAVED_THREAD)
    assert _belongs_to_completed_role(SCOPE, role, ROOT)
    assert not _belongs_to_completed_role(
        SCOPE, role, context_thread_id(SCOPE, role, HistoryWindowKind.PREPARED_HISTORY)
    )
    noncanonical = SAVED_THREAD.replace(str(GENERATION_ID), str(GENERATION_ID).upper())
    assert parse_stage_thread_id(noncanonical) == parse_stage_thread_id(SAVED_THREAD)
    assert not _belongs_to_completed_role(SCOPE, role, noncanonical)
    assert role_for_thread(noncanonical, PREFIX) == role.value
    assert role_for_thread(SAVED_THREAD, f"{STAGE_ID}:{EXECUTION_ID}:") is None
    assert role_for_thread(SAVED_THREAD + ":context", PREFIX) is None


@pytest.mark.parametrize("role", list(AgentRole))
def test_diagnostics_role_selection_keeps_root_and_stage_windows(role):
    root = context_thread_id(SCOPE, role, HistoryWindowKind.COMPLETED_WORK)
    assert role_for_thread(root, PREFIX) == role.value
    assert role_for_thread(stage_thread_id(root, GENERATION_ID, STAGE_ID), PREFIX) == role.value
    assert role_for_thread(root.replace("completed_work", "prepared_history"), PREFIX) is None
