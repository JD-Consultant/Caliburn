from app.services.knowledge.models import SearchResult, TaskPool, Pairs


class FakeKnowledge:
    def __init__(self, search=None, pool=None, tasks=None):
        self._search = search or SearchResult(mode="dense", hits=[])
        self._pool = pool or TaskPool(groups=[])
        self._tasks = tasks  # TasksByIdResult | None
        self.calls = []

    async def search(self, query, **kw):
        self.calls.append(("search", query)); return self._search

    async def task_pool(self, ocs_codes, **kw):
        self.calls.append(("task_pool", ocs_codes)); return self._pool

    async def pairs(self, ocs_code):
        self.calls.append(("pairs", ocs_code)); return Pairs(ocs_code=ocs_code)

    async def tasks_by_id(self, ids):
        from app.services.knowledge.models import TasksByIdResult
        self.calls.append(("tasks_by_id", list(ids)))
        return self._tasks or TasksByIdResult(tasks=[])

    async def healthz(self):
        return True


class SpyPersist:
    def __init__(self): self.selected = None; self.flushed = None
    async def set_selected_ocs(self, pid, ocs): self.selected = (str(pid), ocs)
    async def flush_tasks(self, pid, tasks): self.flushed = (str(pid), tasks)


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
