"""有序 PluginStep 直接接入主圖；原生子圖保持自己的排程與保存。"""

from itertools import pairwise
from typing import Any, Literal, get_type_hints

from langchain_core.runnables import Runnable
from langgraph.graph import StateGraph

from caliburn.modules.agent.plugins.contracts import AgentContext, AgentPlugin
from caliburn.modules.agent.plugins.hooks import wrap_plugin_hook
from caliburn.modules.agent.state import AgentInput, AgentOutput, AgentState


def add_plugin_steps(
    graph: StateGraph[AgentState, AgentContext, AgentInput, AgentOutput],
    plugins: tuple[AgentPlugin, ...],
    phase: Literal[
        "on_turn_start", "before_model_step", "after_model_step", "on_turn_end"
    ],
    state_schema: type[Any],
) -> list[str]:
    normal: list[str] = []
    tail: list[str] = []
    for plugin in plugins:
        _validate_segment(plugin.name)
        names: set[str] = set()
        for step in getattr(plugin, phase):
            _validate_segment(step.name)
            if step.name in names:
                raise ValueError(
                    f"Duplicate plugin step: {phase}.{plugin.name}.{step.name}"
                )
            names.add(step.name)
            name = f"{phase}.{plugin.name}.{step.name}"
            if step.input_schema is not None:
                fields = get_type_hints(state_schema, include_extras=True)
                for field, annotation in get_type_hints(
                    step.input_schema, include_extras=True
                ).items():
                    if field not in fields or fields[field] != annotation:
                        raise ValueError(
                            f"Plugin step {name} reads undeclared or conflicting "
                            f"State field: {field}"
                        )
            node = step.node
            if step.wrappers:
                if isinstance(node, Runnable):
                    raise ValueError("Around wrappers require a callable plugin hook")
                node = wrap_plugin_hook(node, step.wrappers)
            graph.add_node(name, node, input_schema=step.input_schema or state_schema)
            (tail if step.run_last else normal).append(name)
    nodes = [*normal, *tail]
    for previous, following in pairwise(nodes):
        graph.add_edge(previous, following)
    return nodes


def _validate_segment(name: str) -> None:
    if not name or not name.replace("_", "").replace("-", "").isalnum():
        raise ValueError(f"Plugin and step names require simple name segments: {name}")
