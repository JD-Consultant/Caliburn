"""Pydantic models for raw OCS JSON files produced by jd-pdf-to-json.

Tolerant parsing: missing arrays default to []; unknown keys are ignored.
Validation is not strict — we want to load all 908 files even when upstream
schema drift introduces extra fields.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class CodeName(_Base):
    code: str | None = None
    name: str | None = None


class CodeText(_Base):
    code: str | None = None
    text: str | None = None


class VersionEntry(_Base):
    version: str | None = None
    ocs_code: str | None = None
    ocs_name: str | None = None
    status: str | None = None
    update_note: str | None = None
    update_date: str | None = None


class VersionInfo(_Base):
    versions: list[VersionEntry] = Field(default_factory=list)


class OcsName(_Base):
    job_category_name: str | None = None
    occupation_name: str | None = None


class Category(_Base):
    job_categories: list[CodeName] = Field(default_factory=list)
    occupations: list[CodeName] = Field(default_factory=list)
    industries: list[CodeName] = Field(default_factory=list)


class OcsProfile(_Base):
    ocs_code: str
    ocs_name: OcsName | None = None
    category: Category | None = None
    job_description: str | None = None
    ocs_level: int | None = None


class CompetencyBlock(_Base):
    competency_level: int | None = None
    indicators: list[CodeText] = Field(default_factory=list)
    outputs: list[CodeName] = Field(default_factory=list)
    knowledge: list[CodeName] = Field(default_factory=list)
    skills: list[CodeName] = Field(default_factory=list)


class TaskGroup(_Base):
    task_codes: list[CodeName] = Field(default_factory=list)
    competency_blocks: list[CompetencyBlock] = Field(default_factory=list)


class OcuUnit(_Base):
    ocu_code: str | None = None
    ocu_name: str | None = None
    tasks: list[TaskGroup] = Field(default_factory=list)


class OcsContent(_Base):
    ocu_units: list[OcuUnit] = Field(default_factory=list)


class Attitude(_Base):
    code: str | None = None
    name: str | None = None


class OcsAttitude(_Base):
    attitudes: list[Attitude] = Field(default_factory=list)


class Notes(_Base):
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)


class OCSDocument(_Base):
    """Top-level OCS JSON document."""

    version_info: VersionInfo = Field(default_factory=VersionInfo)
    ocs_profile: OcsProfile
    ocs_content: OcsContent = Field(default_factory=OcsContent)
    ocs_attitude: OcsAttitude = Field(default_factory=OcsAttitude)
    notes: Notes = Field(default_factory=Notes)

    raw: dict[str, Any] | None = None
