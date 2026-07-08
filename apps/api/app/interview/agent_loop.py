"""手刻工具迴圈(v2;ADR 0027 §4.2、spec、12-Factor F8 own your control flow)。

顧問 agent 的 while 迴圈抽成**注入 call_once 的純邏輯**——離線可測(tool_call_id 對回、
上限、拼裝);adapter 提供真實 OpenAI 呼叫。**顧問只讀不寫**(工具皆 READ);
撞上限→補問一次(無工具)拿收斂文字(OpenAI GPT-4.1 指南:給明確 stop)。
"""
import hashlib
import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_LIMIT_NUDGE = "查詢次數已滿,請根據已知資訊直接回覆並提出下一個問題。"


@dataclass
class ChatResult:
    text: str
    tool_trace: list[dict] = field(default_factory=list)   # [{name,args,result_digest}]
    stopped: str = "natural"                                # natural | tool_limit


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True)
                          .encode()).hexdigest()[:12]


async def run_tool_loop(*, call_once, dispatch, messages: list[dict],
                        max_tool_iterations: int = 5) -> ChatResult:
    """call_once(messages, with_tools:bool) -> {"content": str|None, "tool_calls": [...]}
    (tool_calls 形:{"id","type","function":{"name","arguments"}});
    dispatch(name, args:dict) -> dict(工具結果)。輸入 messages 不變(內部複製)。"""
    msgs = list(messages)
    trace: list[dict] = []
    for _ in range(max_tool_iterations):
        msg = await call_once(msgs, True)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return ChatResult(msg.get("content") or "", trace, "natural")
        # 先把 assistant 的 tool_calls 回合放回(provider 要求成對),再逐一附工具結果
        msgs.append({"role": "assistant", "content": msg.get("content"),
                     "tool_calls": tool_calls})
        for tc in tool_calls:
            name = tc["function"]["name"]
            raw = tc["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                logger.warning("tool args 非法 JSON(%s):%.80s", name, raw)
                args = {}
            result = await dispatch(name, args)
            msgs.append({"role": "tool", "tool_call_id": tc["id"],   # 對回 id(§8.5)
                         "content": json.dumps(result, ensure_ascii=False)})
            trace.append({"name": name, "args": args, "result_digest": _digest(result)})
    # 撞上限:補問一次(不帶工具)逼出收斂文字
    msgs.append({"role": "user", "content": _LIMIT_NUDGE})
    final = await call_once(msgs, False)
    return ChatResult(final.get("content") or "", trace, "tool_limit")
