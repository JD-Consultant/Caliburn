"""公開組裝入口檢查服務依賴，原生 async CM 負責取得與清理。"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, cast
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import (
    PluginServices,
    ServiceBinding,
    ServiceKey,
)
from caliburn.modules.agent.state import (
    AgentState,
    request_items,
)
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    MODEL_REQUEST,
    EventStream,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

FIRST = ServiceKey[str]("first")
SECOND = ServiceKey[str]("second")
TRACE = ServiceKey[list[str]]("trace")
SOURCE_BINDINGS = ServiceKey[tuple[ServiceBinding[str], ...]]("source-bindings")
MIDDLE_ENTERED = ServiceKey[asyncio.Event]("middle-entered")
MIDDLE_RELEASE = ServiceKey[asyncio.Event]("middle-release")


@asynccontextmanager
async def source(
    dependencies: PluginServices,
) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
    events = dependencies.require(TRACE)
    events.append("source:enter")
    try:
        yield (FIRST.bind("shared"),)
    finally:
        await asyncio.sleep(0)
        events.append("source:exit")


@asynccontextmanager
async def source_with_supplied_bindings(
    dependencies: PluginServices,
) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
    async with source(dependencies):
        yield dependencies.require(SOURCE_BINDINGS)


@asynccontextmanager
async def consumer(
    dependencies: PluginServices,
) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
    events = dependencies.require(TRACE)
    value = dependencies.require(FIRST)
    events.append(f"consumer:{value}:enter")
    try:
        yield ()
    finally:
        events.append(f"consumer:{value}:exit")


def fail_setup() -> None:
    raise RuntimeError("consumer setup failed")


@asynccontextmanager
async def failing_consumer(
    dependencies: PluginServices,
) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
    async with consumer(dependencies) as bindings:
        fail_setup()
        yield bindings


@asynccontextmanager
async def undeclared_lookup_consumer(
    dependencies: PluginServices,
) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
    async with consumer(dependencies) as bindings:
        dependencies.require(SECOND)
        yield bindings


@asynccontextmanager
async def waiting_middle(
    dependencies: PluginServices,
) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
    events = dependencies.require(TRACE)
    value = dependencies.require(FIRST)
    events.append("middle:partial-acquire")
    try:
        dependencies.require(MIDDLE_ENTERED).set()
        await dependencies.require(MIDDLE_RELEASE).wait()
        yield (SECOND.bind(value),)
    finally:
        await asyncio.sleep(0)
        events.append("middle:partial-release")


@asynccontextmanager
async def downstream_consumer(
    dependencies: PluginServices,
) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
    dependencies.require(TRACE).append("downstream:enter")
    yield ()


def ordered_plugin(
    name: str,
    required: tuple[ServiceKey[str], ...],
    provided: tuple[ServiceKey[str], ...],
) -> AgentPlugin:
    @asynccontextmanager
    async def acquire(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        dependencies.require(TRACE).append(name)
        yield tuple(key.bind(name) for key in provided)

    async def provide(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        request = state["model_request"]
        return {
            "model_request": {
                **request,
                "input": cast(
                    ResponseInputParam,
                    [*request_items(request), {"role": "user", "content": name}],
                ),
            }
        }

    return AgentPlugin(
        name,
        required_services=(*required, TRACE),
        provided_services=provided,
        open_services=acquire,
        prompt_sections=(name,),
        before_model_step=(PluginStep("provide", provide),),
    )


SOURCE_PLUGIN = AgentPlugin(
    "source",
    required_services=(TRACE,),
    provided_services=(FIRST,),
    open_services=source,
)
CONSUMER_PLUGIN = AgentPlugin(
    "consumer", required_services=(FIRST, TRACE), open_services=consumer
)
BUNDLES = {
    "missing": AgentBundle((AgentPlugin("consumer", required_services=(FIRST,)),)),
    "duplicate_plugin": AgentBundle((AgentPlugin("same"), AgentPlugin("same"))),
    "duplicate_service": AgentBundle(
        (
            AgentPlugin("one", provided_services=(FIRST,)),
            AgentPlugin("two", provided_services=(FIRST,)),
        )
    ),
    "ambiguous_key": AgentBundle(
        (
            AgentPlugin("one", provided_services=(FIRST,)),
            AgentPlugin("two", required_services=(ServiceKey[str]("first"),)),
        )
    ),
    "cycle": AgentBundle(
        (
            AgentPlugin("one", required_services=(SECOND,), provided_services=(FIRST,)),
            AgentPlugin("two", required_services=(FIRST,), provided_services=(SECOND,)),
        )
    ),
    "normal": AgentBundle((CONSUMER_PLUGIN, SOURCE_PLUGIN)),
    "setup_failure": AgentBundle(
        (
            AgentPlugin(
                "consumer",
                required_services=(FIRST, TRACE),
                open_services=failing_consumer,
            ),
            SOURCE_PLUGIN,
        )
    ),
    "undeclared_lookup": AgentBundle(
        (
            AgentPlugin(
                "consumer",
                required_services=(FIRST, TRACE),
                open_services=undeclared_lookup_consumer,
            ),
            SOURCE_PLUGIN,
        )
    ),
    "supplied_bindings": AgentBundle(
        (
            CONSUMER_PLUGIN,
            AgentPlugin(
                "source",
                required_services=(TRACE, SOURCE_BINDINGS),
                provided_services=(FIRST,),
                open_services=source_with_supplied_bindings,
            ),
        )
    ),
    "ready_order": AgentBundle(
        (
            ordered_plugin("consumer", (SECOND,), ()),
            ordered_plugin("first", (), (FIRST,)),
            ordered_plugin("second", (), (SECOND,)),
        )
    ),
    "ready_tie": AgentBundle(
        (
            ordered_plugin("a", (SECOND,), ()),
            ordered_plugin("b", (FIRST,), ()),
            ordered_plugin("c", (), (FIRST,)),
            ordered_plugin("d", (), (SECOND,)),
        )
    ),
    "waiting_acquisition": AgentBundle(
        (
            AgentPlugin(
                "downstream",
                required_services=(SECOND, TRACE),
                open_services=downstream_consumer,
            ),
            AgentPlugin(
                "middle",
                required_services=(FIRST, TRACE, MIDDLE_ENTERED, MIDDLE_RELEASE),
                provided_services=(SECOND,),
                open_services=waiting_middle,
            ),
            SOURCE_PLUGIN,
        )
    ),
}


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return BUNDLES[str(config["name"])]


@pytest.mark.parametrize(
    "name, match",
    [
        ("missing", "consumer.*first"),
        ("duplicate_plugin", "same"),
        ("duplicate_service", "first"),
        ("ambiguous_key", "first"),
        ("cycle", "one.*two|two.*one"),
    ],
)
def test_invalid_service_configuration_fails_at_startup(name: str, match: str) -> None:
    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            with pytest.raises(ValueError, match=match):
                async with open_agent(
                    agent_id="services",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    checkpointer=InMemorySaver(),
                    bundles=[BundleConfig(__name__, {"name": name})],
                ):
                    pytest.fail("invalid Agent opened")

    asyncio.run(run())


def test_external_provider_conflict_is_rejected_at_startup() -> None:
    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            with pytest.raises(ValueError, match="first"):
                async with open_agent(
                    agent_id="services",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    checkpointer=InMemorySaver(),
                    bundles=[BundleConfig(__name__, {"name": "normal"})],
                    external_services=(FIRST.bind("host"), TRACE.bind([])),
                ):
                    pytest.fail("conflicting Agent opened")

    asyncio.run(run())


def test_startup_injects_shared_service_and_closes_in_reverse_order() -> None:
    events: list[str] = []

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            agent_lifecycle = open_agent(
                agent_id="services",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"name": "normal"})],
                external_services=(TRACE.bind(events),),
            )
            async with agent_lifecycle:
                events.append("body")

    asyncio.run(run())
    assert events == [
        "source:enter",
        "consumer:shared:enter",
        "body",
        "consumer:shared:exit",
        "source:exit",
    ]


def test_initialization_failure_closes_partial_then_acquired_resources() -> None:
    events: list[str] = []

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            agent_lifecycle = open_agent(
                agent_id="services",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"name": "setup_failure"})],
                external_services=(TRACE.bind(events),),
            )
            with pytest.raises(RuntimeError, match="consumer setup failed"):
                async with agent_lifecycle:
                    pytest.fail("run entered")

    asyncio.run(run())
    assert events == [
        "source:enter",
        "consumer:shared:enter",
        "consumer:shared:exit",
        "source:exit",
    ]


def test_undeclared_service_lookup_is_rejected_and_closes_resources() -> None:
    events: list[str] = []

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            agent_lifecycle = open_agent(
                agent_id="services",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"name": "undeclared_lookup"})],
                external_services=(TRACE.bind(events),),
            )
            with pytest.raises(ValueError, match="second"):
                async with agent_lifecycle:
                    pytest.fail("run entered")

    asyncio.run(run())
    assert events == [
        "source:enter",
        "consumer:shared:enter",
        "consumer:shared:exit",
        "source:exit",
    ]


@pytest.mark.parametrize(
    "bindings, match, cleanup",
    [
        pytest.param(
            (), "source.*first", ["source:enter", "source:exit"], id="missing"
        ),
        pytest.param(
            (FIRST.bind("7"), SECOND.bind("7")),
            "source.*second",
            ["source:enter", "source:exit"],
            id="extra",
        ),
        pytest.param(
            (FIRST.bind("7"), FIRST.bind("7")),
            "source.*first",
            ["source:enter", "source:exit"],
            id="duplicate",
        ),
    ],
)
def test_binding_mismatch_rejects_startup_and_closes_source(
    bindings: tuple[ServiceBinding[str], ...], match: str, cleanup: list[str]
) -> None:
    events: list[str] = []

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            agent_lifecycle = open_agent(
                agent_id="services",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"name": "supplied_bindings"})],
                external_services=(TRACE.bind(events), SOURCE_BINDINGS.bind(bindings)),
            )
            with pytest.raises(ValueError, match=match):
                async with agent_lifecycle:
                    pytest.fail("run entered")

    asyncio.run(run())
    assert events == cleanup


def test_missing_external_binding_fails_before_acquiring_plugins() -> None:
    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            agent_lifecycle = open_agent(
                agent_id="services",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"name": "normal"})],
            )
            with pytest.raises(ValueError, match="trace"):
                async with agent_lifecycle:
                    pytest.fail("run entered")

    asyncio.run(run())


@pytest.mark.parametrize(
    "name, expected",
    [
        ("ready_order", ["first", "second", "consumer"]),
        ("ready_tie", ["c", "d", "a", "b"]),
    ],
)
def test_ready_plugins_keep_configuration_order(name: str, expected: list[str]) -> None:
    events: list[str] = []

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail())
        ) as client:
            agent_lifecycle = open_agent(
                agent_id="services",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"name": name})],
                external_services=(TRACE.bind(events),),
            )
            async with agent_lifecycle:
                pass

    asyncio.run(run())
    assert events == expected


def test_dependency_startup_does_not_reorder_materials_or_wrappers() -> None:
    events: list[str] = []
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            agent_lifecycle = open_agent(
                agent_id="services",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"name": "ready_order"})],
                external_services=(TRACE.bind(events),),
            )
            async with agent_lifecycle as agent:
                for workspace_id in (UUID(int=1), UUID(int=2)):
                    async for _ in agent.astream(
                        turn_id=uuid4(),
                        workspace_id=workspace_id,
                        input=cast(ResponseInputParam, INITIAL),
                    ):
                        pass

    asyncio.run(run())
    assert events == ["first", "second", "consumer"]
    assert len(sent) == 2
    assert sent[0]["instructions"] == "consumer\n\nfirst\n\nsecond"
    assert [item["content"] for item in sent[0]["input"][1:]] == [
        "consumer",
        "first",
        "second",
    ]


def test_cancellation_during_acquisition_releases_partial_then_acquired_resources() -> (
    None
):
    async def run() -> None:
        events: list[str] = []
        entered = asyncio.Event()
        release = asyncio.Event()
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            agent_lifecycle = open_agent(
                agent_id="services",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"name": "waiting_acquisition"})],
                external_services=(
                    TRACE.bind(events),
                    MIDDLE_ENTERED.bind(entered),
                    MIDDLE_RELEASE.bind(release),
                ),
            )

            async def enter() -> None:
                async with agent_lifecycle:
                    pytest.fail("run entered")

            task = asyncio.create_task(enter())
            await asyncio.wait_for(entered.wait(), timeout=5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=5)
            assert events == [
                "source:enter",
                "middle:partial-acquire",
                "middle:partial-release",
                "source:exit",
            ]
            assert not client.is_closed()

    asyncio.run(run())


def test_service_collection_without_provider_is_empty_for_declared_consumer() -> None:
    from caliburn.modules.agent.plugins.composition import open_plugin_services
    from caliburn.modules.agent.plugins.services import ServiceCollection

    collection = ServiceCollection[str]("contributions")
    observed: list[tuple[str, ...]] = []

    @asynccontextmanager
    async def acquire(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        observed.append(dependencies.require(collection))
        yield ()

    async def run() -> None:
        async with open_plugin_services(
            (
                AgentPlugin(
                    "consumer", required_services=(collection,), open_services=acquire
                ),
            ),
            (),
        ) as context:
            assert context.services.require(collection) == ()

    asyncio.run(run())
    assert observed == [()]


@pytest.mark.parametrize("external", [False, True])
def test_collection_aggregation_keeps_declaration_order_after_dependency_sort(
    external: bool,
) -> None:
    from caliburn.modules.agent.plugins.composition import open_plugin_services
    from caliburn.modules.agent.plugins.services import ServiceCollection

    collection = ServiceCollection[str]("contributions")
    events: list[str] = []
    observed: list[tuple[str, ...]] = []

    @asynccontextmanager
    async def acquire_first(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        assert dependencies.require(FIRST) == "ready"
        events.append("first:enter")
        try:
            yield (collection.bind(("first-one", "first-two")),)
        finally:
            events.append("first:exit")

    @asynccontextmanager
    async def acquire_second(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        events.append("second:enter")
        try:
            yield (FIRST.bind("ready"), collection.bind(("second",)))
        finally:
            events.append("second:exit")

    @asynccontextmanager
    async def acquire_consumer(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        events.append("consumer:enter")
        observed.append(dependencies.require(collection))
        try:
            yield ()
        finally:
            events.append("consumer:exit")

    async def run() -> None:
        async with open_plugin_services(
            (
                AgentPlugin(
                    "consumer",
                    required_services=(collection,),
                    open_services=acquire_consumer,
                ),
                AgentPlugin(
                    "first",
                    required_services=(FIRST,),
                    provided_services=(collection,),
                    open_services=acquire_first,
                ),
                AgentPlugin(
                    "second",
                    provided_services=(FIRST, collection),
                    open_services=acquire_second,
                ),
            ),
            (collection.bind(("host",)),) if external else (),
        ) as context:
            assert context.services.require(collection) == observed[0]

    asyncio.run(run())
    assert observed == [
        ("host", "first-one", "first-two", "second")
        if external
        else ("first-one", "first-two", "second")
    ]
    assert events == [
        "second:enter",
        "first:enter",
        "consumer:enter",
        "consumer:exit",
        "first:exit",
        "second:exit",
    ]


@pytest.mark.parametrize("failure", ["missing", "duplicate", "undeclared"])
def test_collection_binding_mismatch_rejects_startup_and_closes_provider(
    failure: str,
) -> None:
    from caliburn.modules.agent.plugins.composition import open_plugin_services
    from caliburn.modules.agent.plugins.services import ServiceCollection

    collection = ServiceCollection[str]("contributions")
    bindings = {
        "missing": (),
        "duplicate": (collection.bind(("one",)), collection.bind(("two",))),
        "undeclared": (collection.bind(("one",)),),
    }
    events: list[str] = []

    @asynccontextmanager
    async def acquire(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        events.append("provider:enter")
        try:
            yield bindings[failure]
        finally:
            events.append("provider:exit")

    async def run() -> None:
        with pytest.raises(ValueError, match="provider.*contributions"):
            async with open_plugin_services(
                (
                    AgentPlugin(
                        "provider",
                        provided_services=()
                        if failure == "undeclared"
                        else (collection,),
                        open_services=acquire,
                    ),
                ),
                (),
            ):
                pytest.fail("invalid services opened")

    asyncio.run(run())
    assert events == ["provider:enter", "provider:exit"]


def test_empty_collection_does_not_bypass_declared_dependency_boundary() -> None:
    from caliburn.modules.agent.plugins.composition import open_plugin_services
    from caliburn.modules.agent.plugins.services import ServiceCollection

    collection = ServiceCollection[str]("contributions")

    @asynccontextmanager
    async def acquire(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        dependencies.require(collection)
        yield ()

    async def run() -> None:
        with pytest.raises(ValueError, match="not declared.*contributions"):
            async with open_plugin_services(
                (AgentPlugin("consumer", open_services=acquire),),
                (),
            ):
                pytest.fail("undeclared collection was available")

    asyncio.run(run())


def test_collection_dependency_cycles_are_rejected_before_acquisition() -> None:
    from caliburn.modules.agent.plugins.composition import open_plugin_services
    from caliburn.modules.agent.plugins.services import ServiceCollection

    collection = ServiceCollection[str]("contributions")

    @asynccontextmanager
    async def acquire(
        dependencies: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        pytest.fail("cyclic services were acquired")
        yield ()

    async def run() -> None:
        with pytest.raises(
            ValueError, match="cycle.*first.*second|cycle.*second.*first"
        ):
            async with open_plugin_services(
                (
                    AgentPlugin(
                        "first",
                        required_services=(FIRST,),
                        provided_services=(collection,),
                        open_services=acquire,
                    ),
                    AgentPlugin(
                        "second",
                        required_services=(collection,),
                        provided_services=(FIRST,),
                        open_services=acquire,
                    ),
                ),
                (),
            ):
                pytest.fail("cyclic services opened")

    asyncio.run(run())
