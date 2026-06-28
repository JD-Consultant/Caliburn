from app.core.knowledge_dto import (
    CompetencyPool,
    OccupationSearchResponse,
    OccupationTasks,
)


class FakeKnowledge:
    def __init__(self):
        self._competencies = None
        self._occ_tasks = None
        self._occ_search = None
        self.calls = []

    async def search_occupations(self, query, *, top_k=10):
        self.calls.append(("search_occupations", query))
        return self._occ_search or OccupationSearchResponse(hits=[])

    async def occupation_tasks(self, ocs_code):
        self.calls.append(("occupation_tasks", ocs_code))
        return self._occ_tasks or OccupationTasks(ocs_code=ocs_code)

    async def competencies(self, ocs_code):
        self.calls.append(("competencies", ocs_code))
        return self._competencies or CompetencyPool(ocs_code=ocs_code)

    async def healthz(self):
        return True


class SpyPersist:
    def __init__(self): self.selected = None; self.doc_saved = None
    async def set_selected_ocs(self, pid, codes): self.selected = (str(pid), codes)
    async def save_document(self, pid, content):
        self.doc_saved = (str(pid), content)
        return {"id": "spy-1", "version": 1, "content": content, "status": "draft"}


class FakeLlm:
    """可配的 LlmPort 假件。json/text 可給 callable 或固定值；raises=True 模擬失敗。"""
    def __init__(self, json=None, text="", raises=False):
        self._json = json
        self._text = text
        self._raises = raises
        self.calls = []

    async def complete_text(self, prompt, *, role="cheap"):
        self.calls.append(("text", role))
        if self._raises:
            raise RuntimeError("llm down")
        return self._text(prompt) if callable(self._text) else self._text

    async def complete_json(self, prompt, *, role="cheap", default=None):
        self.calls.append(("json", role))
        if self._raises:
            return default
        if self._json is None:
            return default
        return self._json(prompt) if callable(self._json) else self._json
