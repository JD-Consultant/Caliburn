"""Export one historical interview candidate without exposing source content.

Normal data must export outside the repository and receives known-identifier
redaction.  Owner-confirmed synthetic data may use ``--test-data`` with a
``TEST-`` case id and repository output.  Both paths use a read-only database
transaction, and neither fabricates replay readiness when turn-zero fixtures
are unavailable.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text

from app.adapters.interview_repo import InterviewRepo
from app.database import AsyncSessionLocal, engine
from app.models import DocumentVersion, JobProfile, User
from evals.interview_v4.exporter import export_session_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _outside_repository(path: str | Path, *, test_data: bool = False) -> Path:
    root = Path(path).resolve()
    if not test_data and (root == REPOSITORY_ROOT or REPOSITORY_ROOT in root.parents):
        raise ValueError("candidate exports must stay outside the Git repository")
    return root


def _known_replacements(profile: JobProfile, user: User | None) -> dict[str, str]:
    replacements: dict[str, str] = {}
    values = (
        (getattr(user, "email", None), "[EMAIL_1]"),
        (getattr(user, "name", None), "[PERSON_1]"),
        (getattr(user, "company", None), "[ORGANIZATION_1]"),
        (profile.department, "[DEPARTMENT_1]"),
        (profile.job_title, "[ROLE_TITLE_1]"),
    )
    for source, replacement in values:
        if source and str(source).strip():
            replacements[str(source)] = replacement
    return replacements


async def export_candidate(
    *,
    session_id: UUID,
    case_id: str,
    output_root: str | Path,
    source_hash_salt: str,
    test_data: bool = False,
) -> Path:
    if test_data and not case_id.startswith("TEST-"):
        raise ValueError("repository test-data exports require a TEST- case id")
    root = _outside_repository(output_root, test_data=test_data)
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        repo = InterviewRepo(db)
        session = await repo.get(session_id)
        if session is None:
            raise LookupError("interview session not found")
        profile = await db.get(JobProfile, session.job_profile_id)
        if profile is None:
            raise LookupError("job profile not found")
        user = await db.get(User, profile.user_id)
        observed_document = (await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.job_profile_id == profile.id)
            .order_by(DocumentVersion.version.desc())
            .limit(1)
        )).scalar_one_or_none()

        return await export_session_case(
            repo=repo,
            session_id=session_id,
            initial_document=None,
            initial_state=None,
            reference_snapshot=None,
            observed_document=(observed_document.content or {}) if observed_document else None,
            output_root=root,
            case_id=case_id,
            source_hash_salt=source_hash_salt,
            role_family="pending_manual_taxonomy",
            risk_tags=[
                "guard-alert",
                "long-active-session",
                "mixed-acceptance",
                "missing-initial-fixtures",
            ],
            replacements=None if test_data else _known_replacements(profile, user),
            test_data=test_data,
        )


async def _main(args: argparse.Namespace) -> int:
    salt = os.environ.get(args.salt_env)
    if not salt:
        raise RuntimeError(f"required secret salt environment variable is missing: {args.salt_env}")
    try:
        destination = await export_candidate(
            session_id=UUID(args.session_id),
            case_id=args.case_id,
            output_root=args.output_root,
            source_hash_salt=salt,
            test_data=args.test_data,
        )
        audit = json.loads((destination / "source_audit.json").read_text(encoding="utf-8"))
        print(json.dumps({
            "case_id": args.case_id,
            "destination": str(destination),
            "privacy_status": "synthetic" if args.test_data else "redaction_pending_review",
            "residual_direct_identifier_findings": len(
                audit["residual_direct_identifier_findings"]
            ),
            "fixture_provenance": audit["fixture_provenance"],
            "replay_ready": False,
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--salt-env", default="CALIBURN_EVAL_EXPORT_SALT")
    parser.add_argument("--test-data", action="store_true")
    raise SystemExit(asyncio.run(_main(parser.parse_args())))
