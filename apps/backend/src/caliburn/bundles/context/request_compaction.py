"""普通請求計數與原生壓縮方法，不依賴 Graph 或業務模組。"""

from typing import cast

from openai import APIError, AsyncOpenAI
from openai.types.responses import CompactedResponse
from openai.types.responses.input_token_count_params import InputTokenCountParams
from openai.types.responses.response_compact_params import ResponseCompactParams
from openai.types.responses.response_create_params import ResponseCreateParamsBase
from openai.types.responses.response_input_param import ResponseInputParam

_COUNT_FIELDS = {
    "model",
    "input",
    "instructions",
    "tools",
    "tool_choice",
    "parallel_tool_calls",
    "reasoning",
    "text",
    "personality",
    "truncation",
}


async def compact_request(
    client: AsyncOpenAI,
    request: ResponseCreateParamsBase,
    *,
    threshold_tokens: int,
) -> CompactedResponse | None:
    """未達門檻回 None；成功回 SDK 完整原件，失敗傳出且不修改 request。

    接受已組裝的 Core request，其 service_tier 固定 default。client 由
    呼叫者管理；沿 Core 關閉 SDK 隱式重試。只投影 count 支援的欄位，
    input 與原生 items 原樣送出，包含不透明推理與工具配對。
    """
    client = client.with_options(max_retries=0)
    if await count_request(client, request) < threshold_tokens:
        return None
    compact_parameters = cast(
        ResponseCompactParams,
        {
            key: value
            for key, value in request.items()
            if key in {"model", "input", "instructions", "service_tier"}
        },
    )
    try:
        compacted = await client.responses.compact(**compact_parameters)
    except APIError:
        raise RuntimeError("Model provider compaction failed") from None
    if not compacted.output:
        raise ValueError("Compaction returned an empty window")
    return compacted


def compaction_input(response: CompactedResponse) -> ResponseInputParam:
    """採用已保存的回應時，依序取其完整窗口，不改寫或篩除項目。"""
    # SDK 把合法 user/input_text 項套入較窄的 output 型別；保留所有實際
    # 欄位，避免後續序列化的型別警告包含原話。不重新驗證或篩選窗口。
    return cast(
        ResponseInputParam,
        [
            item.model_dump(mode="json", exclude_unset=True, warnings=False)
            for item in response.output
        ],
    )


async def count_request(client: AsyncOpenAI, request: ResponseCreateParamsBase) -> int:
    """精確計數已組裝請求；API 失敗傳出，不以零或字元數代替。"""
    parameters = cast(
        InputTokenCountParams,
        {key: value for key, value in request.items() if key in _COUNT_FIELDS},
    )
    try:
        count = await client.with_options(max_retries=0).responses.input_tokens.count(
            **parameters
        )
    except APIError:
        raise RuntimeError("Model provider input token count failed") from None
    if count.input_tokens < 0:
        raise ValueError("Input token count cannot be negative")
    return count.input_tokens
