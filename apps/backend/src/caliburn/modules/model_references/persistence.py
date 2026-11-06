"""以 PostgreSQL 唯一約束配置持久短碼，每次公開呼叫各自提交短交易。"""

import re
from collections.abc import Callable, Collection
from typing import get_args
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from caliburn.modules.model_references.contracts import (
    InvalidModelReferenceError,
    ModelReferenceAllocationError,
    ReferenceTarget,
    ResourceKind,
    UnknownModelReferenceError,
)
from caliburn.modules.model_references.orm_models import ModelReferenceRow

_REFERENCE = re.compile(
    rf"(?:{'|'.join(get_args(ResourceKind.__value__))})_([1-9][0-9]{{0,18}})"
)


class SqlAlchemyModelReferences:
    def __init__(self, sessions: Callable[[], Session]) -> None:
        self._sessions = sessions

    def get_or_create_refs(
        self, workspace_id: UUID, targets: Collection[ReferenceTarget]
    ) -> dict[ReferenceTarget, str]:
        unique = sorted(
            set(targets), key=lambda target: (target.resource_kind, target.resource_id)
        )
        if not unique:
            return {}
        with self._sessions() as session, session.begin():
            session.execute(
                insert(ModelReferenceRow)
                .values(
                    [
                        {
                            "workspace_id": workspace_id,
                            "resource_kind": target.resource_kind,
                            "resource_id": target.resource_id,
                        }
                        for target in unique
                    ]
                )
                .on_conflict_do_nothing(constraint="uq_model_references_target")
            )
            # READ COMMITTED 的新 SELECT 能看見剛才等待的並行提交者。
            rows = session.scalars(
                select(ModelReferenceRow).where(
                    ModelReferenceRow.workspace_id == workspace_id,
                    tuple_(
                        ModelReferenceRow.resource_kind, ModelReferenceRow.resource_id
                    ).in_(
                        [
                            (target.resource_kind, target.resource_id)
                            for target in unique
                        ]
                    ),
                )
            )
            result = {
                ReferenceTarget(
                    row.resource_kind, row.resource_id
                ): f"{row.resource_kind}_{row.reference_number}"
                for row in rows
            }
            if len(result) != len(unique):
                raise ModelReferenceAllocationError(
                    "Model reference allocation could not return the complete batch."
                )
        return result

    def resolve_refs(
        self, workspace_id: UUID, refs: Collection[str]
    ) -> dict[str, ReferenceTarget]:
        numbers = []
        for reference in refs:
            match = _REFERENCE.fullmatch(reference)
            if match is None or int(match[1]) > 2**63 - 1:
                raise InvalidModelReferenceError(
                    reference, "Use a model reference supplied in this Workspace."
                )
            numbers.append(int(match[1]))
        if not numbers:
            return {}
        with self._sessions() as session:
            rows = session.scalars(
                select(ModelReferenceRow).where(
                    ModelReferenceRow.workspace_id == workspace_id,
                    ModelReferenceRow.reference_number.in_(numbers),
                )
            )
            resolved = {
                f"{row.resource_kind}_{row.reference_number}": ReferenceTarget(
                    row.resource_kind, row.resource_id
                )
                for row in rows
            }
        for reference in refs:
            if reference not in resolved:
                raise UnknownModelReferenceError(
                    reference, "No matching model reference in this Workspace."
                )
        return resolved
