from app.services.knowledge.models import SearchResult, TaskPool


class FakeKnowledge:
    def __init__(self, search=None, pool=None):
        self._search = search or SearchResult(mode="dense", hits=[])
        self._pool = pool or TaskPool(groups=[])
        self.calls = []

    async def search(self, query, **kw):
        self.calls.append(("search", query)); return self._search

    async def task_pool(self, ocs_codes, **kw):
        self.calls.append(("task_pool", ocs_codes)); return self._pool

    async def pairs(self, ocs_code): ...
    async def tasks_by_id(self, ids): ...
    async def healthz(self): return True


class SpyPersist:
    def __init__(self): self.selected = None; self.flushed = None
    async def set_selected_ocs(self, pid, ocs): self.selected = (str(pid), ocs)
    async def flush_tasks(self, pid, tasks): self.flushed = (str(pid), tasks)
