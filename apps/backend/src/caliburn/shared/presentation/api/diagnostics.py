"""HTTP 失敗診斷只記代碼位置，不記輸入、SQL 或例外訊息。"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from traceback import extract_tb
from uuid import uuid4

from fastapi import Request

logger = logging.getLogger(__name__)


def log_http_failure(
    request: Request, error: Exception, *, status_code: int = 500
) -> str:
    request_id = uuid4().hex
    route = request.scope.get("route")
    payload = json.dumps(
        {
            "event": "http_request_failed",
            "timestamp": datetime.now(UTC).isoformat(),
            "level": "error",
            "module": __name__,
            "request_id": request_id,
            "method": request.method,
            "route": getattr(route, "path", "unmatched"),
            "status_code": status_code,
            "error_type": type(error).__name__,
            "frames": [
                {
                    "file": Path(frame.filename).name,
                    "function": frame.name,
                    "line": frame.lineno,
                }
                for frame in extract_tb(error.__traceback__)
            ],
        }
    )
    try:
        logger.error(payload)
    except Exception:
        # 日誌目的地故障不可覆蓋已知提交事實；此處不能遞迴記錄。
        pass
    return request_id
