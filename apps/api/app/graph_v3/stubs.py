"""Demo 用 stub：不需真 indexer/Qdrant/DB，先證明 CopilotKit↔graph_v3 plumbing。
仍走 KnowledgeClient / PersistPort 抽象（D6/D7）。真實作於後續 phase 接上。"""
from uuid import UUID

from app.core.knowledge_dto import (
    CitableItem,
    CompetencyPool,
    OccupationHit,
    OccupationSearchResponse,
    OccupationTasks,
    SourceRef,
    TaskRef,
    UnitTasks,
)


class StubKnowledge:
    """假 KnowledgeClient（canned 資料）。"""

    async def search_occupations(self, query, *, top_k=10) -> OccupationSearchResponse:
        return OccupationSearchResponse(hits=[
            OccupationHit(ocs_code="KRM2421-001v4", urn="ocs:KRM2421-001v4", ocs_name="設備維護工程師"),
            OccupationHit(ocs_code="KRM2422-001v4", urn="ocs:KRM2422-001v4", ocs_name="生產線技術員"),
        ])

    async def occupation_tasks(self, ocs_code) -> OccupationTasks:
        return OccupationTasks(ocs_code=ocs_code, ocs_name="設備維護工程師", units=[
            UnitTasks(ocu_code="U1", ocu_name="預防保養", urn=f"ocs:{ocs_code}:U:U1", tasks=[
                TaskRef(task_code="T1.1", task_name="例行設備巡檢", urn=f"ocs:{ocs_code}:T:T1.1"),
                TaskRef(task_code="T1.2", task_name="保養排程管理", urn=f"ocs:{ocs_code}:T:T1.2"),
            ])])

    async def competencies(self, ocs_code) -> CompetencyPool:
        return CompetencyPool(ocs_code=ocs_code,
            knowledge=[CitableItem(id=f"ocs:{ocs_code}:K:K01", type="K", code="K01",
                                   name="設備保養原理", ocs_code=ocs_code, ocs_name="設備維護工程師",
                                   sources=[SourceRef(task_code="T1.1")])],
            skills=[CitableItem(id=f"ocs:{ocs_code}:S:S01", type="S", code="S01", name="點檢操作",
                                ocs_code=ocs_code, ocs_name="設備維護工程師", sources=[SourceRef(task_code="T1.1")])],
            attitudes=[CitableItem(id=f"ocs:{ocs_code}:A:A01", type="A", code="A01", name="細心負責",
                                   ocs_code=ocs_code, ocs_name="設備維護工程師", sources=[])])

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
