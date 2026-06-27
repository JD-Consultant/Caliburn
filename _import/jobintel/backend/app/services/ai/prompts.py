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


EXTRACT_TASKS = """你是職務分析助手。以下是員工的自述（intake），以及一份出自職能基準的候選任務清單（每列為「- 代碼 任務名稱」）。
請判斷此員工實際執行的是哪些候選任務（回傳其代碼），並把自述中明確提到、但不在候選清單內的任務，提為自訂候選（只給名稱）。
suggested_task_ids 只能從候選清單的代碼挑選，不可發明新代碼。

員工自述：{intake}

候選任務清單：
{candidate_list}

只輸出 JSON（不要任何其他文字）：
{{"suggested_task_ids": ["<代碼>"], "custom_candidates": ["任務名稱"]}}"""


STRUCTURE_TASK = """你是職務分析助手。請把以下一句話的自由描述，整理成一個精煉、正式的「任務名稱」，並建議一個合適的「職責(unit)」分組名稱。

自由描述：{description}
職類參考（OCS 代碼，僅供參考）：{occupation_context}

只輸出 JSON（不要任何其他文字）：
{{"task_name": "精煉後的任務名稱", "unit_suggestion": "建議的職責分組名稱"}}"""


CLARIFY = """你是職務分析助手。以下是一個任務，以及使用者目前（可能過於簡略）的補充說明。
若此說明不足以據以撰寫工作產出／衡量指標，請提出「一個」簡短的追問問題（繁體中文）；若已足夠，請回傳 null。

任務：{task}
目前說明：{note}

只輸出 JSON（不要任何其他文字）：
{{"question": "一句追問問題"}} 或 {{"question": null}}"""
