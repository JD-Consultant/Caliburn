"""普通 Python around factory 的明示組合；不自行執行圖或重收材料。"""

from caliburn.modules.agent.plugins.contracts import PluginHook, PluginWrapper


def wrap_plugin_hook[StateT](
    hook: PluginHook[StateT], wrappers: tuple[PluginWrapper[StateT], ...]
) -> PluginHook[StateT]:
    """第一個 wrapper 最外層；局部 update 的合併由 wrapper 明示負責。"""
    for wrapper in reversed(wrappers):
        hook = wrapper(hook)
    return hook
