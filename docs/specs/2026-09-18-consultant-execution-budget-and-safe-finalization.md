# A 主顧問執行額度、有限修正與安全收尾

- 日期：2026-09-18
- Topic：`JD-R002／A-R001`
- Stage：**G4 Owner 已確認；文件對齊完成，G7 尚未開始**
- 範圍：只調整 A 主顧問每次員工輸入的執行 guardrail。既有 OpenRouter／Luna、Prompt、Skills、JD／Memory 權責、B1／B2／C、compaction、保存與 UI 狀態契約均保留。

## 1. 決策結果

每次員工輸入對應的一個 A child run，最多使用：

| 額度 | 正式值 | 語意 |
|---|---:|---|
| model requests | 64 | 包含一般推理、工具結果後續判斷、錯誤修正及最後回答 |
| executed tool calls | 63 | 所有 JD、Memory 與唯讀工具共用；不是每個工具各有 63 次 |
| correction submissions | 2 | 第一次可修正失敗之後，最多再提交兩次替代操作；仍受 64／63 總額限制 |
| SDK hidden retry | 0 | 保留現況；不把 transport retry 疊在 Agent、工具、Node 或 SQL 之上 |

第 64 次 model request 是保留的**無工具收尾請求**。它只在前 63 次仍未自然完成時啟用；一般回合提早完成就直接結束，不必湊滿額度。第 64 次請求必須沿同一個已組裝、已按既有規則壓縮的 request view，設為 `tools=[]` 並明確禁止 tool choice，只能：

- 回答使用者；
- 說明已確認保存的成果；
- 說明尚未完成、需要使用者補充或下輪再處理的事項；
- 不再發起讀取、寫入、Memory 修補或背景請求。

這個 64／63 是 Caliburn 為長訪談與多工具工作選定的 App guardrail，不是 OpenAI、Anthropic、OpenRouter 或 LangChain 規定的標準數字。A 的模型仍為 `openai/gpt-5.6-luna`、reasoning high、8,192 output tokens、90 秒 request timeout、OpenAI-only、禁止 fallback；本切片不調整這些設定。B1／B2 的正式背景 profile 也不變。

同一 run 的 resume／收尾必須沿用已消耗額度；下一次新的員工輸入才取得新的 64／63。現行 child thread 正是每次員工輸入的邊界，因此保留 thread-persisted counter，不改成會在同一 run 恢復時歸零的臨時計數。

## 2. 為什麼取代 16／15

16 model steps／15 tool calls 是較早接線時的保守配置，不是供應商標準，也沒有涵蓋目前已接入的 JD、分層 Memory、來源回查、C 修補及背景通知工具面。既有顧問研究已經證明，若所有額度都可用於工具循環，最後可能沒有模型請求可以對使用者收尾；單純把 16／15 放大成 64／64 仍會保留同一缺陷。

因此本案採 64／63：最多 63 次「模型決定→工具執行」後，仍保留第 64 次模型回答。這符合兩家官方資料共同支持的原則，但數字仍是本產品取捨：

- OpenAI 建議為 agent 明定 outcome、stop rules、工具副作用、retry safety 與錯誤模式，而不是讓工具迴圈無界延長；Responses 的 `tool_choice=none` 可明確要求只產生訊息。[OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5)、[OpenAI Responses create](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- Anthropic 建議將具體錯誤及下一步回給模型；對無效／缺參數的工具要求，模型通常會修正 2–3 次後停止。這支持有界修正，不代表所有業務或副作用錯誤都可重試。[Anthropic Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
- AWS 建議按錯誤是否 transient、操作是否冪等及副作用是否可確認來限制 retry，避免多層重試放大。[AWS Well-Architected REL05](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_limit_retries.html)、[AWS Builders' Library：Making retries safe](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)

鎖定的 `langchain==1.4.0` 已由本機實際原碼核對：`ModelCallLimitMiddleware(exit_behavior="end")` 會插入英文人工 AIMessage，`ToolCallLimitMiddleware(exit_behavior="end")` 也會產生供 UI 顯示的限制訊息。這種框架診斷不是顧問回答，不能進公開聊天或成為 B1 訪談來源。因此正式接線不得再以 generic `end` 訊息作正常終局；它只能是拋錯型 backstop，由 App 依既有 run 狀態安全呈現。

## 3. 現有權責保持不變

| 責任 | Owner | 本次規則 |
|---|---|---|
| 決定是否讀取、修改或回答 | A 模型 | 在 Prompt、工具契約與剩餘額度內選擇，不生成版本、身分或保存事實 |
| 計數、禁止最後再用工具、辨識可信工具結果 | App／Agent Runtime | 不由模型自行宣稱「還有幾次」或「已保存」 |
| JD 候選、交易、receipt、`outcome_unknown` 對帳 | 既有 App 保存層 | 每次 Node／SQL attempt 仍 1 次、0 automatic replay |
| 公開聊天與失敗狀態 | 既有 Chat App／UI | 只顯示已保存公開 AI 正文與固定 App 狀態，不偽造 AI 回覆 |
| 原始訪談、B1／B2、Memory publication | 既有 source／Memory owners | 不因 A 額度或錯誤修正改版、重跑或另建資料權威 |

本案不新增 Agent、工具、資料表、queue、retry service、第二套 conversation／Memory、JD 操作狀態或 provider fallback。也不採用 LangChain generic `ToolRetryMiddleware` 重跑 JD 工具；該 middleware 適合已知安全的 callable retry，不能替代本案的 receipt、未知副作用與模型重新判斷。

## 4. Context 與 compaction 順序

正式順序保持：

```text
原始對話／既有 continuity state
    ↓
組裝 Prompt、Skills、JD notice、Memory guide／按需結果、背景 availability
    ↓
對「實際要送出的對話延續內容」套既有 request-only compaction
    ↓
若為第 64 次請求：移除工具能力並加入最小收尾指令
    ↓
呼叫同一 A 模型
```

JD、Memory、Skills、背景提示及工具定義不是 compaction 摘要的被壓縮資料，也不能被摘要替代。既有 compaction 只處理允許壓縮的對話延續內容；未完整處理的員工訪談原話仍不得壓縮。最後收尾不建立另一份摘要，也不改寫 canonical messages。

實作可以依 middleware 的實際 wrapping 順序安排，但必須證明最終送往模型的 request 同時滿足：

1. 所有既有 App context 已正確組裝；
2. continuity compaction 看到的是實際 request，而不是較早的半成品；
3. 最後一次沒有任何可呼叫工具，且 provider 收到 no-tool choice；
4. 收尾指令不覆蓋既有顧問 Prompt，只是該次 request 的 Runtime 限制。

## 5. 有限修正，不是自動重試

### 5.1 Correction episode

Runtime 不猜模型的「語意是不是同一件事」。它依目前 run 中可信、結構化的 ToolMessage 開啟一個 **correction episode**：

1. 第一個可修正錯誤是原始失敗，不算 correction submission。
2. 模型可按錯誤提供的 `next_action` 讀取必要證據；這些 read 仍計入 64／63，但不會洗掉 correction 次數。
3. 模型提交替代的失敗工具操作時，使用一次 correction submission；最多兩次。
4. JD mutation 回 `committed`／`no_change`，或原失敗的 read 成功並由模型完成回答，才結束這個 episode。
5. 第二次替代操作仍失敗，或 Runtime 證明同一 canonical request／同一結果無進展時，不再給新工具操作；進入無工具收尾。

這個 episode 從 canonical saved messages／tool results 重建，不建立新的資料表或長期權威。若實作使用 private checkpoint counter 作快取，必須能由同一 run 的 canonical 結果驗證，不能在 resume 時歸零，也不能成為另一份結果 SSOT。

### 5.2 依現行契約分類

| 現行結果／動作 | 可做行為 | 修正上限 |
|---|---|---:|
| `invalid_input`＋`correct_arguments` | 根據欄位錯誤修正參數；不得刪有效內容求過測 | 2 次替代提交 |
| `relationship_conflict`＋`correct_arguments` | 讀取相關 items 後修正明確關係 | 2 次替代提交 |
| `target_missing`／`stale_view`＋`reread_current` | 先讀 current，再用新 refs 重新規劃；不能把舊 refs 偷換成 latest | 2 次重新提交 |
| `dependent_items` | 只有既有意圖與證據足以支持明示解除／改接時才處理；否則詢問使用者 | 不得自動 cascade／set NULL |
| `save_failed`／`read_failed`／`operation_conflict` | 停止工具修正，保留已知結果 | 0 |
| `outcome_unknown`／未確認 receipt | App 以同一 operation identity 對帳 | 0；不得新 operation 重做 |
| `busy`／`archived`／Runtime 或 provider failure | 交既有 App 狀態／恢復流程 | 0 |

較早 JD 文件中的 `unsupported_content`／`engine_failed` 是舊契約名稱；現行 relational result schema 沒有這兩個公開 status。本切片不把它們重新加回 schema。若內部或歷史邊界仍遇到相同情況，由既有 owner 映射為目前可修參數或停止類結果，再套上表；不可為了 execution guardrail 擴張結果契約。

修正次數與三件事分開：

- 不是 HTTP transport retry；SDK hidden retry 仍為 0。
- 不是 Node／SQL replay；每個已發配 operation 的保存 attempt 規則不變。
- 不是重新啟動整個 Agent run；所有修正都在原 run、原對話與原總額內。

## 6. 安全收尾與 UI

成功收尾時，最後 AIMessage 是一般公開顧問回答；它可以說明已確認成果與未完成事項，但不能把 candidate、未確認 receipt 或模型推測寫成已保存。

若第 64 次無工具請求本身 incomplete、refused、逾時、transport 失敗，或異常回傳 tool call：

1. Runtime 將 run 依既有規則閉合為 `failed`，不插入框架英文限制訊息，也不偽造 AIMessage。
2. 已確認 `committed` 的 JD receipts 與 revision 保留；不 rollback、不重做。
3. Web 沿用現有固定繁中狀態：已保存輸入時顯示「原話已保存，回覆未完成」；輸入未保存時維持既有另一分支。
4. 固定 UI 狀態不是 assistant message，不進 `chat_history`、conversation source、B1、Working State 或 Memory。

模型自行修復的中間 ToolMessage 錯誤也不新增 App 警告或公開聊天訊息。原生 checkpoint 可保留工具結果供恢復與診斷；公開歷史仍只投影 Human 與真正 AI 公開正文。若最後回答需要交代仍未完成的事項，應說結果與下一步，不顯示內部 exception、stack、框架計數或已被修好的原始參數錯誤。

## 7. 最小施工面

後續 G7 計畫只能處理下列範圍：

- 將 A 的 `MAX_MODEL_STEPS／MAX_TOOL_CALLS` 改為 64／63；A 的模型輸出、timeout、route 不變。
- 在既有 A graph 增加一個 App-owned execution/finalization guard，使用 LangChain 公開 middleware／`ModelRequest.override` 能力；不 fork LangChain、不碰私有 provider payload。
- generic model/tool limit 改成不產生公開人工訊息的 fail-closed backstop。
- 從現有結構化 ToolMessage／`next_action` 執行 correction episode；不改 JD result schema、receipt 或 tool input schema。
- 沿用現有 Chat UI 的固定失敗狀態；除非測試證明現況不符，本切片不改 Web 文案或 HTTP contract。

## 8. 驗收

先做離線、固定模型與真 Agent graph 測試；本切片不需要 provider 呼叫或付費：

1. 最多 63 個工具可執行，第 64 次 model request 實際收到零 tools／no-tool choice，並產生公開回答。
2. 第 64 次 request 使用同一份已組裝 context 與既有 request-only compaction；JD／Memory／Skills／背景提示未被摘要取代。
3. 模型提早回答時不被迫多呼叫；新的員工 turn 取得新額度，同一 run resume 不重置。
4. `invalid_input`／`relationship_conflict` 及 stale→reread→replan 各證明最多兩次替代提交；成功會結束 episode，純 read 不會洗額度，完全相同的無進展結果提早停止。
5. `save_failed`、`read_failed`、`operation_conflict` 與 `outcome_unknown` 都不觸發新工具重送；未知結果只走原 operation 對帳。
6. 最後請求失敗時，已保存 JD 保留、run 為 failed、UI 顯示固定繁中狀態，公開 chat/source 沒有框架英文訊息、假 AI 回覆或固定 fallback。
7. 中間可修錯誤成功後，不新增公開錯誤提示；原 ToolMessage 仍留在 canonical checkpoint。
8. 現有 Prompt、Skills、Memory、B1／B2／C、compaction、來源引用與人工／AI 共用保存回歸未被改寫。

自然模型／付費驗證、完整瀏覽器 App journey 與 production authority 仍是後續 gate；離線通過不能宣稱這些已完成。

## 9. 非目標

- 不保證 64 次一定能完成所有使用者要求；它是有界上限，不是品質承諾。
- 不新增自動 fallback、額外模型、動態 64→更高額度或輸出上限重送。
- 不重談 A Prompt、Memory 分層、B1／B2 生命週期、C repair、compaction 內容或 JD 業務規則。
- 不把固定 UI 失敗提示保存為對話，也不讓 B1／B2 使用它作證據。
- 不因本文件改動就重跑全部 App suite；施工時先跑精確反例與受影響回歸，只有實際影響或失敗才擴大。

## 10. 與既有文件的效力

本文件只取代：

- A 的 16 model steps／15 tool calls；
- 「同一語意錯誤只修正一次」的舊保守起始值；
- 以 LangChain generic `exit_behavior="end"` 人工訊息作公開終局的可能解讀。

以下不被取代：

- 8,192 output tokens、90 秒、Luna／OpenRouter route、禁止 fallback、hidden retry 0；
- JD operation、Node／SQL attempt、receipt、unknown outcome 及恢復規則；
- 已完成的 A request-only compaction、B1／B2／C、Memory publication 與 App UI 權責。

正式現況以[目前決策](../current-decisions.md)為入口；模型 route 參考[角色模型工廠](2026-09-17-openrouter-role-model-factory.md)，工具結果與保存責任參考[關聯式 Agent 工具契約](2026-09-12-jd-relational-agent-tool-contract.md)，歷史 Node／SQL 恢復研究參考[ER01–03 收斂依據](evidence/2026-09-10-jd-error-recovery-contract-closure.md)。

## 11. G7 實際驗證紀錄（2026-09-18）

- A guard、child thread 額度生命週期、原生 JD Tool correction、request-only context／compaction 接點及安全收尾已在既有 commit `8f16954a`、`9d6f6339`、`d2c3bd0d`、`6a9cbbad` 完成；本段只記 Task 5–6 的收尾驗證，不改前述產品契約。
- PostgreSQL failed-final 回歸的 synthetic plan 先保存一筆真實 JD mutation，再以 61 次成功 `jd_read` 到達第 64 次 `tools=[]`／`tool_choice="none"`；最後 transport failure 後，確認 committed receipt／revision、原話保存與 `failed` run 不變，沒有 fallback AIMessage、框架英文限額訊息或公開 assistant history／source。
- 受影響離線 Python 集合為 **314 passed／0 failed**；Web `chat-session`／`chat-drafts` 為 **62 passed／0 failed**；`src／tests` compileall 與 `git diff --check` 通過。精確 PostgreSQL 測試因未設定明示 `JD_RELATIONAL_TEST_DB=1` 而 **1 skipped**，不把它寫成真 PG 通過。
- 本地證據不涵蓋自然 Luna 品質、OpenRouter 付費／服務端行為、完整瀏覽器 journey、多 process production authority；這些仍保持後續 gate。此次沒有讀取正式 key、provider request、schema／migration，也沒有改 Prompt、Skills、Memory、B1／B2／C、compaction 或 Web copy。
