"""合成一次父圖 TypedDict；保存與 reducer 仍由 LangGraph 擁有。"""

from collections.abc import Callable
from typing import Any, TypedDict, cast, get_type_hints, is_typeddict

from caliburn.modules.agent.plugins.contracts import AgentPlugin
from caliburn.modules.agent.state import AgentState

CORE_FIELDS = frozenset(get_type_hints(AgentState))
RESERVED_FIELDS = CORE_FIELDS | {"messages"}


def compose_state_schema(plugins: tuple[AgentPlugin, ...]) -> type[Any]:
    fields = get_type_hints(AgentState, include_extras=True)
    for plugin in plugins:
        if plugin.state_schema is None:
            continue
        if not is_typeddict(plugin.state_schema):
            raise ValueError(f"Plugin {plugin.name} requires a TypedDict state_schema")
        declared = get_type_hints(plugin.state_schema, include_extras=True)
        for name, annotation in declared.items():
            if name in RESERVED_FIELDS:
                raise ValueError(
                    f"Plugin {plugin.name} declared reserved State field: {name}"
                )
            if name in fields and fields[name] != annotation:
                raise ValueError(f"Conflicting plugin State field: {name}")
            fields[name] = annotation
    # 欄位來自已驗證 TypedDict，functional API 保留 Annotated reducer。
    factory = cast(Callable[..., type[Any]], TypedDict)
    return factory("ComposedAgentState", fields, total=False)
