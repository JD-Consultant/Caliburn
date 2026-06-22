"""Demo 用 stub：不需真 indexer/Qdrant/DB，先證明 CopilotKit↔graph_v3 plumbing。
仍走 KnowledgeClient / PersistPort 抽象（D6/D7）。真實作於後續 phase 接上。"""
from uuid import UUID

from app.services.knowledge.models import (
    Hit,
    Pair,
    Pairs,
    PoolGroup,
    PoolTask,
    PoolUnit,
    ProfileMeta,
    SearchResult,
    TaskPool,
    TasksByIdResult,
)


class StubKnowledge:
    """假 KnowledgeClient（canned 資料）。"""

    async def search(self, query, **kw) -> SearchResult:
        return SearchResult(mode="dense", hits=[
            Hit(id="OC1", ocs_code="KRM2421-001v4", chunk_level="profile", job_title="設備維護工程師"),
            Hit(id="OC2", ocs_code="KRM2422-001v4", chunk_level="profile", job_title="生產線技術員"),
        ])

    async def task_pool(self, ocs_codes, **kw) -> TaskPool:
        return TaskPool(groups=[PoolGroup(
            ocs_code=(ocs_codes or ["OC1"])[0], job_title="設備維護工程師",
            units=[PoolUnit(unit_id="U1", unit_title="預防保養", tasks=[
                PoolTask(id="T1.1", task_id="T1.1", task_title="例行設備巡檢",
                         activity_examples=["每日點檢", "異常記錄"]),
                PoolTask(id="T1.2", task_id="T1.2", task_title="保養排程管理",
                         activity_examples=["排定週期保養"]),
            ])])])

    async def pairs(self, ocs_code) -> Pairs:
        return Pairs(ocs_code=ocs_code,
                     knowledge=[Pair(code="K01", name="設備保養原理")],
                     skills=[Pair(code="S01", name="點檢操作")],
                     attitudes=[Pair(code="A01", name="細心負責")])

    async def profile(self, ocs_code) -> ProfileMeta:
        return ProfileMeta(ocs_code=ocs_code, job_title="設備維護工程師",
                           job_category=Pair(code="KRM", name="機械類"),
                           industries=[Pair(code="C", name="製造業")],
                           attitudes=[Pair(code="A01", name="細心負責")],
                           job_description="負責設備維護", ocs_level=4)

    async def tasks_by_id(self, ids) -> TasksByIdResult:
        return TasksByIdResult(tasks=[])

    async def healthz(self) -> bool:
        return True


class InMemoryPersist:
    """Demo 用 PersistPort：只記憶體，不寫 DB（真 DbPersist 留 live-persistence phase）。"""

    def __init__(self):
        self.selected: dict = {}
        self.docs: dict = {}

    async def set_selected_ocs(self, job_profile_id: UUID, codes: list[str]) -> None:
        self.selected[str(job_profile_id)] = list(codes or [])

    async def save_document(self, job_profile_id, content) -> dict:
        v = len(self.docs.get(str(job_profile_id), [])) + 1
        self.docs.setdefault(str(job_profile_id), []).append(content)
        return {"id": f"mem-{v}", "version": v,
                "content": content, "status": "draft"}
