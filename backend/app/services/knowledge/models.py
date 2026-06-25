"""jd-ocs-indexer query API 的回應模型（typed，extra 欄位忽略以容忍 API 演進）。"""
from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    # populate_by_name：別名欄位仍可用欄位名建構（stub/測試用 Pairs(knowledge=...)）。
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class Pair(_Base):
    code: str = ""
    name: str = ""


class Hit(_Base):
    id: str
    score: float = 0.0
    chunk_level: str = ""
    ocs_code: str = ""
    job_title: str | None = None
    unit_id: str | None = None
    unit_title: str | None = None
    task_id: str | None = None
    task_title: str | None = None


class SearchResult(_Base):
    mode: str = ""
    hits: list[Hit] = []


class PoolTask(_Base):
    id: str
    task_id: str = ""
    task_title: str = ""
    activity_examples: list[str] = []


class PoolUnit(_Base):
    unit_id: str = ""
    unit_title: str = ""
    tasks: list[PoolTask] = []


class PoolGroup(_Base):
    ocs_code: str = ""
    job_title: str = ""
    units: list[PoolUnit] = []


class TaskPool(_Base):
    groups: list[PoolGroup] = []


class Pairs(_Base):
    # indexer 的 PairsResponse 用 all_*_pairs 為 key（任務 K/S 的 union + profile A）；
    # alias 對應到我們消費端的名稱。沒對到時就是這個 bug（K/S/A 全空）。
    ocs_code: str = ""
    knowledge: list[Pair] = Field(default_factory=list, alias="all_k_pairs")
    skills: list[Pair] = Field(default_factory=list, alias="all_s_pairs")
    attitudes: list[Pair] = Field(default_factory=list, alias="all_a_pairs")
    outputs: list[Pair] = Field(default_factory=list, alias="all_output_pairs")
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)


class ProfileMeta(_Base):
    """jd-ocs-indexer ``GET /profile/{ocs_code}`` 回應（D29）：文件表頭用的職類 metadata。
    所屬類別三組（job_categories/occupations/industries）皆多值 {code,name}；
    job_category_name 為標題用的單一職類名（ocs_name.job_category_name，常空）。"""
    ocs_code: str = ""
    job_title: str = ""
    job_category_name: str = ""
    job_categories: list[Pair] = Field(default_factory=list)
    occupations: list[Pair] = Field(default_factory=list)
    industries: list[Pair] = Field(default_factory=list)
    job_description: str = ""
    ocs_level: int | None = None
    attitudes: list[Pair] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)


class TaskDetail(_Base):
    id: str
    ocs_code: str = ""
    unit_id: str | None = None
    unit_title: str | None = None
    task_id: str = ""
    task_title: str = ""
    competency_level: int | None = None
    activity_examples: list[str] = []
    k_pairs: list[Pair] = []
    s_pairs: list[Pair] = []
    output_pairs: list[Pair] = []


class TasksByIdResult(_Base):
    tasks: list[TaskDetail] = []


class CodeName(_Base):
    code: str = ""
    name: str = ""


class OcsName(_Base):
    job_category_name: str | None = None
    occupation_name: str | None = None


class SourceRef(_Base):
    ocu_code: str | None = None
    ocu_name: str | None = None
    task_code: str | None = None
    task_name: str | None = None
    competency_level: int | None = None


class CitableItem(_Base):
    id: str = ""
    type: str = ""
    code: str = ""
    name: str | None = None
    text: str | None = None
    ocs_code: str = ""
    ocs_name: str = ""
    sources: list[SourceRef] = Field(default_factory=list)


class OccupationDetail(_Base):
    ocs_code: str = ""
    urn: str = ""
    ocs_name: OcsName = Field(default_factory=OcsName)
    job_categories: list[CodeName] = Field(default_factory=list)
    occupations: list[CodeName] = Field(default_factory=list)
    industries: list[CodeName] = Field(default_factory=list)
    job_description: str = ""
    ocs_level: int | None = None
    attitudes: list[CodeName] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)


class CompetencyPool(_Base):
    ocs_code: str = ""
    knowledge: list[CitableItem] = Field(default_factory=list)
    skills: list[CitableItem] = Field(default_factory=list)
    outputs: list[CitableItem] = Field(default_factory=list)
    indicators: list[CitableItem] = Field(default_factory=list)
    attitudes: list[CitableItem] = Field(default_factory=list)


class TaskRef(_Base):
    task_code: str = ""
    task_name: str = ""
    urn: str = ""


class UnitTasks(_Base):
    ocu_code: str | None = None
    ocu_name: str | None = None
    urn: str = ""
    tasks: list[TaskRef] = Field(default_factory=list)


class OccupationTasks(_Base):
    ocs_code: str = ""
    ocs_name: str = ""
    units: list[UnitTasks] = Field(default_factory=list)


class OccupationHit(_Base):
    ocs_code: str = ""
    urn: str = ""
    ocs_name: str = ""
    job_description: str = ""
    ocs_level: int | None = None
    score: float | None = None


class OccupationSearchResponse(_Base):
    hits: list[OccupationHit] = Field(default_factory=list)


class TaskHit(_Base):
    ocs_code: str = ""
    ocs_name: str = ""
    ocu_code: str | None = None
    ocu_name: str | None = None
    task_code: str | None = None
    task_name: str | None = None
    urn: str = ""
    score: float | None = None


class TaskSearchResponse(_Base):
    hits: list[TaskHit] = Field(default_factory=list)
