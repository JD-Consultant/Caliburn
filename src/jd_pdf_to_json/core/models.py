"""Data models for OCS documents."""

from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class VersionEntry(BaseModel):
    """Single version entry in version history."""
    version: str
    ocs_code: str
    ocs_name: str
    status: str
    update_note: Optional[str] = Field(None, description="Update notes, 'skip' if empty")
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
    output_code: str
    output_name: str


class BehavioralIndicator(BaseModel):
    """Behavioral indicator."""
    indicator_code: str
    indicator_text: str


class CompetencyBlock(BaseModel):
    """P-centered competency block under a task."""
    competency_level: int = Field(..., ge=1, le=5)
    indicators: List[BehavioralIndicator] = Field(default_factory=list)
    outputs: List[OutputItem] = Field(default_factory=list)
    knowledge_k: List[CompetencyItem] = Field(default_factory=list)
    skills_s: List[CompetencyItem] = Field(default_factory=list)


class Task(BaseModel):
    """Work task."""
    model_config = ConfigDict(populate_by_name=True)

    task_code: str
    task_name: str
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
    attitude_code: str
    attitude_name: str
    attitude_description: Optional[str] = None


class OCSAttitude(BaseModel):
    """OCS attitude section."""
    attitudes: List[Attitude] = Field(default_factory=list)


class Requirement(BaseModel):
    """Single requirement in notes."""
    category: str
    content: str
    notes: Optional[str] = None


class NotesAndAppendix(BaseModel):
    """Notes and supplementary information."""
    requirements: List[Requirement] = Field(default_factory=list)


class OCSDocument(BaseModel):
    """Complete OCS document model."""
    version_info: VersionInfo = Field(default_factory=VersionInfo)
    ocs_profile: OCSProfile
    ocs_content: OCSContent = Field(default_factory=OCSContent)
    ocs_attitude: OCSAttitude = Field(default_factory=OCSAttitude)
    notes_and_appendix: NotesAndAppendix = Field(default_factory=NotesAndAppendix)

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "version_info": {"versions": []},
                "ocs_profile": {},
                "ocs_content": {"ocu_units": []},
                "ocs_attitude": {"attitudes": []},
                "notes_and_appendix": {"requirements": []},
            }
        }


# Removed backward-compatible alias `TaskGroup` to enforce P-centric model.
