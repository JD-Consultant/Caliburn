"""Append-only persistence for explicitly consented interview eval captures."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from app.interview.eval_capture import EvalSessionStart, canonical_hash
from app.models import InterviewEvalArtifact, InterviewEvalCapture


class EvalCaptureRepo:
    def __init__(self, session):
        self.session = session

    async def get_for_session(self, session_id) -> InterviewEvalCapture | None:
        stmt = select(InterviewEvalCapture).where(
            InterviewEvalCapture.session_id == session_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create_start(
        self,
        *,
        session_id,
        contract: EvalSessionStart,
        initial_document: dict[str, Any],
        initial_state: dict[str, Any],
        reference_snapshot: dict[str, Any],
    ) -> InterviewEvalCapture:
        if await self.get_for_session(session_id) is not None:
            raise ValueError("eval capture already exists for session")
        expected = {
            "initial_document": contract.initial_document_hash,
            "initial_state": contract.initial_state_hash,
            "reference_snapshot": contract.reference_snapshot_hash,
        }
        artifacts = {
            "initial_document": initial_document,
            "initial_state": initial_state,
            "reference_snapshot": reference_snapshot,
        }
        for kind, content in artifacts.items():
            if canonical_hash(content) != expected[kind]:
                raise ValueError(f"{kind} content hash does not match contract")

        row = InterviewEvalCapture(
            session_id=session_id,
            schema_version=contract.schema_version,
            consent_policy_version=contract.consent_policy_version,
            locale=contract.locale,
            initial_document_hash=contract.initial_document_hash,
            initial_state_hash=contract.initial_state_hash,
            reference_snapshot_hash=contract.reference_snapshot_hash,
            prompt_bundle_hash=contract.prompt_bundle_hash,
            tool_schema_hash=contract.tool_schema_hash,
            code_git_sha=contract.code_git_sha,
            dirty_worktree=contract.dirty_worktree,
            limitations=list(contract.limitations),
        )
        self.session.add(row)
        await self.session.flush()
        for kind, content in artifacts.items():
            self.session.add(InterviewEvalArtifact(
                capture_id=row.id,
                kind=kind,
                sequence=0,
                content=content,
                content_hash=expected[kind],
            ))
        await self.session.flush()
        return row

    async def append_artifact(
        self,
        *,
        capture_id,
        kind: str,
        sequence: int,
        content: dict[str, Any] | list[Any],
    ) -> InterviewEvalArtifact:
        if not kind or sequence < 0:
            raise ValueError("artifact kind is required and sequence must be non-negative")
        row = InterviewEvalArtifact(
            capture_id=capture_id,
            kind=kind,
            sequence=sequence,
            content=content,
            content_hash=canonical_hash(content),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_artifacts(self, capture_id) -> list[InterviewEvalArtifact]:
        stmt = (
            select(InterviewEvalArtifact)
            .where(InterviewEvalArtifact.capture_id == capture_id)
            .order_by(InterviewEvalArtifact.kind, InterviewEvalArtifact.sequence)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def mark_completed(self, capture_id) -> InterviewEvalCapture:
        """Advance capture lifecycle once; immutable artifact rows stay untouched."""
        stmt = (
            update(InterviewEvalCapture)
            .where(
                InterviewEvalCapture.id == capture_id,
                InterviewEvalCapture.status == "capturing",
            )
            .values(status="completed")
            .returning(InterviewEvalCapture)
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is not None:
            await self.session.flush()
            return row
        existing = await self.session.get(InterviewEvalCapture, capture_id)
        if existing is None:
            raise LookupError("eval capture not found")
        if existing.status != "completed":
            raise ValueError(f"invalid eval capture status: {existing.status}")
        return existing
