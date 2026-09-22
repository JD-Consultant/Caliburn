"""Pure background request receipt, not a background job or Memory write.

The official ToolNode/Saver persists content+artifact. A later application
dispatcher consumes the canonical safe-turn projection; this tool never waits
for B1/B2 and never reports that consolidation completed.
https://docs.langchain.com/oss/python/langchain/messages#tool-message
"""
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool


REQUEST_TOOL_NAME = 'request_memory_consolidation'
REQUEST_KIND = 'memory_consolidation_requested'


@tool(response_format='content_and_artifact', description=(
    "通知符合系統Memory actions條件的累積訪談進展；本工具不執行整理，也不修補已發布Memory。\n"
    "\n"
    "已有核實過時Memory時先依repair_memory契約處理；不要以本工具取代適用但尚未嘗試的修補。\n"
    "不需填參數、ID、理由、詳記或候選。回傳只代表收到請求，由系統在本輪安全結束後評估排程，不代表已保存。繼續顧問答覆，不等待背景完成。"
))
def request_memory_consolidation() -> tuple[str, dict]:
    """Return a durable request receipt without starting background work."""
    return (
        '收到整理請求；系統會在本輪安全結束後評估排程。'
        '背景尚未執行，記憶尚未更新；請繼續完成本輪答覆。',
        {'kind': REQUEST_KIND},
    )


def has_saved_request(messages) -> bool:
    """Require one real, unambiguous call/result pair, not text or bare metadata."""
    calls = [(i, call) for i, message in enumerate(messages) if isinstance(message, AIMessage)
             for call in message.tool_calls]
    for index, call in calls:
        if call.get('name') != REQUEST_TOOL_NAME or not call.get('id'):
            continue
        if sum(c.get('id') == call['id'] for _, c in calls) != 1:
            continue
        results = [(i, m) for i, m in enumerate(messages)
                   if isinstance(m, ToolMessage) and m.tool_call_id == call['id']]
        if len(results) != 1:
            continue
        result_index, result = results[0]
        if (result_index > index and result.name == REQUEST_TOOL_NAME
                and result.status == 'success' and result.artifact == {'kind': REQUEST_KIND}):
            return True
    return False
