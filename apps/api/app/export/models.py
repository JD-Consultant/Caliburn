"""Renderer-neutral export projection owned by the current consultant runtime."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ExportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExportHeader(ExportModel):
    competency_name: str | None = None
    occupation_category_name: str | None = None
    occupation_name: str | None = None
    # These cells are assigned by iCAP, never inferred from employee reference codes.
    occupation_code: None = None
    industry_name: str | None = None
    industry_code: None = None
    work_description: str | None = None
    competency_level: int | None = None
    notes: str | None = None


class ExportOpksEntry(ExportModel):
    position_code: str | None
    text: str


class ExportTaskEntry(ExportModel):
    task_id: str
    position_code: str | None
    statement: str
    competency_level: int | None
    outputs: tuple[ExportOpksEntry, ...] = ()
    indicators: tuple[ExportOpksEntry, ...] = ()
    knowledge: tuple[ExportOpksEntry, ...] = ()
    skills: tuple[ExportOpksEntry, ...] = ()


class ExportDutySection(ExportModel):
    position_code: str
    statement: str
    tasks: tuple[ExportTaskEntry, ...] = ()


class ExportDocument(ExportModel):
    title: str
    header: ExportHeader
    duties: tuple[ExportDutySection, ...] = ()
    unassigned_tasks: tuple[ExportTaskEntry, ...] = ()
    attitudes: tuple[ExportOpksEntry, ...] = ()


__all__ = [
    "ExportDocument",
    "ExportDutySection",
    "ExportHeader",
    "ExportOpksEntry",
    "ExportTaskEntry",
]
