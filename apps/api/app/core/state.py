"""Current State：一名員工、一份職務說明書的目前狀態(§9.4 的兩層)。

`JobAnalysisState` 全在記憶體,不碰 DB。交易、CAS、reload、authority snapshot 的
持久化保護是 authority/persistence 層的責任,不是這個 shared kernel 的責任。
"""

from __future__ import annotations

from pydantic import model_validator

from app.core.domain import (
    CurrentJdOpks,
    CurrentWorkModel,
    DomainModel,
    Duty,
    JdHeader,
    JdTask,
    OpksProposal,
    Proposal,
    TaskId,
)


class JobAnalysisState(DomainModel):
    """一名員工、一份職務說明書的目前狀態(§9.4 的兩層)。"""

    jd_header: JdHeader
    current_duties: tuple[Duty, ...]
    work_model: CurrentWorkModel = CurrentWorkModel()
    current_jd: tuple[JdTask, ...] = ()
    proposals: tuple[Proposal, ...] = ()
    current_opks: CurrentJdOpks = CurrentJdOpks()
    opks_proposals: tuple[OpksProposal, ...] = ()

    @model_validator(mode="after")
    def ids_are_unique_and_jd_is_canonical(self):
        duty_ids = [duty.duty_id for duty in self.current_duties]
        if len(set(duty_ids)) != len(duty_ids):
            raise ValueError("duplicate Duty ids")
        expected_duties = sorted(
            self.current_duties, key=lambda duty: (duty.display_order, duty.duty_id)
        )
        if list(self.current_duties) != expected_duties:
            raise ValueError("Duties must be sorted by display order and duty id")
        duty_display_orders = [duty.display_order for duty in self.current_duties]
        if len(set(duty_display_orders)) != len(duty_display_orders):
            raise ValueError("Duty display orders must be unique")
        jd_ids = [entry.task_id for entry in self.current_jd]
        if len(set(jd_ids)) != len(jd_ids):
            raise ValueError("duplicate current JD task ids")
        expected = sorted(
            self.current_jd, key=lambda task: (task.display_order, task.task_id)
        )
        if list(self.current_jd) != expected:
            raise ValueError("current JD must be sorted by display order and task id")
        display_orders = [task.display_order for task in self.current_jd]
        if len(set(display_orders)) != len(display_orders):
            raise ValueError("current JD task display orders must be unique")
        known_duties = set(duty_ids)
        unknown_duties = sorted(
            {
                task.duty_id
                for task in self.current_jd
                if task.duty_id is not None and task.duty_id not in known_duties
            }
        )
        if unknown_duties:
            raise ValueError(f"unknown Duty ids: {unknown_duties}")
        proposal_ids = [proposal.proposal_id for proposal in self.proposals]
        if len(set(proposal_ids)) != len(proposal_ids):
            raise ValueError("duplicate proposal ids")
        self.current_opks.validate_against_tasks(frozenset(jd_ids))
        opks_proposal_ids = [
            proposal.proposal_id for proposal in self.opks_proposals
        ]
        if len(set(opks_proposal_ids)) != len(opks_proposal_ids):
            raise ValueError("duplicate OPKS proposal ids")
        return self

    @property
    def current_jd_task_ids(self) -> frozenset[TaskId]:
        return frozenset(task.task_id for task in self.current_jd)
