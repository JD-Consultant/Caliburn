"""Host 在正式輪次完成後得到通知；觀察者失敗不重跑已完成輪。"""

import asyncio
from uuid import UUID, uuid4

import httpx2
import pytest

from caliburn.modules.agent.application.agent_service import AgentService
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    offline_client,
    open_test_agent,
    response_events,
    response_payload,
    sse_response,
)


def test_completion_notification_runs_after_saved_end_and_only_once() -> None:
    async def run() -> None:
        notices: list[tuple[UUID, UUID]] = []
        completed = asyncio.Event()
        workspace_id, turn_id = uuid4(), uuid4()

        async def ensure_workspace(workspace_id: UUID) -> None:
            return None

        def on_completed(workspace_id: UUID, turn_id: UUID) -> None:
            notices.append((workspace_id, turn_id))
            completed.set()

        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            )
        ) as client:
            async with open_test_agent(client=client) as agent:
                service = AgentService(
                    agent,
                    ensure_workspace=ensure_workspace,
                    on_turn_completed=on_completed,
                )
                try:
                    await service.submit_turn(
                        workspace_id=workspace_id, turn_id=turn_id, input="合成訪談"
                    )
                    async with asyncio.timeout(5):
                        await completed.wait()
                    assert (
                        await service.get_turn(
                            workspace_id=workspace_id, turn_id=turn_id
                        )
                    ).status == "completed"
                    repeated = await service.submit_turn(
                        workspace_id=workspace_id, turn_id=turn_id, input="合成訪談"
                    )
                    assert not repeated.created
                    assert notices == [(workspace_id, turn_id)]
                finally:
                    await service.aclose()

    asyncio.run(run())


def test_failed_completion_observer_preserves_completed_turn() -> None:
    async def run() -> None:
        workspace_id, turn_id = uuid4(), uuid4()
        observed = asyncio.Event()

        async def ensure_workspace(workspace_id: UUID) -> None:
            return None

        def on_completed(workspace_id: UUID, turn_id: UUID) -> None:
            observed.set()
            raise RuntimeError("private-observer-detail")

        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            )
        ) as client:
            async with open_test_agent(client=client) as agent:
                service = AgentService(
                    agent,
                    ensure_workspace=ensure_workspace,
                    on_turn_completed=on_completed,
                )
                try:
                    await service.submit_turn(
                        workspace_id=workspace_id, turn_id=turn_id, input="合成訪談"
                    )
                    async with asyncio.timeout(5):
                        await observed.wait()
                    assert (
                        await service.get_turn(
                            workspace_id=workspace_id, turn_id=turn_id
                        )
                    ).status == "completed"
                finally:
                    await service.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("response_status", ["failed", "incomplete"])
def test_unsuccessful_model_response_does_not_notify(response_status: str) -> None:
    async def run() -> None:
        notices: list[tuple[UUID, UUID]] = []
        workspace_id, turn_id = uuid4(), uuid4()

        async def ensure_workspace(workspace_id: UUID) -> None:
            return None

        async with (
            offline_client(
                httpx2.MockTransport(
                    lambda _: sse_response(
                        EventStream(
                            response_events(response_payload(status=response_status))
                        )
                    )
                )
            ) as client,
            open_test_agent(client=client) as agent,
        ):
            service = AgentService(
                agent,
                ensure_workspace=ensure_workspace,
                on_turn_completed=lambda w, t: notices.append((w, t)),
            )
            try:
                await service.submit_turn(
                    workspace_id=workspace_id, turn_id=turn_id, input="未完成訪談"
                )
                async with asyncio.timeout(5):
                    while (
                        await service.get_turn(
                            workspace_id=workspace_id, turn_id=turn_id
                        )
                    ).status == "running":
                        await asyncio.sleep(0.01)
                assert not notices
            finally:
                await service.aclose()

    asyncio.run(run())
