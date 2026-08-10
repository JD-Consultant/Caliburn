"""OPKS first slice 的真 PostgreSQL scripted vertical。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.documents import load_document
from app.core.domain import OpksEntityKind, OpksProposalStatus
from scripts.job_analysis_opks_smoke import run_scripted_opks_smoke


pytestmark = pytest.mark.asyncio


async def test_scripted_opks_vertical_is_durable_idempotent_and_readable(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    isolation_document_id = uuid4()
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(  # noqa: E731
        postgres_session_factory
    )

    try:
        report = await run_scripted_opks_smoke(
            uow_factory=uow_factory,
            document_id=document_id,
            isolation_document_id=isolation_document_id,
        )
        loaded = await load_document(uow_factory, document_id)
        isolated = await load_document(uow_factory, isolation_document_id)

        assert loaded is not None
        assert isolated is not None
        assert report.provider_calls == 3
        assert tuple(item.provider_calls for item in report.scenarios) == (
            1,
            1,
            1,
            1,
            2,
            3,
            3,
        )
        assert report.scenario_names == (
            "generate_proposals",
            "idempotent_replay",
            "employee_decisions",
            "manual_attitude",
            "reuse_knowledge",
            "task_delete",
            "ungrounded_stop",
        )
        assert report.generation_replay_equal
        assert report.decision_statuses == (
            OpksProposalStatus.ACCEPTED,
            OpksProposalStatus.EDITED,
            OpksProposalStatus.REJECTED,
            OpksProposalStatus.DEFERRED,
        )
        assert report.reused_entity_id == "direct-manual-knowledge-knowledge"
        assert report.reused_task_refs == ("task-1", "task-2")
        assert report.isolation_unchanged
        assert report.ungrounded_state_unchanged

        current_by_kind = {
            kind: tuple(
                item
                for item in loaded.state.current_opks.items
                if item.entity_kind is kind
            )
            for kind in OpksEntityKind
        }
        assert current_by_kind[OpksEntityKind.OUTPUT] == ()
        assert current_by_kind[OpksEntityKind.INDICATOR] == ()
        assert len(current_by_kind[OpksEntityKind.KNOWLEDGE]) == 1
        assert current_by_kind[OpksEntityKind.KNOWLEDGE][0].task_refs == (
            "task-2",
        )
        assert current_by_kind[OpksEntityKind.ATTITUDE] == ()
        assert any(
            proposal.status is OpksProposalStatus.STALE
            and proposal.proposal_id == "opks-pending-op0"
            for proposal in loaded.state.opks_proposals
        )

        summary = report.render()
        assert "7/7 scripted scenarios passed" in summary
        assert "provider calls: 3" in summary
        assert "reuse_knowledge" in summary
        assert "same entity, 2 Task refs" in summary
        assert "no model-quality claim" in summary
        print("\n" + summary)
    finally:
        async with postgres_session_factory() as session:
            await session.execute(
                text(
                    "DELETE FROM job_analysis_documents "
                    "WHERE document_id = :document_id"
                ),
                {"document_id": str(isolation_document_id)},
            )
            await session.commit()
