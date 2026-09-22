# A／B1／B2 角色化 Continuation Compaction Implementation Plan

> **2026-09-22 後續驗收 successor：**本計畫完成後的真 Luna JD 長工具迴圈證明，原本把「A 最新 Human turn」整段鎖住會同時阻止該 Human 之後已完成 wave 壓縮。後續最小修正仍沿本計畫唯一 middleware／profile／summary／digest，只把 A 改為逐字保護最新員工訊息本身，並允許其後 completed waves 進摘要；B1 最新未處理窗口及 B2 fixed task 不變。state v2 的 Runtime-owned `protected_message_id` 與測試結果以[正式設計](../specs/2026-09-16-openrouter-continuation-compaction-design.md)及[驗收證據](../specs/evidence/2026-09-22-jd-component-first-acceptance.md)為準。下方原計畫文字保留當時施工順序，不再作最新 A boundary 權威。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不新增 Agent、Memory、資料表或 provider 接法的前提下，讓共用 App-side compaction 依 A／B1／B2 的工作目的保存正確續作資訊，並固定近期 reasoning metadata 的既有 round-trip 契約。

**Architecture:** 沿用唯一 `ContinuationCompactionMiddleware`、`ContinuationCompaction` state、safe boundary、digest 與原子保存。只在既有 `CompactionProfile` 增加角色專用 summary instructions，摘要 request 以既有 model-visible projection 接收舊 summary＋完成 prefix；B2 另接收逐字固定任務作唯讀 `protected_orientation`。Opaque reasoning 不進 semantic summary；未被 boundary 覆蓋的 canonical tail 仍由框架與鎖定 `ChatOpenRouter` 原樣保存及重送。

**Tech Stack:** Python 3.12、LangChain 1.4.0、LangGraph 1.2.11、langchain-openrouter 0.2.7、Pydantic 2.13.5、pytest 9.1.1。

**Spec:** `docs/specs/2026-09-16-openrouter-continuation-compaction-design.md`

## Global Constraints

- 不改 A／B1／B2 主 Prompt、Skills、Memory 分層、Working State、JD domain、Agent graph、provider factory、credential、資料表或 migration。
- 不把 summary、reasoning metadata 或 B2 orientation 升格為 evidence、Memory、JD basis 或新的持久 authority。
- A／B1／B2 共用同一 middleware；角色差異只存在於既有 profile 的 summary instructions。
- B2 固定任務仍逐字留在主 request；摘要 request 只讀同一 model-visible 訊息作 orientation，不建立縮短版 task。
- 未完成 tool call／result wave保持逐字；A 逐字保護最新員工 HumanMessage 但可壓縮其後已完成 wave，B1 保護最新未處理 Human turn／來源窗口。
- `reasoning_details` 不送入 semantic summary；未被覆蓋的 tail 經 checkpoint／request view／OpenRouter wire 原樣保留。
- 目前工作區已有其他已授權未提交修改；本計畫不 merge、push，也不把無關檔案納入提交。若無法只提交本計畫 hunk，保留驗證完成的工作區差異，不製造混合 commit。

## Review Focus

- B2 固定任務很長或含 Runtime-issued handles：摘要可用它判斷相關性，但主 request 仍只有一份權威原文，summary 不延長 handle scope。
- tool request 已發出但 ToolMessage 尚未完整返回：boundary 不得切入，summary 不得把 request 說成成功。
- A 背景整理通知：摘要只能記通知／receipt，不得宣稱 B1／B2 已完成或 Memory 已更新。
- B1 同一案例散落多段原話且含更正：角色摘要保留處理進度與差異，但尚未處理來源仍逐字留在 tail。
- B2 某一支持案例改變但其他案例仍成立：角色摘要保留支持／反證關係，不得自動將理解判為失效或把所有案例一起改寫。

---

### Task 1: 固定 role profile、B2 orientation 與 reasoning characterization

**Files:**
- Modify: `experiments/jd-relational-app/tests/test_continuation_compaction.py`
- Modify: `experiments/jd-relational-app/tests/test_compaction_adapter_contract.py`

**Interfaces:**
- Consumes: 現有 `CompactionProfile`、`_summary_prompt()`、`build_request_view()`、LangChain `message_to_dict／messages_from_dict` 與鎖定 adapter `_convert_message_to_dict()`。
- Produces: 會在現碼失敗的角色化摘要／B2 orientation 測試，以及應在現碼通過的 reasoning round-trip characterization。

- [x] **Step 1: 先加入 reasoning characterization**

在 `test_continuation_compaction.py` 加入一個含 `reasoning_details` 的近期 `AIMessage`，先經 `message_to_dict／messages_from_dict`，再套用涵蓋較舊 prefix 的 `build_request_view()`；斷言近期訊息的 `additional_kwargs["reasoning_details"]` 未變，且 `_summary_prompt()` JSON 不含 opaque 值。

- [x] **Step 2: 執行 characterization，確認現有行為已通過**

Run: `$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_continuation_compaction.py -k reasoning -q`

Expected: PASS；若失敗，先記錄精確遺失層，不修改 provider adapter 以外的層來掩蓋。

- [x] **Step 3: 加入角色化摘要與 B2 orientation 的失敗測試**

測試建立 A／B1／B2 三個 middleware，以固定 summary model 捕捉 system／human request，斷言：

```python
assert "訪談焦點" in a_summary_request[0].text
assert "案例身分與差異" in b1_summary_request[0].text
assert "跨案例" in b2_summary_request[0].text

payload = json.loads(b2_summary_request[1].text.split("\n", 1)[1])
assert payload["protected_orientation"] == [
    {"role": "user", "content": "固定 B2 任務原文"}
]
assert payload["new_completed_messages"][0]["role"] == "assistant"
```

同時斷言 A／B1 的 `protected_orientation == []`，以及 B2 主 request view 仍以固定任務原文開頭、summary 居第二位。

- [x] **Step 4: 執行新測試並確認 RED 原因正確**

Run: `$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_continuation_compaction.py -k "role_specific or protected_orientation" -q`

Expected: FAIL，原因是 profile 尚無角色 instructions，且 `_summary_prompt()` 尚未提供 `protected_orientation`；不得是 fixture、import 或 JSON 解析錯誤。

### Task 2: 在共用 middleware 實作最小角色化 projection

**Files:**
- Modify: `experiments/jd-relational-app/src/jd_relational/continuation_compaction.py`
- Modify: `experiments/jd-relational-app/tests/test_continuation_compaction.py`
- Modify: `experiments/jd-relational-app/tests/test_background_agent_compaction.py`

**Interfaces:**
- Consumes: Task 1 的失敗測試與現有 `preserve_initial_messages`。
- Produces: `CompactionProfile.summary_instructions`、`_summary_system_prompt(profile)` 與 `_summary_prompt(..., protected_orientation=...)`；原 state shape、boundary 及 digest 不變。

- [x] **Step 1: 加入共用與三角色 instructions**

在 `continuation_compaction.py` 保留現有 `SUMMARY_SYSTEM_PROMPT` 作共同前綴，新增三個短常數，內容只對應 spec §4.3；`CompactionProfile` 新增具非空預設值的 `summary_instructions: str`，A／B1／B2 profile 各自覆寫。不得新增 prompt registry 或新模組。

- [x] **Step 2: 組出角色化 system prompt**

新增：

```python
def _summary_system_prompt(profile: CompactionProfile) -> str:
    return (
        f"{SUMMARY_SYSTEM_PROMPT}\n\n"
        "【本角色續作重點】\n"
        f"{profile.summary_instructions}\n\n"
        "protected_orientation 只供判斷相關性，仍會逐字留在主請求；"
        "不要重抄、改寫或宣稱已由摘要取代。"
    )
```

`SUMMARY_SYSTEM_PROMPT` 本身仍可作測試辨識的穩定共同前綴。

- [x] **Step 3: 把既有 protected initial messages 投影給摘要模型**

將 `_summary_prompt()` 改為接收 `protected_orientation: list[BaseMessage]`，payload 固定為：

```python
{
    "protected_orientation": [
        _summary_input(message) for message in protected_orientation
    ],
    "existing_summary": previous.summary_text if previous else None,
    "new_completed_messages": [
        _summary_input(message) for message in incremental
    ],
}
```

middleware 呼叫時傳入 `canonical[:profile.preserve_initial_messages]`，並用 `_summary_system_prompt(self.profile)`；不得修改 boundary、digest、state schema 或主 request view。

- [x] **Step 4: 修正受影響的合成模型辨識方式**

`test_background_agent_compaction.py` 的 `RoleAwareModel` 改以：

```python
messages[0].content.startswith(SUMMARY_SYSTEM_PROMPT)
```

辨識摘要 request，避免把角色 suffix 誤判為主模型呼叫；不改 production 判斷。

- [x] **Step 5: 執行 Task 1／2 受影響測試**

Run: `$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_continuation_compaction.py tests/test_compaction_adapter_contract.py tests/test_background_agent_compaction.py -q`

Expected: 全部 PASS；既有 private artifact／opaque reasoning 排除、B1 窗口與 B2 attempt lifecycle 測試不得退化。

### Task 3: 組裝回歸、文件狀態與完整離線驗證

**Files:**
- Modify: `docs/specs/2026-09-16-openrouter-continuation-compaction-design.md`
- Modify: `docs/current-decisions.md`
- Modify: `docs/README.md`
- Test: `experiments/jd-relational-app/tests/test_consultant_app.py`
- Test: `experiments/jd-relational-app/tests/test_background_agent_compaction.py`

**Interfaces:**
- Consumes: Task 2 的 profile 與 prompt projection。
- Produces: A／B1／B2 正式 assembly 沿用角色 profile 的證據，以及目前決策入口的精確完成／未完成狀態。

- [x] **Step 1: 執行正式組裝與相鄰 context 回歸**

Run: `$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest tests/test_consultant_app.py tests/test_background_agent_compaction.py tests/test_consultant_context.py tests/test_consultant_memory_context.py -q`

Expected: 全部 PASS；A／B1／B2 仍使用同一注入 role model object，無 provider request。

- [x] **Step 2: 執行完整 App 離線套件**

Run: `$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'; uv run pytest -q`

Expected: 產品測試 0 failed；若只出現已記錄的 Windows 暫存目錄 ACL 環境錯誤，保留首敗並以既有安全排除方式另跑，不把環境錯誤冒稱產品 PASS。

- [x] **Step 3: 驗證語法、格式與差異**

Run: `$env:PYTHONUTF8='1'; uv run python -m compileall -q src tests`

Expected: exit 0。

Run: `git diff --check`

Expected: 無 whitespace error。

- [x] **Step 4: 更新狀態但不誇大驗收**

在 `docs/current-decisions.md` 與 `docs/README.md` 記錄：角色化摘要、B2 orientation、reasoning client round-trip 及離線測試結果；同時保留「正式 16K 自然長訪談、每次真 Luna reasoning metadata、付費品質與 provider-native compaction 未由本切片證明」。不新增另一份研究或 evidence 文件。

- [x] **Step 5: 提交邊界**

只在能精確隔離本計畫 hunks 時提交：

```text
feat: align continuation compaction by agent role
```

若相關檔案含本計畫開始前的未提交修改而無法安全分離，保留工作區並回報，不建立混合 commit；不 push。

本次採後者：相關 production、測試及入口文件在本計畫前已有同一整合工作中的未提交差異，故不建立混合 commit，也不 push。
