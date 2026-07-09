"""Demo 用 stub：不需真 indexer/Qdrant/DB，先證明 CopilotKit↔authoring plumbing。
仍走 KnowledgeClient / PersistPort 抽象（D6/D7）。真實作於後續 phase 接上。"""
from uuid import UUID

from app.core.knowledge_dto import (
    CitableItem,
    CompetencyPool,
    MatchResponse,
    OccupationHit,
    OccupationSearchResponse,
    OccupationTasks,
    SourceRef,
    TaskRef,
    UnitTasks,
)


class StubLlm:
    """假 LlmPort(測試/demo):三句話型皆可程控;呼叫紀錄留 calls 供斷言。"""

    def __init__(self, *, text: str = "", json_result=None, select_result=None,
                 chat_text: str = "我了解了,想再多聊聊你這件事的細節,方便說個最近的例子嗎?",
                 chat_trace: list | None = None):
        self._text = text
        self._json = json_result
        self._select = select_result   # dict 或 callable(prompt, schema) -> dict
        self._chat_text = chat_text
        self._chat_trace = list(chat_trace or [])   # 模擬顧問工具軌跡(0028 widget 測試)
        self.calls: list[dict] = []

    async def complete_text(self, prompt: str, *, role: str = "cheap") -> str:
        self.calls.append({"kind": "text", "role": role, "prompt": prompt})
        return self._text

    async def complete_json(self, prompt: str, *, role: str = "cheap", default=None):
        self.calls.append({"kind": "json", "role": role, "prompt": prompt})
        return self._json if self._json is not None else default

    async def select_schema(self, prompt: str, schema: dict, *,
                            role: str = "select", schema_name: str = "output"):
        self.calls.append({"kind": "select", "role": role, "prompt": prompt,
                           "schema": schema, "schema_name": schema_name})
        if callable(self._select):
            return self._select(prompt, schema)
        return self._select if self._select is not None else {"records": []}

    async def chat_with_tools(self, *, role: str, messages: list[dict], tools: list[dict],
                              dispatch, max_tool_iterations: int = 5):
        """假顧問迴圈:回 canned 文字(ChatResult),不呼工具。role/messages 記 calls。"""
        from app.interview.agent_loop import ChatResult
        self.calls.append({"kind": "chat", "role": role, "messages": messages})
        for t in self._chat_trace:            # 忠實模擬:trace 裡的工具真的 dispatch 一次
            try:
                await dispatch(t["name"], t.get("args") or {})
            except Exception:  # noqa: BLE001,S110  (stub:dispatch 失敗不擋 canned 回覆)
                pass
        return ChatResult(text=self._chat_text, tool_trace=list(self._chat_trace),
                          stopped="natural")


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

    async def match(self, kind: str, items: list[dict]) -> MatchResponse:
        return MatchResponse()   # demo:無分群(空 groups/possible_matches)

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
