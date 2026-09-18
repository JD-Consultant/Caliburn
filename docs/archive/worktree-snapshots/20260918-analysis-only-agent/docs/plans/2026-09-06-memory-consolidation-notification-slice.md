# Q019 Task4a：耐久通知與安全收尾 Implementation Plan

> For agentic workers: use superpowers:executing-plans，TDD 後獨立 review；本段是同一 root／child 接點，按順序執行。Owner 已准隔離實作，到本段完成可停下回報。

**Goal:** 主顧問可要求背景整理並繼續答覆；通知經重啟仍能找回，取消途中不鎖死訪談、不假報 Memory 已更新。
**Architecture:** 官方 `@tool(content_and_artifact)`＋ToolNode＋既有 Saver 保存訊號，ConversationReader 從安全封閉來源投影未涵蓋要求。沒有外部 job 副作用；重用 root／child 收尾，不重寫 Agent loop。
**Tech Stack:** 隔離 package 的已鎖版 LangChain／LangGraph／OpenAI adapter／PostgresSaver；本段不新增依賴。
**Spec:** [通知接線 §3–5.3](S:/caliburn/docs/specs/2026-09-06-memory-consolidation-request-wiring-design.md)。[父計畫](S:/caliburn/docs/plans/2026-09-06-analysis-only-agent-application-wiring.md) Task3 API 及其餘 Task4 worker／結果 Context 仍是接續工作，不能把本段視為完整排程。

## Global Constraints

- 只在 `codex/analysis-only-agent`／`experiments/analysis-agent` 實作，不接舊 app／production／JD，不 push／merge。
- 模型通知參數 `{}`，不填理由、來源 ID、時間或版本。通知不等 B、不發布 Memory、不建立 job／outbox。
- 用成功且配對的已保存 ToolMessage artifact；不解析自然語言要求。安全來源邊界仍由 Runtime 決定。
- 保留既有 9 model／8 tool 上限；工具回覆不冒充最終顧問答覆，不把通知等同零成本。
- `close_turn` 的純通知特例只適用本實際已註冊工具；未知外部效果與 C 的 receipt 對帳規則不放寬。
- 原文只由 Checkpointer 保存；已處理來源順序依 canonical message order，不比較 UUID 大小。部分處理不能消掉後半段要求。
- 付費呼叫 0；PG 只用已驗標籤 `com.caliburn.purpose=q019-durable-conversation-test` 的 `127.0.0.1:55433/q019_agent_test`；不重啟 Docker。
- 字數後備值、API／scheduler、終止失敗 Context、UI、真模型判斷品質不在這個可獨立驗證段，保留父計畫待辦。

## Task 1：通知、來源投影與中斷收尾

Files（相對 `experiments/analysis-agent`）：新增 `src/analysis_agent/consolidation_request.py`、`tests/test_consolidation_request.py`、`tests/test_postgres_consolidation_request.py`；修改 `conversation.py`、`sources.py`、README。

Interfaces：`request_memory_consolidation()` 為官方 tool，返回短 content＋固定 artifact。由 `build_conversation` 註冊；其名稱不得被外部同名 tool 覆寫。`ConversationReader.pending_consolidation_turns(after_reference=None)` 回傳尚未涵蓋的真實 `input_id/end_id`，只讀取當前 canonical 安全前綴；傳入最後成功 publication 的來源 reference，不自行維護 ack／已讀旗標。

- [x] RED：真正 root／child＋MockTransport 模型要求通知後仍能回答；通知前後無 Memory 發布。驗 wire 中工具參數為空、artifact 不進模型；呼叫及結果配對保存。
- [x] RED：成功通知未完成回合不釋出；完成／安全取消後才釋出；自然語言、錯誤結果、其他工具 artifact、不配對 ID 不構成通知。重複通知同回合合併。
- [x] RED：不同回合先後以實際序列；處理到前一回合只移除前要求，不移除後要求。未解回合之後的項目不能跳過；跨文件／不存在的 cursor 拒絕，不猜已處理。
- [x] RED：工具結果保存前中斷、保存後最終回答失敗兩種情境。確認 quiescent 後可關閉並送下一輪；前者補配對 error 不產生成功通知，後者保留真正成功通知。C／未知工具 regression 不變。
- [x] 最小實作範例形狀：

```python
@tool(response_format="content_and_artifact")
def request_memory_consolidation() -> tuple[str, dict]:
    """累積值得整理的新進展時通知背景；不是每輪必呼叫。"""
    return "收到整理請求；記憶尚未更新，請繼續答覆。", {"kind": "memory_consolidation_requested"}
```

  實際 docstring 要說清楚不需主題完成、不重寫詳記。來源 reader 以既有安全回合函式、真實 cursor 及成功配對結果投影；新增薄接點，不新增持久資料層。
- [x] GREEN：`uv run --no-sync pytest tests/test_consolidation_request.py -q --tb=short`；先看預期缺功能失敗再實作，不只測框架或比文字常數。
- [x] PG：關閉後重建 Saver／graph，找回通知、驗部分 cursor 與不重複；清理限測試唯一 thread。無 DSN 要明示 skip，不聲稱已通過。
- [x] 全回歸、compileall／offline lock／diff check、獨立 review；README 與結果寫清楚已做／未做。保存只包含本段檔案，本地 commit／tag 以 current register 及 git 查核，不 push／merge。

## Preflight／狀態

Topic `Q019-MEM-CADENCE-01`，G4 approved → isolated implementation。本輪沒有需再問的產品選擇。基本通知可先於 API 實作；尚無 worker 故不偽造背景狀態來提前宣稱完成 §5.2。舊 Source／Memory 及 native reasoning regression 保留。來源及政策權威在 spec，不複製長研究。

基線：2026-09-06 offline `204 passed / 22 skipped`（未提供專用 PG DSN）。本段最終 `244 passed / 0 skipped`，含18個新增用例；獨立 review 無 Critical／Important／Minor。完整紅綠、測試資料修正與框架空參數核對見[结果](../specs/2026-09-06-memory-consolidation-notification-results.md)。Task4a 關閉後回到父計畫 Task3／其餘 Task4，不能宣稱服務接線完成。
