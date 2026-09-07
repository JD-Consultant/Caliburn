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


@tool(response_format='content_and_artifact')
def request_memory_consolidation() -> tuple[str, dict]:
    """通知背景整理有實質進展的訪談，不在這裡執行整理或更新記憶。

    新辨識的工作範圍、案例中本人做法、成果與完成判準、頻率、條件、
    例外、責任交接或專業判斷，都可能是值得整理的新資訊；這些是例子，
    不是必填清單。類似案例補充不同條件也算進展，不必產生新任務。
    具體工作資料的明確更正也需要保存，例如期限、頻率或案例條件，
    即使共同工作模式不變、只改一句話，也不能略過。已核實Memory
    過時時依repair_memory指引修補；若這次更正尚未經成功修補保留，
    在本輪答覆前呼叫本工具，不只在回答中採用新值。
    零碎補充可累積成段；轉向另一工作或回顧收尾前，若有尚未通知的
    實質進展，就呼叫本工具。仍有未知或衝突也可如實整理，不必等整項
    工作問完、填滿Task／OPKS，或為通知而繼續追問。
    純重述、寒暄或只有話題切換不需通知；已通知且沒有新進展，不重複
    呼叫。不要每輪例行通知，也不需重寫詳記、候選、理由或填入ID。
    回傳只代表收到請求，不代表整理完成。繼續完成本輪顧問答覆，
    不等待背景完成。
    """
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
