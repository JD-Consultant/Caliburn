Verdict: FAIL

# Memory Routing 與 Canonical Read 隔離實驗報告

## 1. 結論

Trial revision 2 沒有產生可評分的模型結果。OpenRouter metadata preflight 已完成，但隔離
smoke 實驗執行器在第一個資料庫連線、embedding 與 Luna request 之前，以
`psycopg.InterfaceError` 結束。六個品質判準全部是 `NOT_EVALUATED`；本結果不能解讀為
Memory routing 成功，也不能解讀為 Luna 或兩個 Memory tools 品質失敗。

依凍結規則，本 attempt 保存後停止。現在不授權第三次 live attempt、production 整合、ADR
狀態改變、merge 或 push。

## 2. 凍結條件

| 項目 | 實際值 |
|---|---|
| Case SHA-256 | `a39f668dbcb23f4b7c8b8396cb8593f115dda8da41d092efb4b24be63bf9b835` |
| Rubric SHA-256 | `7555260a65dd5882be1ab680c6ac1ecf3ebb45fb385048f0515d5d72682a0158` |
| Prompt SHA-256 | `91558055927742669fe1be8df33100a63a216490d95c2dac44e24c808d62c701` |
| Chat model | `openai/gpt-5.6-luna` |
| Reasoning | `medium` |
| Embedding model | `openai/text-embedding-3-small` |
| 最大 model／tool calls | `3／2` |
| Provider／framework retry | `0／0` |

Case、rubric、prompt、模型與所有 caps 在 attempt 前後均未修改。

## 3. 實際發生的事

1. runner 成功讀取不落盤的 API key，並完成 model、embedding 與 endpoint metadata preflight。
2. runner 以 Windows 上的 `asyncio.run()` 啟動；Python 3.13 預設建立
   `ProactorEventLoop`。
3. `open_spike_runtime()` 在 `_read_current_database()` 建立第一個 Psycopg async connection
   時被官方相容性檢查拒絕。
4. 程序以 exit code 1 結束，launcher wall time 為 2,749 ms；尚未進入 Store、embedding、
   LangGraph agent runtime、Memory tools 或 Luna。
5. 例外不在 runner 的 receipt error boundary 內，因此正常 `LiveSmokeReceipt` 沒有寫出。
   `trials/revision-2-luna-medium.json` 是依保存下來的 command result 重建的 attempt record，
   不是 provider receipt。

精確錯誤分類是 `psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in
async mode`。

## 4. 為何 deterministic tests 沒有提早發現

`tests/conftest.py` 在 Windows 明確安裝 `WindowsSelectorEventLoopPolicy`，所以 PostgreSQL
tests 使用 Psycopg 相容的 Selector loop。CLI runner 的 `main()` 直接使用預設
`asyncio.run()`，沒有繼承 pytest-only 設定；因此 deterministic suite 綠燈，而實際 CLI
入口仍失敗。

這是 experiment-runner entrypoint coverage 缺口，不是 Store、Checkpointer 或 Memory read
contract 的反例。

## 5. 官方診斷與尚未實作的最小候選修法

Psycopg 官方明示 Windows 預設 `ProactorEventLoop` 不相容，應使用
`SelectorEventLoop`。Python 官方說明 Windows 自 Python 3.8 起預設使用 Proactor；Python
3.13 的 runner API 則建議以 `asyncio.run(..., loop_factory=...)` 設定 loop，而非依賴全域
policy。

不發 provider request 的 DB-only 診斷已用
`asyncio.run(..., loop_factory=asyncio.SelectorEventLoop)` 成功讀回專用資料庫名稱
`caliburn_memory_routing_spike`。因此最小候選修法是只在 Windows CLI entrypoint 選用
Selector loop，並補 entrypoint regression test；不需要改 Memory 架構、升級 SDK、增加
retry 或更換資料庫。

本報告只記錄候選修法，沒有實作。是否核准 bounded repair，以及修復後是否另核准新的 live
attempt，是兩個後續 gate。

直接來源：

- [Psycopg — Concurrent operations／Windows event-loop warning](https://www.psycopg.org/psycopg3/docs/advanced/async.html)
- [Python 3.13 — asyncio platform support on Windows](https://docs.python.org/3.13/library/asyncio-platforms.html#windows)
- [Python 3.13 — asyncio runners and `loop_factory`](https://docs.python.org/3.13/library/asyncio-runner.html#running-an-asyncio-program)

## 6. Rubric 結果

| 判準 | 結果 | 原因 |
|---|---|---|
| A 案細節與精確原句 | `NOT_EVALUATED` | 沒有 Luna request |
| A／B 分案與更正後 current Memory | `NOT_EVALUATED` | 沒有 Luna request |
| 未知資訊不捏造 | `NOT_EVALUATED` | 沒有 Luna request |
| 自主 search＋canonical deep-read | `NOT_EVALUATED` | 沒有 model／tool call |
| Context 有界 | `NOT_EVALUATED` | 沒有 model-visible turn |
| Scope／secret 不洩漏 | `NOT_EVALUATED` | 沒有 model-visible turn |

## 7. 支持、不支持與未證明

### 支持

- metadata preflight 可在凍結模型與成本條件下完成。
- 既有 deterministic suite 支持隔離元件的 PostgreSQL persistence、scope guard、strict tool
  contract 與 storage-growth 量測；這些不是 revision 2 的模型品質結論。
- 官方建議的 Windows Selector loop 能在同一環境完成專用資料庫 identity read。

### 不支持

- 現行 CLI live runner 可在 Windows 預設設定下跑通；revision 2 直接反證此點。

### 未證明

- Rubric 六項與 M2、M4 read-side、M7、M8 model-routing、M10 model deep-read、M11
  model-visible scope 全部未證明。
- 原計畫列出的 M3 admission breadth、完整 M4 manager 更新、M5 未知／衝突
  consolidation、M6 整體關係品質、M9 final exact full audit、真實員工資料品質、production
  scale 與 UI 仍未證明。
- 因未發 inference request，實際 resolved model／provider、token、cache、reasoning、embedding
  usage 與 inference request IDs 均未產生；metadata request 的 response identifier／latency 未由
  runner 保存，也不得推測。

## 8. 下一個 gate

先由 Product Owner review 本報告，決定是否只核准 Windows CLI event-loop bounded repair。
即使 repair 通過 deterministic verification，也不自動授權下一個 Luna attempt；不得在同一決策
中默認重跑。
