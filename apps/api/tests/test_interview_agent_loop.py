"""T7:手刻工具迴圈 run_tool_loop(spec §4.2;12-Factor F8 own your control flow)。
迴圈邏輯抽成注入 call_once 的純邏輯 → 離線 TDD(tool_call_id 對回/上限/拼裝);
adapter 只提供真實 OpenAI 呼叫。gotchas(§8.5):tool_call_id 對回、max_iter、限額補問。"""
import json

import pytest

from app.interview.agent_loop import ChatResult, run_tool_loop


def _tc(cid, name, args):
    return {"id": cid, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


class Scripted:
    """call_once 依序吐 assistant messages;記錄每次收到的 messages 與 with_tools。"""
    def __init__(self, msgs):
        self.msgs = list(msgs)
        self.seen = []

    async def __call__(self, messages, with_tools):
        self.seen.append((list(messages), with_tools))
        return self.msgs.pop(0)


async def _dispatch_ok(name, args):
    return {"ok": True, "echo": args}


@pytest.mark.asyncio
async def test_no_tool_calls_returns_text_natural():
    call = Scripted([{"content": "你好,先聊聊你的工作", "tool_calls": []}])
    res = await run_tool_loop(call_once=call, dispatch=_dispatch_ok, messages=[{"role": "user", "content": "hi"}])
    assert isinstance(res, ChatResult)
    assert res.text == "你好,先聊聊你的工作" and res.stopped == "natural"
    assert res.tool_trace == [] and call.seen[0][1] is True   # 首呼帶工具


@pytest.mark.asyncio
async def test_dispatches_tool_then_returns_text():
    call = Scripted([
        {"content": None, "tool_calls": [_tc("call_1", "knowledge_search_occupations", {"query": "測試"})]},
        {"content": "找到了,你是不是做軟體測試?", "tool_calls": []}])
    res = await run_tool_loop(call_once=call, dispatch=_dispatch_ok, messages=[{"role": "user", "content": "hi"}])
    assert res.stopped == "natural" and "軟體測試" in res.text
    assert res.tool_trace[0]["name"] == "knowledge_search_occupations"
    assert res.tool_trace[0]["args"] == {"query": "測試"}


@pytest.mark.asyncio
async def test_parallel_tool_calls_paired_backfill():
    """T13:同輪多 tool_call(parallel_tool_calls)——逐一成對回填,id 各自對回。"""
    call = Scripted([
        {"content": None, "tool_calls": [
            _tc("c1", "knowledge_search_occupations", {"query": "測試"}),
            _tc("c2", "knowledge_occupation_brief", {"ocs_code": "X"})]},
        {"content": "查完了?", "tool_calls": []}])
    res = await run_tool_loop(call_once=call, dispatch=_dispatch_ok, messages=[])
    assert [t["name"] for t in res.tool_trace] == [
        "knowledge_search_occupations", "knowledge_occupation_brief"]
    second_msgs = call.seen[1][0]
    tool_ids = [m["tool_call_id"] for m in second_msgs if m.get("role") == "tool"]
    assert tool_ids == ["c1", "c2"]                    # 成對且保序
    assistant = [m for m in second_msgs if m.get("role") == "assistant"][0]
    assert len(assistant["tool_calls"]) == 2


@pytest.mark.asyncio
async def test_tool_result_appended_with_matching_id():
    call = Scripted([
        {"content": None, "tool_calls": [_tc("call_abc", "knowledge_occupation_brief", {"ocs_code": "X"})]},
        {"content": "好", "tool_calls": []}])
    await run_tool_loop(call_once=call, dispatch=_dispatch_ok, messages=[])
    # 第二次呼叫收到的 messages 應含 assistant(tool_calls) + tool(對回 id)
    second_msgs = call.seen[1][0]
    tool_msg = [m for m in second_msgs if m.get("role") == "tool"][0]
    assert tool_msg["tool_call_id"] == "call_abc"
    assert json.loads(tool_msg["content"])["ok"] is True


@pytest.mark.asyncio
async def test_bad_json_args_defaults_empty():
    call = Scripted([
        {"content": None, "tool_calls": [{"id": "c1", "type": "function",
         "function": {"name": "knowledge_search_occupations", "arguments": "{不是JSON"}}]},
        {"content": "ok", "tool_calls": []}])
    seen_args = {}

    async def disp(name, args):
        seen_args.update({"args": args})
        return {}
    res = await run_tool_loop(call_once=call, dispatch=disp, messages=[])
    assert seen_args["args"] == {}                            # 壞 JSON → 空參數,不炸
    assert res.stopped == "natural"


@pytest.mark.asyncio
async def test_max_iterations_forces_final_answer():
    # 每次都想叫工具 → 撞上限 → 最後一次無工具補問、stopped=tool_limit
    loop_msg = {"content": None, "tool_calls": [_tc("c", "knowledge_search_occupations", {"query": "x"})]}
    final = {"content": "先根據已知回覆:你多久跑一次回歸?", "tool_calls": []}
    call = Scripted([loop_msg, loop_msg, final])
    res = await run_tool_loop(call_once=call, dispatch=_dispatch_ok, messages=[], max_tool_iterations=2)
    assert res.stopped == "tool_limit"
    assert call.seen[-1][1] is False                          # 補問那次不帶工具
    assert "查詢次數已滿" in call.seen[-1][0][-1]["content"]   # 注入了限額提示
    assert len(res.tool_trace) == 2                           # 只 dispatch 了 max_iter 次
