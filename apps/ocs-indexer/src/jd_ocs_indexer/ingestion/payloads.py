"""Typed Qdrant payload contract (schema v4).

Single source of truth for the *stored* payload shape. The builder constructs
these models and `.model_dump()`s them — no hand-rolled dicts. Versioned via
`schema_version` so consumers can assert the schema and CI catches drift
(data-contract discipline).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

SCHEMA_VERSION = "v4"


class CodeName(BaseModel):
    code: str
    name: str


class OcsName(BaseModel):
    """OCS 名稱（擇一；job_category_name 幾乎都 null，occupation_name 為主）。"""

    job_category_name: str | None = None
    occupation_name: str | None = None


class ProfilePayload(BaseModel):
    chunk_level: str = "profile"
    schema_version: str = SCHEMA_VERSION
    ocs_code: str
    ocs_code_base: str
    is_current: bool
    ocs_name: OcsName
    job_description: str | None = None
    ocs_level: int | None = None
    job_categories: list[CodeName] = Field(default_factory=list)
    occupations: list[CodeName] = Field(default_factory=list)
    industries: list[CodeName] = Field(default_factory=list)
    attitudes: list[CodeName] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
    indexed_at: str
    source_file: str


class Indicator(BaseModel):
    code: str
    text: str


class CompetencyBlock(BaseModel):
    """一個能力切片（由 K/S 新值分界，契約 §6.3.2）；多 level 任務 → 多個。"""

    competency_level: int | None = None
    indicators: list[Indicator] = Field(default_factory=list)  # P，每 block 必 ≥1
    outputs: list[CodeName] = Field(default_factory=list)      # O，可空
    knowledge: list[CodeName] = Field(default_factory=list)
    skills: list[CodeName] = Field(default_factory=list)


class TaskPayload(BaseModel):
    chunk_level: str = "task"
    schema_version: str = SCHEMA_VERSION
    ocs_code: str
    ocs_name: str            # 解析後顯示名（denormalized，免 by-id join）
    ocu_code: str | None = None
    ocu_name: str | None = None
    task_code: str
    task_name: str
    competency_blocks: list[CompetencyBlock] = Field(default_factory=list)
    source_file: str
