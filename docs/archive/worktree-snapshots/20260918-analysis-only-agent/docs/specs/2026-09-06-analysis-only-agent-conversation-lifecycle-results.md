# Q019-APP-01：每次發言的持久執行範圍——部分結果

> 2026-09-06 · **Task 1 離線與 PG 補驗證通過：177 passed／0 skipped；尚未 commit／tag，Task 2／API／UI 未施工。**初輪 Docker 阻塞保留為沿革，最新結果見 §6。
> [決策入口](../current-decisions.md) → [接線設計](2026-09-06-analysis-only-agent-application-wiring-design.md) → [隔離計畫 Task 1](../plans/2026-09-06-analysis-only-agent-application-wiring.md)。跨廠商原因與來源仍由[失敗處理研究](2026-09-06-analysis-only-agent-failure-recovery-review.md)持有，本稿只記本次實作證據與未決事項。

## 1. 實作範圍與框架責任

Worktree：`S:/caliburn/.worktrees/analysis-only-agent`，branch `codex/analysis-only-agent`，base `bd6e4751`。新增 `experiments/analysis-agent/src/analysis_agent/conversation.py`，底下仍用同一個 `create_agent`。根圖保存完整對話與本輪結果；Agent 直接作為 per-invocation 子節點，繼承 Checkpointer。官方 thread counters 留在子流程，root 不保存它們，因此恢復同一回合不重置、新回合才取得新額度。

沒有第二位主顧問、另一份可獨立改寫的對話 store、自寫 Agent loop 或私有 counter reset。根圖與子圖的 checkpoint 都可能保存 messages，存在額外 I/O；不是宣稱物理上只存一份 bytes。原生 compaction 仍只改 request view，不刪 canonical items。[官方 subgraph persistence](https://docs.langchain.com/oss/python/langgraph/use-subgraphs#subgraph-persistence)、[官方 middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)

## 2. 已實測的行為

下表記錄首輪離線驗證及其當時限制；PG 重建 clients 的後續補驗證見 §6，不把離線案例本身冒稱 PG 測試。

| 情境 | 離線結果 | 界線 |
|---|---|---|
| 工具中斷後恢復 | 同一 input 額度續算，已存的模型呼叫不重跑，沒有再 append 員工輸入 | InMemorySaver；PG 尚待驗證 |
| 新員工訊息 | 得到新額度，但保留前面全部問答與工具結果 | 不等於 API 重複請求 admission 已完成 |
| reasoning／compaction／tool pair | 完整 root↔child round-trip，下一次 request 的原生切點不變 | 假 HTTP 內容，非真模型品質測試 |
| C 成功／stale | 工具結果帶新版 head，後續讀到正確版本；初始 guide 不被背景偷偷改寫 | MemorySession 舊功能未改寫 |
| C commit 成功但回覆遺失 | 保持 pending，恢復相同 operation；不新增第二個發布回執 | InMemorySaver＋SQLite ORM，不能代替 PG 重建 clients |
| 已知工具 schema 錯誤 | 框架回傳欄位問題，模型下一步可修正 | 不承諾真模型一定修得好 |
| 工具參數不是合法 JSON | 公開 middleware 回傳同 call ID 的 error ToolMessage；原 arguments 不改寫；只給一次修正機會 | 不是 ToolErrorMiddleware 原生自動處理；見下方 R2 |
| incomplete／failed provider 回覆 | 在工具執行前停下，保留原始 status 與 pending | 安全結束／放棄恢復是 Task 2，尚未做 |
| model／tool limit | 人工停止訊息不加 provider completed；本輪 outcome 為 limit，工具結果配對保留 | 不當作背景可抽取的成功問答 |

### 本次真正修正的兩個接線問題

1. **把官方 thread limit 直接放在整份訪談會用完就一直沒額度。** RED 顯示第二則員工訊息沒有新模型呼叫；per-invocation 子節點後，恢復沿用舊額度、新訊息有新額度。
2. **after hooks 逆序且 jump 可略過後續 hook。** 若 tool-limit 先停止，會漏掉該次 model count。現在依序驗 provider 原始完成狀態 → 累加 model count → 檢查 tool limit。測試確認第二次模型回傳觸發工具上限時，計數是 2 而非 1。

### 校準初值，不是擅自放寬付費上限

搜尋正文 → 讀正文 → 讀詳記 → 讀原問答 → 一次錯誤 edit → 修正 edit → 重讀結果 → 最後回答，共 **7 次工具、8 次模型**。原 6 model steps 擋住此正常路徑，已用測試重現。

隔離 factory 暫採可配置 **9 model calls／8 tool calls**，讓最多 8 次准入工具後仍容納一次最終回答。這不是保證任何訪談都足夠、不是各家共同數字，也不增加本輪付費授權：**付費呼叫仍為 0**。官方 counts 不涵蓋全部失敗 HTTP attempts，未知 usage 保持未知；真正 timeout／輸出配置／取消與服務 admission 還須接線驗收。

### 獨立審核的兩項發現與修復

- **R1：人工 limit 訊息污染下一輪 C 來源。** `capture_input` 原本取最近有文字的 AIMessage，因此短句「不是，是處長」會連到停止提示，漏掉真正顧問問題。已先用完整 root→limit→新輸入→C 測試重現，再給 runtime 人工訊息持久標示；來源投影排除該標示，但 canonical 內容仍保留。只修改 `_visible` 的窄幅規則，**不是把 Task 2 失敗來源都放行**。
- **R2：工具 arguments 壞 JSON 時，直接 raise 會卡在已保存的 after_model。** 單純 `invoke(None)` 只重驗相同壞內容。已核對官方 `hook_config`／`jump_to` 與 pinned adapter 實作，新增小型 `ToolJsonFeedback`：保留原 function_call／ID／arguments，回傳「未執行、JSON 不合法、請依 schema 修正」的配對 ToolMessage，經官方 model 入口續作；第二次仍錯則標成 runtime `tool_error` 並結束。不填造 `{}` 參數、不改 provider status、不假裝執行工具、不 reset 額度；中斷後修正次數仍保留。缺 call identity／非預期平行輸出仍 fail closed，服務安全終止由 Task 2 承接。

R2 是本案使用[官方 middleware 擴充接點](https://docs.langchain.com/oss/python/langchain/middleware/custom)的窄幅接線，**不宣稱大廠內部都用這個 class，或官方 ToolErrorMiddleware 已涵蓋 adapter parse 階段**。錯誤回饋與有界修正沿用已同意原則；精確 producer／consumer 以真 SDK 假 HTTP 測試檢查。新的 hook 順序是 provider completion → model count → JSON feedback → MemorySession 正常驗證 → tool limit。

## 3. 真實 SDK／adapter 的失敗行為（假 HTTP）

直接經 `build_model → ChatOpenAI → OpenAI SDK → httpx.MockTransport`；未 mock SDK retry 判斷或模型方法。只替換 sleep 以驗證等待參數、不真的長等。版本：OpenAI 3.8.0、LangChain 1.4.0、langchain-openai 1.6.0、LangGraph 1.2.11。

- 暫時 408／409／429／500／503：一次失敗後成功共 2 個 HTTP attempts；持續 429／503 共 3 attempts 後拋錯，沒有外層重試疊乘。
- 注入的 400 schema／401：各 1 attempt 就拋型別化錯誤；回覆帶 request ID。這不是任何實際 schema 已獲服務端接受的證明。
- Retry-After 的 7 秒、120 秒、毫秒 header 優先順序有測；超過此 SDK ceiling 的 121 秒不提早重送。這是 pinned SDK 行為，不當成所有供應商規格。
- 無 usage 的 incomplete 仍是未知，不填 0；基本 Agent 到 END 不代表 provider 成功。新 conversation 層另驗 `status=completed`。
- **TR-01，保留到串流接線 gate：**部分 SSE `error`／`response.failed` 事件在 SDK 可讀到，但 adapter iterator 可正常結束且沒有失敗 status。不能用「串流沒拋 exception／最後一個 chunk」判斷成功。目前只接同步非串流；不可在 UI 偷偷啟用串流並沿用不完整判斷。未 patch private converter。

外部原則：[OpenAI retries](https://developers.openai.com/api/docs/guides/rate-limits#retrying-with-exponential-backoff)、[Anthropic API errors](https://platform.claude.com/docs/en/api/errors)、[LangGraph fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)。以上數量是本地真 SDK／假 HTTP 的實測，不是推測 Codex／Claude 產品內部重試策略。

## 4. 命令、失敗與誠實 gate

在隔離 package、`PYTHONUTF8=1`、沒有真 API key 的環境：

```text
.venv/Scripts/python.exe -m pytest tests/test_conversation_lifecycle.py -q --tb=short
19 passed in 8.58s

# 明確不提供 Q019_TEST_DATABASE_URL
.venv/Scripts/python.exe -m pytest -q -rs --tb=short
159 passed, 18 skipped in 17.60s
```

18 skipped = 既有 16 個 PG 案例＋新 2 個 root→Agent→C 重建 clients 案例。**不能把跳過案例算成通過，也不能拿上一段 120 passed／0 skipped 取代。**完整 root／child 測試確認沒有疊乘 HTTP 重試，用完 8 次准入工具後第 9 次模型仍能完成回答；四項新回歸涵蓋來源排除技術提示、壞 JSON 成功修正／耗盡，以及中斷恢復不重置修正額度。

`compileall` 與全部本段變更檔 whitespace checks 通過。`uv lock --check --offline` 通過（73 packages）；第一次因預設使用者 cache 權限失敗，改用隔離工作區 `.uv-cache` 後通過，未改依賴／lockfile。Git 的 LF→CRLF 提示不是測試警告，未批次轉換換行。

首輪 baseline 啟動失敗：Docker 未運行，控制命令未即時停下，後續用空 credential 組成無效 DSN，得到 104 passed／11 failed／5 errors。那不是程式回歸證據；已停止該命令、後續改成 fail-fast，沒有使用正式資料庫或輸出真密碼。正式無 DSN run 明確跳過 PG。

Docker 官方 start 後仍無法完成啟動；主機日誌指出 `AppData/Local/Docker/run/dockerInference` stale socket 無法移除。未 kill backend、改名 socket、重設 Docker 或刪除資料。資料庫 gate 因此仍阻塞；要另取得維護者確認處理這個新 socket 問題。

## 5. 下一步與禁止越過的界線

- 獨立 code/spec review：R1／R2 已在修復後限定複核關閉，未見新增 Critical／Important 阻塞。Reviewer 核對公開跳轉入口、計數順序及原始 call／配對結果，沒有代替 controller 跑測試；controller 隨後完成上述 19 focused 與 159 passed／18 skipped 全回歸。舊 root outcome 在 child pending 時不可作當輪結果，已記為後續 API 接線限制。**這不是 PG gate 通過或 Task 1 完成。**
- 專用 PG 全回歸及新 parent／child／C 恢復驗證已於同日補通過，見 §6；尚未建立本段 commit／tag。
- **Task 2 尚未做**：失敗／取消的安全終止、可抽取來源邊界、放棄恢復後新訊息；更不能宣稱聊天室已解鎖或背景不漏來源。
- Task 3–5（API／排程／UI handoff）未做。不改 production、不 merge／push；本段尚未 commit／tag。
- 重開條件：公開 API 無法保留原生 items／來源／子圖恢復，或實測安全關閉做不到；先討論，不寫私有兼容層。

## 6. Docker 恢復後的 PG 補驗證

Owner 授權修復 Docker，agent 升級官方 4.89／備份舊 socket 後曾恢復，但自動重啟仍失敗；Owner 回報按 reset to factory defaults 後恢復。既有容器與 volumes 清單仍在，Q019 原資料庫可連線；細節與未解啟動限制見[維運紀錄](2026-09-06-docker-desktop-startup-repair.md)。不要把補測成功寫成 Docker 重啟問題已根治。

在同一隔離 package，以既有 `caliburn-q019-postgres`、`127.0.0.1:55433/q019_agent_test`、connect_timeout=5，未修改 Task 1 程式，重跑全部測試：

```text
.venv/Scripts/python.exe -m pytest -q -rs --tb=short
177 passed in 36.60s
```

0 skipped、0 付費模型呼叫；18 個原跳過 PG 案例本次實際執行。新增兩案驗證 C commit 前失敗／commit 後回覆遺失，在關閉並重建 PG clients 後以相同 operation 恢復；同回合沿用額度、下一員工訊息重新取得額度。R1／R2 修補也包含在本次全回歸。離線 SDK fixtures 不等於真模型品質已測；Task 2 安全終止與 API 仍未完成。
