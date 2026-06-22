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
    """jd-ocs-indexer ``GET /profile/{ocs_code}`` 回應（D29）：文件表頭用的職類 metadata。"""
    ocs_code: str = ""
    job_title: str = ""
    job_category: Pair = Field(default_factory=Pair)
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
