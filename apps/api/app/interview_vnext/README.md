# Interview AI vNext（隔離開發中）

本 package 是 ADR 0034 的 greenfield 實作區。目前只完成 **V0 + V1-A domain foundation**，沒有 route、DB migration、provider call，也沒有被 production composition root import。現行使用者流量仍走 `app/interview/` v3。

權威文件：

- 目標架構：[`../../../../docs/specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md`](../../../../docs/specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md)
- 實作順序：[`../../../../docs/plans/2026-07-16-interview-ai-vnext-implementation-plan.md`](../../../../docs/plans/2026-07-16-interview-ai-vnext-implementation-plan.md)
- 決策：[`../../../../docs/adr/0034-interview-ai-vnext-greenfield-evidence-workflow.md`](../../../../docs/adr/0034-interview-ai-vnext-greenfield-evidence-workflow.md)
- package 禁令：[`AGENTS.md`](AGENTS.md)

## 目前的程式邊界

```text
domain/                 已實作：純 Pydantic contracts、validators、reducers、events、schemas
application/            空殼：尚未實作 workflow/use case
llm/ providers/         空殼：尚未選模型、SDK 或 prompt
knowledge/ persistence/ 空殼：尚未接 reference snapshot 或資料庫
projection/             空殼：尚未投影到現有 OCS/Web contract
observability/          空殼：Capture vNext 留到 V2
```

`domain/` 只能依賴 Python 標準庫、Pydantic 和同一 domain package。AST dependency test 會阻止 vNext import v3 internals，也會阻止 domain 偷接 FastAPI、ORM 或 provider SDK。

## V1-A 已落實的契約

### Aggregate 與 authority boundary

- `InterviewState` 是 immutable materialized aggregate；nested collection 使用 tuple。
- `InterviewSession.state_version` 是 optimistic concurrency token。
- `processed_command_ids` 是本階段的 deterministic idempotency guard；持久化後會由 repository transaction／idempotency record 承接。
- LLM 未來只能產生 proposal。只有 reducer 可以接受 proposal、驗證並產生新 state。
- employee evidence、inference、reference URN、human review 是不同 authority channel，不混成一段摘要。
- `accepted`／`rejected` candidate 必須有 human `ReviewDecision`；模型不得覆寫人工裁決。

### 時間與文字定位

- 所有 domain timestamp 必須是 aware UTC（offset `+00:00`）；不接受只帶任意時區的時間。
- command 時間不得早於 materialized state 的 `updated_at`，避免 replay 後時間倒退。
- `TranscriptTurn` 保留逐字內容；`received_at >= occurred_at`。
- `QuoteSpan.start/end` 是 Python／Unicode **code point**、左閉右開 `[start, end)`，欄位 `unit` 固定為 `unicode_code_point`。JavaScript UI 若顯示 span，必須轉換 UTF-16 index，不可直接當 JS string offset。
- exact quote 必須逐字等於 span；normalized quote 只允許已版本化的 `quote_nfkc_ws.v1`（NFKC + whitespace collapse）。normalized quote 仍保留原 transcript span，不改寫來源。

### Evidence 與 projection gate

- 新 evidence 必須引用既有 employee turn；consultant 問句不能成為員工事實。
- correction 建立新 evidence，舊 evidence 改 `superseded`，歷史不刪除。
- supersede link 必須雙向、target 必須 active、同一批不得重複取代、整體 lineage 不得成環。
- episode↔evidence、episode↔gap、candidate↔review 都必須雙向閉合；只存單邊 ID 會被 aggregate validator 拒絕。
- projected candidate 至少要有 active、current、affirmed、employee/team evidence，ownership 必須是 `owner|shared|assists`。
- ability／attitude 在 `verified|projected` 前至少需要兩個 episode 的 evidence。
- behavior indicator 的顯式數字門檻必須有 employee evidence、approved policy 或 human source；employee threshold evidence 必須同時存在於 candidate lineage。

### Reducer 結果與事件的正確解讀

Reducer 形式固定為：

```text
old immutable state + typed command
  -> validated new immutable state + typed domain events + stable state hash
```

相同初始 state 與 command stream 會得到相同 event IDs 和 state hash；重送同一 `command_id` 不重複 mutation。事件目前是 artifact index／audit notification，只帶被改變物件的 ID，不含完整 transcript/evidence payload。因此：

- 本階段驗證的是 **command replay + materialized state determinism**；
- 不可聲稱只靠目前 event JSON 就能重建完整 state；
- V2 persistence/Capture 必須原子保存 command/result artifact 或完整可重建 payload，再定義 checkpoint + replay protocol；
- provider SDK response 絕不可塞進 domain event。

這個區分是刻意的：audit event 和完整 event-sourcing payload 是兩種契約，不能因為都叫 event 就混用。

## JSON Schema

committed schema 位於 `domain/schemas/`，檔名與 `$id` 都有 major version。修改 Pydantic contract 後執行：

```powershell
cd apps/api
.venv\Scripts\python.exe -m app.interview_vnext.domain.write_schemas
.venv\Scripts\python.exe -m pytest tests/test_interview_vnext_schemas.py -q
```

Schema golden test 會比較 committed JSON 與當前 Pydantic codegen；未知欄位採 strict reject。runtime validator 的跨物件不變量（例如 quote 對 transcript、lineage cycle）無法只靠 JSON Schema 表達，consumer 仍必須走 domain verifier。

## 測試與下一個切片

目前測試：

```powershell
cd apps/api
.venv\Scripts\python.exe -m pytest tests/test_interview_vnext_domain.py tests/test_interview_vnext_dependencies.py tests/test_interview_vnext_schemas.py -q
```

下一步是 **V1-B**，仍不呼叫 LLM：補齊 episode open/close、gap lifecycle、inference/candidate proposal、withdraw、human review reducers 與各自 command/event/schema；再把所有 aggregate mutation 收斂到 reducer。V1-B 通過後才進 V2 provider-neutral LLM port 與 Capture vNext。

本階段明確不做 route、migration、Web seam、模型 bake-off、ContextBuilder 或 prompt。這些提前加入都會讓尚未穩定的 domain semantics 被外部依賴綁死。
