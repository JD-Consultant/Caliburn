"""服務依賴決定取得順序；Hook 仍依插件配置順序組合。"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from graphlib import CycleError, TopologicalSorter
from typing import Any, cast

from caliburn.modules.agent.plugins.contracts import (
    AgentContext,
    AgentPlugin,
)
from caliburn.modules.agent.plugins.services import (
    PluginServices,
    ServiceBinding,
    ServiceCollection,
    ServiceKey,
)


def validate_plugin_composition(plugins: tuple[AgentPlugin, ...]) -> None:
    """核對選後插件前提與各階段收尾，不改服務或流程的宣告順序。"""
    names = {plugin.name for plugin in plugins}
    for plugin in plugins:
        for required in plugin.required_plugins:
            if required not in names:
                raise ValueError(
                    f"Plugin {plugin.name} requires missing plugin {required}"
                )
    for phase in (
        "on_turn_start",
        "before_model_step",
        "after_model_step",
        "on_turn_end",
    ):
        tail_owner: str | None = None
        for plugin in plugins:
            has_tail = False
            for step in getattr(plugin, phase):
                if step.run_last:
                    if tail_owner is not None and tail_owner != plugin.name:
                        raise ValueError(
                            f"Multiple tail owners for {phase}: "
                            f"{tail_owner} and {plugin.name}"
                        )
                    tail_owner = plugin.name
                    has_tail = True
                elif has_tail:
                    raise ValueError(
                        f"Normal step after tail in {phase} for plugin "
                        f"{plugin.name}: {step.name}"
                    )


def _dependency_order(
    plugins: tuple[AgentPlugin, ...], external: tuple[ServiceKey[Any], ...]
) -> tuple[str, ...]:
    names: set[str] = set()
    keys: dict[str, ServiceKey[Any]] = {}
    owners: dict[ServiceKey[Any], list[str | None]] = {}
    all_keys = list(external)
    for plugin in plugins:
        all_keys.extend(plugin.required_services)
        all_keys.extend(plugin.provided_services)
    for key in all_keys:
        if key.name in keys and keys[key.name] is not key:
            raise ValueError(f"Ambiguous service key name: {key.name}")
        keys[key.name] = key
    providers: list[tuple[str | None, tuple[ServiceKey[Any], ...]]] = [(None, external)]
    for plugin in plugins:
        providers.append((plugin.name, plugin.provided_services))
    for owner, provided in providers:
        for key in provided:
            key_owners = owners.setdefault(key, [])
            if key_owners and (
                not isinstance(key, ServiceCollection) or owner in key_owners
            ):
                raise ValueError(
                    f"Duplicate provider for service {key.name}: "
                    f"{key_owners} and {owner}"
                )
            key_owners.append(owner)
    graph: dict[str, set[str]] = {}
    for plugin in plugins:
        if plugin.name in names:
            raise ValueError(f"Duplicate plugin name: {plugin.name}")
        names.add(plugin.name)
        predecessors: set[str] = set()
        for key in plugin.required_services:
            if key not in owners and not isinstance(key, ServiceCollection):
                raise ValueError(
                    f"Plugin {plugin.name} requires missing service {key.name}"
                )
            predecessors.update(
                owner for owner in owners.get(key, ()) if owner is not None
            )
        graph[plugin.name] = predecessors
    try:
        sorter = TopologicalSorter(graph)
        sorter.prepare()
        position = {plugin.name: index for index, plugin in enumerate(plugins)}
        ordered: list[str] = []
        while sorter.is_active():
            ready = sorted(sorter.get_ready(), key=position.__getitem__)
            ordered.extend(ready)
            sorter.done(*ready)
        return tuple(ordered)
    except CycleError as error:
        raise ValueError(
            f"Plugin dependency cycle: {' -> '.join(error.args[1])}"
        ) from error


def _service_values(
    owner: str,
    declared: tuple[ServiceKey[Any], ...],
    bindings: tuple[ServiceBinding[Any], ...],
) -> dict[ServiceKey[Any], object]:
    values: dict[ServiceKey[Any], object] = {}
    for binding in bindings:
        if binding.key in values:
            raise ValueError(f"{owner} supplied duplicate service {binding.key.name}")
        if binding.key not in declared:
            raise ValueError(f"{owner} supplied undeclared service {binding.key.name}")
        values[binding.key] = binding.value
    missing = [key.name for key in declared if key not in values]
    if missing:
        raise ValueError(f"{owner} did not supply services: {', '.join(missing)}")
    return values


@asynccontextmanager
async def open_plugin_services(
    plugins: tuple[AgentPlugin, ...],
    external: tuple[ServiceBinding[Any], ...],
) -> AsyncIterator[AgentContext]:
    validate_plugin_composition(plugins)
    keys = tuple(binding.key for binding in external)
    order = _dependency_order(plugins, keys)
    by_name = {plugin.name: plugin for plugin in plugins}
    positions = {plugin.name: index for index, plugin in enumerate(plugins)}
    declared = (
        *keys,
        *(key for plugin in plugins for key in plugin.required_services),
        *(key for plugin in plugins for key in plugin.provided_services),
    )
    collections: dict[ServiceCollection[Any], dict[int, tuple[Any, ...]]] = {
        key: {} for key in declared if isinstance(key, ServiceCollection)
    }
    services: dict[ServiceKey[Any], object] = {key: () for key in collections}

    def add_values(position: int, values: dict[ServiceKey[Any], object]) -> None:
        for key, value in values.items():
            if isinstance(key, ServiceCollection):
                collections[key][position] = cast(tuple[Any, ...], value)
                services[key] = tuple(
                    item
                    for _, items in sorted(collections[key].items())
                    for item in items
                )
            else:
                services[key] = value

    add_values(-1, _service_values("Host", keys, external))
    async with AsyncExitStack() as stack:
        for name in order:
            plugin = by_name[name]
            bindings: tuple[ServiceBinding[Any], ...] = ()
            if plugin.open_services is not None:
                dependencies = PluginServices(
                    {key: services[key] for key in plugin.required_services}
                )
                bindings = await stack.enter_async_context(
                    plugin.open_services(dependencies)
                )
            add_values(
                positions[name],
                _service_values(f"Plugin {name}", plugin.provided_services, bindings),
            )
        yield AgentContext(services=PluginServices(services))
