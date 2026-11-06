"""Adapter 邊界的一次安全失敗紀錄；部署 owner 決定 handler。"""

from dataclasses import asdict
from logging import Logger

from langgraph.runtime import ExecutionInfo
from openai.types.responses import Response


def log_failure(
    logger: Logger,
    *,
    event: str,
    error: Exception,
    execution: ExecutionInfo | None,
    response: Response | None = None,
) -> None:
    fields: dict[str, object] = {
        "event": event,
        "error_type": type(error).__name__,
        "execution": asdict(execution) if execution is not None else None,
    }
    if response is not None:
        fields.update(response_id=response.id, response_status=response.status)
    try:
        logger.error("Agent execution step failed", extra=fields)
    except Exception:
        # 診斷輸出不能取代原錯誤、影響保存或觸發重送。
        pass
