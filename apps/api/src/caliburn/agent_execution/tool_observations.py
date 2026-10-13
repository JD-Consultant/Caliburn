"""Typed tool observations from retained native originals, without invoking a Graph."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.native_checkpoint_reads import read_native_records
from caliburn.agent_execution.native_observations import collect_steps, collect_tool_calls


@dataclass(frozen=True, slots=True)
class ToolObservation:
    request_id: UUID
    response_id: str
    call_id: str
    name: str
    arguments: str
    result_state: Literal["recorded", "not_recorded"]
    output: str | None


async def read_tool_observations(
    session: AsyncSession, *, thread_id: str
) -> tuple[ToolObservation, ...]:
    records = await read_native_records(
        session,
        threads={thread_id: ""},
        channels=(
            "request_id",
            "request_snapshot",
            "response_snapshot",
            "tool_results",
            "operation_seed",
            "messages",
            "call",
            "output",
            "operation_id",
        ),
        include_subgraphs=True,
    )
    observations = []
    for call in collect_tool_calls(collect_steps(records)):
        output = call["output"]
        if output is not None and not isinstance(output, str):
            raise ValueError("A saved tool output must be text")
        if not all(
            isinstance(call[key], str) for key in ("response_id", "call_id", "name", "arguments")
        ):
            raise ValueError("A saved function call must contain text identities and arguments")
        observations.append(
            ToolObservation(
                request_id=UUID(str(call["request_id"])),
                response_id=call["response_id"],
                call_id=call["call_id"],
                name=call["name"],
                arguments=call["arguments"],
                result_state="recorded" if call["result_state"] == "recorded" else "not_recorded",
                output=output,
            )
        )
    return tuple(observations)
