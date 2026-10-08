"""一般日誌只輸出安全中繼資料；正文沿原生 checkpoint 的受控查閱。

沿標準 logging 組裝有界 queue，避免 stdout 慢寫卡住 async 工作。
丟棄與輸出失敗會累計；日誌不參與業務保存、重試或結果裁決。
"""

import io
import json
import logging
import logging.config
import math
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import QueueHandler, QueueListener
from queue import Empty, Full, Queue
from typing import TextIO
from uuid import UUID

QUEUE_CAPACITY = 1024
MAX_FIELD_LENGTH = 256
_EVENT = re.compile(r"[a-z][a-z0-9]*(?:[_.][a-z0-9]+)+\Z")
_FIELDS = frozenset(
    {
        "job_file_id",
        "execution_id",
        "execution_kind",
        "http_request_id",
        "request_id",
        "attempt_id",
        "provider_request_id",
        "role",
        "operation",
        "tool_call_id",
        "failure_kind",
        "http_status",
        "provider_code",
        "duration_ms",
        "outcome",
        "app_version",
        "log_level",
        "method",
        "route",
        "status",
        "writer_id",
    }
)
_CONTEXT: ContextVar[dict[str, object] | None] = ContextVar("caliburn_log_context", default=None)
_runtime: LoggingRuntime | None = None


@contextmanager
def bind_log_context(**fields: object) -> Iterator[None]:
    """依 async 工作綁定既有身分，離開或取消時恢復外層 context。"""
    token = _CONTEXT.set(
        {**(_CONTEXT.get() or {}), **{k: v for k, v in fields.items() if k in _FIELDS}}
    )
    try:
        yield
    finally:
        _CONTEXT.reset(token)


class SafeJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = {**(_CONTEXT.get() or {}), **record.__dict__}
        event = fields.get("event", record.msg)
        if not (
            record.name.startswith("caliburn.")
            and isinstance(event, str)
            and len(event) <= 80
            and _EVENT.fullmatch(event)
        ):
            event = "application.log" if record.name.startswith("caliburn.") else "framework.log"
        result: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "module": record.name[:MAX_FIELD_LENGTH],
            "event": event,
        }
        truncated = []
        for key in sorted(_FIELDS):
            if key not in fields:
                continue
            value = fields[key]
            if isinstance(value, UUID):
                value = str(value)
            if isinstance(value, str):
                if len(value) > MAX_FIELD_LENGTH:
                    value = value[: MAX_FIELD_LENGTH - 1] + "…"
                    truncated.append(key)
                result[key] = value
            elif value is None or isinstance(value, (bool, int)):
                result[key] = value
            elif isinstance(value, float) and math.isfinite(value):
                result[key] = value
        if record.name == "uvicorn.access":
            result["event"] = "http.access"
            # Uvicorn 的原始 args 含 client 與完整 URL；只取固定位置的 status。
            if isinstance(record.args, tuple) and len(record.args) == 5:
                status = record.args[4]
                if isinstance(status, int):
                    result["http_status"] = status
        if record.exc_info and record.exc_info[0] is not None:
            result.setdefault("failure_kind", record.exc_info[0].__name__[:MAX_FIELD_LENGTH])
        if truncated:
            result["truncated_fields"] = truncated
        return json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


class _SafeStreamHandler(logging.Handler):
    output_failures = 0

    def __init__(self, stream: TextIO) -> None:
        super().__init__()
        self._memory_stream = stream if isinstance(stream, io.StringIO) else None
        self._output_fd: int | None = None
        try:
            self._output_fd = os.dup(stream.fileno())
            os.set_inheritable(self._output_fd, False)
        except OSError, ValueError:
            # 只有純記憶體 StringIO 可沿原介面；未知輸出不可退回全域緩衝鎖。
            if self._output_fd is not None:
                os.close(self._output_fd)
                self._output_fd = None

    def handle(self, record: logging.LogRecord) -> bool:
        # 此 sink 僅由單一 listener 呼叫；不持有 logging.shutdown 也會取得的鎖。
        self.emit(record)
        return True

    def emit(self, record: logging.LogRecord) -> None:
        if self.output_failures:
            # queue 中只有已遮蔽的 JSON；恢復輸出後明示先前已遺失的事件數。
            payload = json.loads(record.getMessage())
            payload["logging_output_failures"] = self.output_failures
            record.msg = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        try:
            if self._memory_stream is not None:
                self._memory_stream.write(record.getMessage() + "\n")
                return
            if self._output_fd is None:
                raise OSError("Log output is unavailable")
            # 自有 descriptor 不經全域 stdout 的 BufferedWriter；程序收尾不搶其鎖。
            remaining = memoryview((record.getMessage() + "\n").encode("ascii"))
            while remaining:
                written = os.write(self._output_fd, remaining)
                if written <= 0:
                    raise OSError("Log output made no progress")
                remaining = remaining[written:]
        except Exception:
            self.handleError(record)

    def release_output(self) -> None:
        # 只有 listener 退出後關自己的 descriptor，主執行緒不等阻塞中的 raw write。
        if self._output_fd is not None:
            try:
                os.close(self._output_fd)
            except OSError:
                self.output_failures += 1
            self._output_fd = None

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        # 標準 handleError 會 dump 原 record 與 traceback，這裡只記缺失計數。
        self.output_failures += 1


class _SafeQueueHandler(QueueHandler):
    queue: Queue[logging.LogRecord]
    dropped_records = 0
    accepting = True

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        # 在 producer 取得 context 並遮蔽，listener 不重新讀自己的 contextvars。
        payload = json.loads(self.format(record))
        if self.dropped_records:
            payload["logging_dropped_records"] = self.dropped_records
        return logging.makeLogRecord(
            {
                "msg": json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
                "args": (),
                "levelno": record.levelno,
                "levelname": record.levelname,
            }
        )

    def enqueue(self, record: logging.LogRecord) -> None:
        if not self.accepting:
            return
        try:
            self.queue.put_nowait(record)
        except Full:
            self.dropped_records += 1

    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        self.dropped_records += 1


class _BoundedQueueListener(QueueListener):
    def __init__(self, queue: Queue[logging.LogRecord], sink: _SafeStreamHandler) -> None:
        super().__init__(queue, sink)
        self.sink = sink

    def dequeue(self, block: bool) -> logging.LogRecord:
        record = super().dequeue(block)
        # 標準 QueueListener 的終止標記為 None；取到時所有先前寫入已結束。
        if record is None:
            self.sink.release_output()
        return record

    def stop_with_timeout(self, timeout: float) -> bool:
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout)
        complete = not thread.is_alive()
        if complete:
            self._thread = None
        return complete


class LoggingRuntime:
    """程序組裝持有此 handle；重複組裝先關閉舊 listener。"""

    def __init__(
        self, handler: _SafeQueueHandler, listener: _BoundedQueueListener, sink: _SafeStreamHandler
    ) -> None:
        self.handler = handler
        self.listener = listener
        self.sink = sink
        self.closed = False

    @property
    def dropped_records(self) -> int:
        return self.handler.dropped_records

    @property
    def output_failures(self) -> int:
        return self.sink.output_failures

    def close(self, timeout: float = 1.0) -> bool:
        """最多等待指定秒數；慢 sink 留在 daemon，不拖住程序工作收尾。"""
        if not self.closed:
            self.handler.acquire()
            try:
                self.closed = True
                self.handler.accepting = False
                try:
                    self.listener.enqueue_sentinel()
                except Full:
                    # 關閉時 queue 已滿，丟棄一筆以確保終止標記可入列。
                    try:
                        self.handler.queue.get_nowait()
                        self.handler.queue.task_done()
                        self.handler.dropped_records += 1
                    except Empty:
                        pass
                    self.listener.enqueue_sentinel()
            finally:
                self.handler.release()
        return self.listener.stop_with_timeout(max(0.0, timeout))


def configure_logging(level: str | None = None) -> LoggingRuntime:
    """只由程序入口呼叫；create_app／TestClient 不改全域 logging。"""
    global _runtime
    selected = (level or os.environ.get("CALIBURN_LOG_LEVEL", "INFO")).upper()
    if selected not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("CALIBURN_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
    if _runtime is not None:
        _runtime.close()
    queue: Queue[logging.LogRecord] = Queue(maxsize=QUEUE_CAPACITY)
    handler = _SafeQueueHandler(queue)
    handler.setFormatter(SafeJsonFormatter())
    sink = _SafeStreamHandler(sys.stdout)
    listener = _BoundedQueueListener(queue, sink)
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {"safe_json": {"()": lambda: handler}},
            "root": {"level": selected, "handlers": ["safe_json"]},
            "loggers": {
                name: {"handlers": [], "level": "NOTSET", "propagate": True}
                for name in ("caliburn", "uvicorn", "uvicorn.error", "uvicorn.access")
            },
        }
    )
    listener.start()
    _runtime = LoggingRuntime(handler, listener, sink)
    return _runtime
