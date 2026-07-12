"""(T6 搬家後轉口)setup/get_tracer 已搬 app/observability.py;
本檔只剩 graph 專用 traced_node,隨 authoring 整包退場(T12)。"""
import functools

from opentelemetry.trace import Status, StatusCode
from langgraph.errors import GraphBubbleUp

from app.observability import get_tracer, setup_tracing  # noqa: F401(轉口)


def traced_node(name: str):
    """包 async graph node 成一個 span；interrupt（GraphBubbleUp）視為正常控制流不記 error。"""
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(state, config):
            with get_tracer().start_as_current_span(f"node.{name}") as span:
                span.set_attribute("caliburn.node", name)
                step = state.get("current_step") if isinstance(state, dict) else None
                if step:
                    span.set_attribute("caliburn.current_step", step)
                exc_to_raise = None
                try:
                    return await fn(state, config)
                except GraphBubbleUp as exc:
                    # interrupt / 正常暫停，非錯誤；捕捉但不記 error
                    exc_to_raise = exc
                except Exception as exc:       # noqa: BLE001
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    exc_to_raise = exc
            # 在 span context 外才 raise，避免 span 自動記錄為 error
            if exc_to_raise is not None:
                raise exc_to_raise
        return wrapper
    return deco
