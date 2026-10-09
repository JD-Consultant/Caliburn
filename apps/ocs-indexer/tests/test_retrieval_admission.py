"""Exercise the production ASGI boundary with real workers and no model/network."""

import asyncio
import threading
from pathlib import Path

import anyio
import anyio.lowlevel
import httpx
import pytest
from conftest import FakeQdrant, StubEmbedder
from jd_ocs_indexer.api.app import create_app
from jd_ocs_indexer.config import Settings
from jd_ocs_indexer.references.service import ReferenceSearch


def settings():
    return Settings("http://unused", None, "test", 1, Path("."), 1, "http://unused")


class BlockingEmbedder(StubEmbedder):
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def embed_query(self, text):
        self.calls += 1
        self.started.set()
        assert self.release.wait(10), "test did not release worker"
        return super().embed_query(text)


async def eventually(predicate):
    with anyio.fail_after(3):
        while not predicate():
            await anyio.sleep(0.001)


def test_forty_searches_do_not_starve_health_or_reads():
    async def scenario():
        embedder = BlockingEmbedder()
        app = create_app(settings=settings(), embedder=embedder, client=FakeQdrant())
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test"
            ) as client,
        ):
            requests = [
                asyncio.create_task(
                    client.post("/occupations:search", json={"query": "work"})
                )
                for _ in range(40)
            ]
            try:
                await eventually(embedder.started.is_set)
                # Each request is already in the real ASGI route before the probe.
                await anyio.sleep(0.1)
                with anyio.fail_after(1):
                    health = await client.get("/healthz")
                    read = await client.post(
                        "/tasks:batchGet",
                        json={"ids": ["00000000-0000-0000-0000-000000000001"]},
                    )
                assert health.status_code == read.status_code == 200
                assert embedder.calls == 1
                assert (
                    anyio.to_thread.current_default_thread_limiter().total_tokens == 40
                )
            finally:
                embedder.release.set()
                await asyncio.gather(*requests)

    asyncio.run(scenario())


def test_all_four_model_routes_share_admission():
    class Store:
        def validate_index(self):
            pass

        def search(self, dense, *, route, limit):
            return []

    class Ranker:
        model = "fake"
        revision = "fake"

    async def scenario():
        embedder = BlockingEmbedder()
        app = create_app(
            settings=settings(),
            embedder=embedder,
            client=FakeQdrant(),
            reference_search=ReferenceSearch(Store(), embedder, Ranker()),
        )
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test"
            ) as client,
        ):
            first = asyncio.create_task(
                client.post("/occupations:search", json={"query": "first"})
            )
            rest = []
            try:
                await eventually(embedder.started.is_set)
                rest = [
                    asyncio.create_task(
                        client.post("/tasks:search", json={"query": "task"})
                    ),
                    asyncio.create_task(
                        client.post(
                            "/occupation-references:search",
                            json={"query": "reference"},
                        )
                    ),
                    asyncio.create_task(
                        client.post(
                            "/items:match",
                            json={
                                "kind": "knowledge",
                                "items": [
                                    {"id": "a", "text": "alpha", "sources": ["a"]},
                                    {"id": "b", "text": "beta", "sources": ["b"]},
                                ],
                            },
                        )
                    ),
                ]
                await anyio.sleep(0.05)
                assert not any(task.done() for task in rest)
                assert embedder.calls == 1
                assert (await client.get("/healthz")).status_code == 200
            finally:
                embedder.release.set()
                results = await asyncio.gather(first, *rest)
            assert all(response.status_code == 200 for response in results), [
                r.text for r in results
            ]
            assert embedder.calls == 5  # Match embeds the two distinct items.

    asyncio.run(scenario())


def test_running_scope_cancellation_discards_result_after_completion():
    from jd_ocs_indexer.api.retrieval import RetrievalWorker

    async def scenario():
        owner = RetrievalWorker()
        embedder = BlockingEmbedder()
        scope = anyio.CancelScope()
        results = []

        async def request():
            with scope:
                results.append(await owner.run(lambda: embedder.embed_query("one")))

        task = asyncio.create_task(request())
        try:
            await eventually(embedder.started.is_set)
            scope.cancel()
            await anyio.sleep(0.02)
            assert not task.done()
        finally:
            embedder.release.set()
            await task
            await owner.aclose()
        assert scope.cancelled_caught
        assert results == []

    asyncio.run(scenario())


def test_lifespan_waits_for_worker_before_closing_owned_clients(monkeypatch):
    import jd_ocs_indexer.embeddings.factory as embedder_factory
    import jd_ocs_indexer.store.qdrant_client as client_factory

    events = []

    class Embedder(BlockingEmbedder):
        def embed_query(self, text):
            result = super().embed_query(text)
            events.append("worker finished")
            return result

        def close(self):
            events.append("embedder closed")

    class Client(FakeQdrant):
        def close(self):
            events.append("client closed")

    embedder = Embedder()
    monkeypatch.setattr(embedder_factory, "make_embedder", lambda *a, **kw: embedder)
    monkeypatch.setattr(client_factory, "make_client", lambda **kw: Client())

    async def scenario():
        app = create_app(settings=settings())
        lifespan = app.router.lifespan_context(app)
        await lifespan.__aenter__()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            request = asyncio.create_task(
                client.post("/occupations:search", json={"query": "one"})
            )
            shutdown = None
            try:
                await eventually(embedder.started.is_set)
                request.cancel()
                shutdown = asyncio.create_task(lifespan.__aexit__(None, None, None))
                await anyio.sleep(0.01)
                shutdown.cancel()
                await anyio.sleep(0.01)
                shutdown.cancel()
                await anyio.sleep(0.01)
                assert events == []
                assert not shutdown.done()
            finally:
                embedder.release.set()
                await asyncio.gather(
                    request, *([shutdown] if shutdown else []), return_exceptions=True
                )
                if shutdown is None:
                    await lifespan.__aexit__(None, None, None)
        assert events == ["worker finished", "client closed", "embedder closed"]
        assert not any(
            t.name.startswith("ocs-retrieval") for t in threading.enumerate()
        )

    asyncio.run(scenario())


@pytest.mark.parametrize("cancellation", ["scope", "raw"])
def test_cancelled_before_dispatch_never_starts_worker(cancellation):
    from jd_ocs_indexer.api.retrieval import RetrievalWorker

    async def scenario():
        owner = RetrievalWorker()
        calls = []
        try:
            if cancellation == "scope":
                with anyio.CancelScope() as scope:
                    scope.cancel()
                    await owner.run(lambda: calls.append("started"))
                assert scope.cancelled_caught
            else:
                asyncio.get_running_loop().call_soon(asyncio.current_task().cancel)
                with pytest.raises(asyncio.CancelledError):
                    await owner.run(lambda: calls.append("started"))
            assert calls == []
        finally:
            await owner.aclose()

    asyncio.run(scenario())


def test_running_cancel_keeps_lane_and_close_waits_for_physical_completion():
    from jd_ocs_indexer.api.retrieval import RetrievalUnavailable, RetrievalWorker

    async def scenario():
        owner = RetrievalWorker()
        embedder = BlockingEmbedder()
        active = asyncio.create_task(owner.run(lambda: embedder.embed_query("one")))
        queued = None
        closing = None
        try:
            await eventually(embedder.started.is_set)
            queued = asyncio.create_task(owner.run(lambda: embedder.embed_query("two")))
            active.cancel()
            await anyio.lowlevel.checkpoint()
            active.cancel()
            await anyio.sleep(0.02)
            assert not active.done()
            assert embedder.calls == 1
            closing = asyncio.create_task(owner.aclose())
            await anyio.sleep(0.02)
            assert not closing.done()
            with pytest.raises(RetrievalUnavailable):
                await queued
            with pytest.raises(RetrievalUnavailable):
                await owner.run(lambda: None)
            closing.cancel()
            await anyio.lowlevel.checkpoint()
            closing.cancel()
            assert not closing.done()
        finally:
            embedder.release.set()
            results = await asyncio.gather(
                active,
                *([queued] if queued else []),
                *([closing] if closing else []),
                return_exceptions=True,
            )
            await owner.aclose()
        assert isinstance(results[0], asyncio.CancelledError)
        assert isinstance(results[-1], asyncio.CancelledError)
        assert embedder.calls == 1

    asyncio.run(scenario())


def test_queue_cancel_timeout_and_failure_leave_owner_usable():
    from jd_ocs_indexer.api.retrieval import RetrievalBusy, RetrievalWorker

    async def scenario():
        owner = RetrievalWorker(admission_timeout=0.03)
        embedder = BlockingEmbedder()
        active = asyncio.create_task(owner.run(lambda: embedder.embed_query("one")))
        try:
            await eventually(embedder.started.is_set)
            queued = asyncio.create_task(
                owner.run(lambda: embedder.embed_query("cancelled"))
            )
            await anyio.sleep(0.01)
            queued.cancel()
            with pytest.raises(asyncio.CancelledError):
                await queued
            with pytest.raises(RetrievalBusy):
                await owner.run(lambda: embedder.embed_query("timed out"))
            assert embedder.calls == 1
        finally:
            embedder.release.set()
            await active
        try:

            def broken():
                raise ValueError("broken")

            with pytest.raises(ValueError, match="broken"):
                await owner.run(broken)
            assert await owner.run(lambda: 42) == 42
        finally:
            await owner.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("cancellation", ["scope", "raw"])
def test_cancellation_after_token_acquisition_prevents_submit(
    monkeypatch, cancellation
):
    from jd_ocs_indexer.api.retrieval import RetrievalWorker

    async def scenario():
        owner = RetrievalWorker()
        calls = []
        limiter_type = type(anyio.CapacityLimiter(1))
        acquire_nowait = limiter_type.acquire_on_behalf_of_nowait
        with anyio.CancelScope() as scope:

            def acquire_and_cancel(limiter, borrower):
                acquire_nowait(limiter, borrower)
                if cancellation == "scope":
                    scope.cancel()
                else:
                    asyncio.get_running_loop().call_soon(asyncio.current_task().cancel)

            with monkeypatch.context() as patch:
                # Use native acquisition; inject cancellation into its documented
                # shielded checkpoint, rather than replacing the limiter.
                patch.setattr(
                    limiter_type, "acquire_on_behalf_of_nowait", acquire_and_cancel
                )
                if cancellation == "raw":
                    with pytest.raises(asyncio.CancelledError):
                        await owner.run(lambda: calls.append("started"))
                else:
                    await owner.run(lambda: calls.append("started"))
        await owner.aclose()
        assert calls == []
        if cancellation == "scope":
            assert scope.cancelled_caught

    asyncio.run(scenario())


def test_busy_and_shutdown_are_controlled_http_responses(monkeypatch):
    from functools import partial

    import jd_ocs_indexer.api.app as app_module
    from jd_ocs_indexer.api.retrieval import RetrievalWorker

    monkeypatch.setattr(
        app_module, "RetrievalWorker", partial(RetrievalWorker, admission_timeout=0.02)
    )

    async def scenario():
        embedder = BlockingEmbedder()
        app = create_app(settings=settings(), embedder=embedder, client=FakeQdrant())
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test"
            ) as client,
        ):
            active = asyncio.create_task(
                client.post("/tasks:search", json={"query": "one"})
            )
            try:
                await eventually(embedder.started.is_set)
                busy = await client.post("/tasks:search", json={"query": "two"})
                assert busy.status_code == 503
                assert busy.json() == {"detail": {"code": "retrieval_busy"}}
            finally:
                embedder.release.set()
                await active
            await app.state.retrieval.aclose()
            closed = await client.post("/tasks:search", json={"query": "three"})
            assert closed.status_code == 503
            assert closed.json() == {"detail": {"code": "retrieval_unavailable"}}

    asyncio.run(scenario())
