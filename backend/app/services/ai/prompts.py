"""Prompt templates for the ``/ai/*`` endpoints (D28).

One focused, single-purpose template per function, kept together so the model
wording is reviewable in one place and tunable per-function. All templates ask
for JSON-only output (parsed via ``LlmPort.complete_json``).
"""

RECOMMEND_KS = """你是職務分析助手。以下是某任務的官方知識(K)與技能(S)候選清單（出自職能基準）。
請依使用者對這個任務的實際描述，篩選並排序「真正相關」的項目，每項給一句（20字內）理由。
只能從候選清單挑選，不可發明新代碼；不相關的就不要列入。

任務：{task_name}
使用者描述：{note}

知識候選：
{k_list}

技能候選：
{s_list}

只輸出 JSON（不要任何其他文字）：
{{
  "knowledge": [{{"code": "K01", "reason": "一句理由"}}],
  "skills": [{{"code": "S01", "reason": "一句理由"}}]
}}"""


DRAFT_OP = """你是職務分析助手。請依使用者對這個任務的實際描述，撰寫貼合其情境的「工作產出(outputs)」與「衡量指標／行為指標(indicators)」。
以下官方參考（出自職能基準）僅供參照與用語對齊，請以使用者描述為主進行客製改寫，不要照抄。
產出請是具體可交付的成果；指標請是可觀察、可衡量的行為或標準。

任務：{task_name}
使用者描述：{note}

官方產出參考：
{outputs_ref}

官方行為／活動參考：
{indicators_ref}

只輸出 JSON（不要任何其他文字）：
{{"outputs": ["產出1", "產出2"], "indicators": ["指標1"]}}"""
