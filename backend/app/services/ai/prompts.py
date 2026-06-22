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
