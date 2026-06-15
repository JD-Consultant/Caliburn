"""jd-ocs-indexer query API 的回應模型（typed，extra 欄位忽略以容忍 API 演進）。"""
from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


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
    ocs_code: str = ""
    knowledge: list[Pair] = []
    skills: list[Pair] = []
    attitudes: list[Pair] = []
    outputs: list[Pair] = []
    prerequisites: list[str] = []
    supplements: list[str] = []


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
