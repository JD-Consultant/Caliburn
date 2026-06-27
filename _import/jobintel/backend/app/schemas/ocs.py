"""OCS (Occupational Competency Standard) Pydantic models — mirrors iCAP JSON schema."""
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Evidence reference ─────────────────────────────────────────────────────────

class EvidenceRef(BaseModel):
    source_type: str              # interview_quote | star_slot | five_w2h_field | icap_reference | manual_edit
    evidence_kind: str = "direct" # direct | structured | inferred
    quote: Optional[str] = None   # for interview_quote
    field: Optional[str] = None   # for star_slot (S/T/A/R) or five_w2h_field name
    value: Any = None             # str or list[str] depending on field
    icap_code: Optional[str] = None  # for icap_reference


# ── Version info ───────────────────────────────────────────────────────────────

class OcsVersion(BaseModel):
    status: str = "最新版本"
    ocs_code: str


class OcsVersionInfo(BaseModel):
    versions: list[OcsVersion] = []


# ── Profile ────────────────────────────────────────────────────────────────────

class OcsName(BaseModel):
    occupation_name: str = ""


class OcsCategory(BaseModel):
    occ_code: Optional[str] = None          # 職業代碼，優先取 occupations[0].code
    occupations: list[dict] = Field(default_factory=list)
    job_categories: list[dict] = Field(default_factory=list)
    industries: list[dict] = Field(default_factory=list)


class OcsProfile(BaseModel):
    ocs_code: str
    ocs_name: OcsName
    job_description: str = ""
    ocs_level: int = 3
    notes: Optional[str] = None            # 學歷/年資等補充說明（from iCAP notes_and_appendix）
    occ_code: Optional[str] = None         # 職業代碼（冗餘欄位，方便 XLSX row 4 直接取用）
    category: OcsCategory = Field(default_factory=OcsCategory)


# ── Competency blocks ──────────────────────────────────────────────────────────

class OcsIndicator(BaseModel):
    code: str
    text: str
    quality_score: Optional[float] = None   # 0.0–1.0，LLM 7 維度評分
    quality_status: Optional[str] = None    # ok | force_accepted
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    display_label: Optional[str] = None
    display_labels: list[str] = Field(default_factory=list)


class OcsOutput(BaseModel):
    code: str
    name: str
    quality_score: Optional[float] = None
    quality_status: Optional[str] = None
    display_label: Optional[str] = None
    display_labels: list[str] = Field(default_factory=list)


class OcsKnowledge(BaseModel):
    code: str
    name: str
    source_type: str = "company_defined"   # icap_official | company_defined
    icap_ref: Optional[str] = None
    display_label: Optional[str] = None
    display_labels: list[str] = Field(default_factory=list)


class OcsSkill(BaseModel):
    code: str
    name: str
    source_type: str = "company_defined"
    icap_ref: Optional[str] = None
    display_label: Optional[str] = None
    display_labels: list[str] = Field(default_factory=list)


class OcsCompetencyBlock(BaseModel):
    competency_level: int = 3
    indicators: list[OcsIndicator] = Field(default_factory=list)
    outputs: list[OcsOutput] = Field(default_factory=list)
    knowledge: list[OcsKnowledge] = Field(default_factory=list)
    skills: list[OcsSkill] = Field(default_factory=list)


# ── Tasks & units ──────────────────────────────────────────────────────────────

class OcsTaskCode(BaseModel):
    code: str
    name: str


class OcsTask(BaseModel):
    task_codes: list[OcsTaskCode] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    display_label: Optional[str] = None
    display_labels: list[str] = Field(default_factory=list)
    competency_blocks: list[OcsCompetencyBlock] = Field(default_factory=list)


class OcsUnit(BaseModel):
    ocu_code: str
    ocu_name: str
    tasks: list[OcsTask] = Field(default_factory=list)


class OcsContent(BaseModel):
    ocu_units: list[OcsUnit] = Field(default_factory=list)


# ── Attitude ───────────────────────────────────────────────────────────────────

class OcsAttitude(BaseModel):
    code: str
    name: str
    source_type: str = "company_defined"
    icap_ref: Optional[str] = None
    display_label: Optional[str] = None
    display_labels: list[str] = Field(default_factory=list)


class OcsAttitudeSection(BaseModel):
    attitudes: list[OcsAttitude] = Field(default_factory=list)


# ── Top-level document ─────────────────────────────────────────────────────────

class OcsDocument(BaseModel):
    version_info: OcsVersionInfo
    ocs_profile: OcsProfile
    ocs_content: OcsContent
    ocs_attitude: OcsAttitudeSection
