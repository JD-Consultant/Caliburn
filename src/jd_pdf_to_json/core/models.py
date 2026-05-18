"""Data models for OCS documents."""

from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class VersionEntry(BaseModel):
    """Single version entry in version history."""
    version: str
    ocs_code: str
    ocs_name: str
    status: str
    update_note: Optional[str] = Field(None)
    update_date: str = Field(..., description="Date in YYYY/MM/DD format")


class VersionInfo(BaseModel):
    """Version information block."""
    versions: List[VersionEntry] = Field(default_factory=list)


class OCSName(BaseModel):
    """OCS name with category and occupation."""
    job_category_name: Optional[str] = None
    occupation_name: Optional[str] = None


class CategoryItem(BaseModel):
    """Single category item with code."""
    name: str
    code: str


class OCSCategory(BaseModel):
    """OCS category information."""
    job_categories: List[CategoryItem] = Field(default_factory=list)
    occupations: List[CategoryItem] = Field(default_factory=list)
    industries: List[CategoryItem] = Field(default_factory=list)


class OCSProfile(BaseModel):
    """OCS profile section."""
    ocs_code: str
    ocs_name: OCSName
    category: OCSCategory
    job_description: str
    ocs_level: int = Field(..., ge=1, le=5)


class CompetencyItem(BaseModel):
    """Knowledge or skill item."""
    code: str
    name: str


class OutputItem(BaseModel):
    """Work output item."""
    code: str
    name: str


class BehavioralIndicator(BaseModel):
    """Behavioral indicator (P-code)."""
    code: str
    text: str


class CompetencyBlock(BaseModel):
    """Competency block under a task, anchored by one or more P-codes."""
    competency_level: int = Field(..., ge=1, le=5)
    indicators: List[BehavioralIndicator] = Field(default_factory=list)
    outputs: List[OutputItem] = Field(default_factory=list)
    knowledge: List[CompetencyItem] = Field(default_factory=list)
    skills: List[CompetencyItem] = Field(default_factory=list)


class TaskCodeEntry(BaseModel):
    """Single task code and its name within a task group."""
    code: str
    name: str


class Task(BaseModel):
    """Work task group — one or more T-codes sharing the same competency blocks."""
    task_codes: List[TaskCodeEntry] = Field(default_factory=list)
    competency_blocks: List[CompetencyBlock] = Field(default_factory=list)


class OCSUnit(BaseModel):
    """OCU (Occupational Competency Unit)."""
    ocu_code: str
    ocu_name: str
    tasks: List[Task] = Field(default_factory=list)


class OCSContent(BaseModel):
    """OCS content section."""
    ocu_units: List[OCSUnit] = Field(default_factory=list)


class Attitude(BaseModel):
    """Attitude competency."""
    code: str
    name: str


class OCSAttitude(BaseModel):
    """OCS attitude section."""
    attitudes: List[Attitude] = Field(default_factory=list)


class Notes(BaseModel):
    """Notes and supplementary information."""
    prerequisites: List[str] = Field(default_factory=list)
    supplements: List[str] = Field(default_factory=list)


class OCSDocument(BaseModel):
    """Complete OCS document model."""
    version_info: VersionInfo = Field(default_factory=VersionInfo)
    ocs_profile: OCSProfile
    ocs_content: OCSContent = Field(default_factory=OCSContent)
    ocs_attitude: OCSAttitude = Field(default_factory=OCSAttitude)
    notes: Notes = Field(default_factory=Notes)
