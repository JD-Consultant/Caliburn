"""Agent 執行錯誤的 HTTP 對應。"""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException

from caliburn.modules.agent.application.errors import (
    AgentUnavailable,
    TurnConflict,
    TurnNotFound,
)


@contextmanager
def http_errors() -> Iterator[None]:
    try:
        yield
    except TurnNotFound as error:
        raise HTTPException(404, detail={"code": "agent_turn_not_found"}) from error
    except TurnConflict as error:
        raise HTTPException(409, detail={"code": "agent_turn_conflict"}) from error
    except AgentUnavailable as error:
        raise HTTPException(503, detail={"code": "agent_unavailable"}) from error
