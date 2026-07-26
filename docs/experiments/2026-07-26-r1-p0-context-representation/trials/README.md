# Trial records

每個受測 subagent 產生一個 JSON record。這是可追溯實驗資料，不是 production Capture 契約。

## 檔名

```text
<case-id>__<arm-id>__<model-short-name>__t01.json
```

## JSON 格式

```json
{
  "trial_id": "CR-01__raw-only__luna__t01",
  "experiment_id": "2026-07-26-r1-p0-context-representation",
  "experiment_revision": 1,
  "phase": "screening",
  "case_id": "CR-01-tools-not-tasks",
  "arm_id": "raw_only",
  "requested_subagent_model": "gpt-5.6-luna",
  "reasoning_effort": "medium",
  "fork_context": false,
  "agent_id": "實際 spawn 後填入的 opaque ID",
  "started_at": "實際 ISO 8601 時間",
  "completed_at": "實際 ISO 8601 時間",
  "subject_request": "實際傳給 subagent 的完整單一 request，包含共同指令與 INPUT_CONTEXT",
  "visible_input_char_count": 0,
  "raw_final_output": "subagent 最終回覆原文，不修補 fenced JSON 或其他格式錯誤",
  "output_char_count": 0,
  "parse_result": {
    "status": "valid_json_object",
    "error": null,
    "parsed_output": {
      "tasks": [],
      "excluded_mentions": [],
      "uncertainties": [],
      "next_question": null
    }
  },
  "evaluation": {
    "review_blind_label": "實際評審前產生的匿名標籤",
    "critical_checks": {
      "C1_TOOL_BOUNDARY": "pass",
      "C6_SOURCE_FIDELITY": "pass"
    },
    "critical_pass": true,
    "secondary_scores": {
      "S1_TASK_STATEMENT": 0,
      "S2_NEXT_QUESTION": 0,
      "S3_UNSUPPORTED_CLAIMS": 0,
      "S4_CONTEXT_EFFICIENCY": 0
    },
    "reviewer_notes": []
  },
  "platform_limitations": [
    "hidden_system_instructions_not_captured",
    "private_reasoning_not_captured",
    "tool_execution_trace_not_available",
    "requested_model_not_openrouter_shipping_model"
  ]
}
```

上例是欄位格式，不是有效實驗結果。正式 trial 必須：

- 將所有「實際……」示意值換成真值；
- `visible_input_char_count` 與 `output_char_count` 由實際字串計算；
- 原始輸出永遠保留；解析失敗不得靜默修復；
- 只寫適用的 critical checks；
- reviewer 在不知道 arm 名稱的狀態下先完成 `C*` 與 `S1`–`S3`，解盲後再評 `S4`；
- 不保存或推測 chain-of-thought。

## Parse status

允許值：

- `valid_json_object`
- `invalid_json`
- `non_object_root`
- `missing_required_field`
- `invalid_field_type`

格式失敗要保存完整 `raw_final_output`，並在報告中與 Task 語意品質分開呈現。
