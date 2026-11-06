"""顧問 Bundle 的公開組裝入口及固定開場。"""

from collections.abc import Mapping

from caliburn.bundles.consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin

OPENING_TEXT = (
    "這裡會透過訪談，逐步理解您的實際工作並整理職務說明書。"
    "您不需要先學會撰寫，也不必一次說完。不確定的地方可以直接說明。\n\n"
    "請先說說您目前擔任什麼職位，主要負責哪些工作？"
    "先說工作大項就好，可以用自己的說法，從平常大家會找您處理的事情開始。"
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    """用空設定載入顧問角色與內容指引。"""
    return AgentBundle(
        plugins=(
            AgentPlugin(
                name="consultant",
                prompt_sections=(CONSULTANT_INSTRUCTIONS,),
            ),
        )
    )
