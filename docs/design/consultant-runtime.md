# AI 職務顧問 runtime 設計

- 決策：[ADR 0060](../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)
- 狀態：Big-bang migration 建構中；目前完成框架底座、durable authority、模型執行、最小充分 Context、專業分析 Skills，以及 adaptive interview／可見理解／語意進度／足夠性，production composition root 尚未切換
- 實作：`apps/api/app/consultant`、`apps/api/app/adapters/langgraph`、`apps/api/app/adapters/openrouter/langchain.py`

## 儲存權威

每項持久事實只有一個 writer：

| 事實 | Owner |
|---|---|
| 文件 ID、library title、thread pointer、tombstone | Alembic 管理的 `consultant_documents` 最小 catalog |
| 員工逐字輸入、direct-edit 改寫文字、修正 lineage、position anchor | LangGraph `AsyncPostgresStore` 的文件 UUID namespace |
| 可演進顧問狀態、source references、review queue、核准文件與 run status | LangGraph `AsyncPostgresSaver` checkpoint |

checkpoint 不複製員工逐字來源；Store 不保存第二份核准文件。API／Web 日後只讀 checkpoint projection，不再建立 relational／JSONB semantic mirror。

## 一筆員工來源的 durable 順序

1. 驗證 application-issued document UUID、stable source ID 與 payload hash。
2. 先把 immutable source 以 `pending` 寫入文件專屬 Store namespace；修正與被取代來源用同一 Store batch 更新。
3. 以 LangGraph command 在一個 checkpoint 加入 source reference／lineage 與 semantic revision。provider 不在本 Task，也不會持有 DB transaction。
4. 將 Store source 標為 `committed`。若在兩個 crash window 任一處失敗，同一 source ID 重播只補缺少的步驟；其他新訪談輸入先被擋住。

只有 employee turn 與真的 authority direct edit 可鑄成 evidence source。模型文字、accept／reject／defer 與未啟用的 Reference 都不是來源種類。employee turn 的前後空白與換行按原樣保存並以原始 bytes 計 hash；quote range 也不做 trim。direct edit 只走明確允許的員工文字欄位，保存員工實際改寫的文字及其 JSON-pointer-like path，不把系統 UUID、enum、整份文件或未改文字複製成來源。核准 OPKS 引用的 evidence ID 必須能在同一文件 Store namespace 找到，或正是該次 direct edit 即將建立的來源。

## 安全與生命週期

- Saver 使用 `JsonPlusSerializer(allowed_msgpack_modules=None, pickle_fallback=False)`；等價於官方 strict msgpack allowlist。
- 官方 connection factory 提供 `autocommit=True`、`prepare_threshold=0`、`dict_row`；整合測試直接驗證。
- Windows 的 psycopg async connection 要求 Selector event loop；`run_live.py` 與獨立 storage setup entrypoint 都必須在建立 loop 前設定，不能只靠 pytest fixture。
- Saver／Store `.setup()` 可重跑；Caliburn catalog schema 只由 Alembic 管理。
- Catalog migration 使用 Alembic schema primitives 與具名 constraint／index，不以 `IF NOT EXISTS` 掩蓋 schema drift；每次成功寫入 semantic revision 後更新 catalog `updated_at`。
- 同一 process 以 document UUID admission lock 序列化 semantic writer；revision 再阻止 stale command。
- 刪除先 tombstone catalog，再清 checkpoint thread 與完整 Store namespace；重跑仍安全。
- Store namespace 不接受自由字串，只能由 application-issued UUID 組成。

## 模型執行

- Versioned model profile 只決定 requested model、唯一 provider、有效參數與 timeout；versioned run policy 只決定 eligible Skills／tools、context／call／token／time／cost budget 與 retry。兩者在每次 run 前解析成 immutable `ResolvedExecution`，Skill 不能選模型。
- `ChatOpenRouter` 承接 provider wire，`create_agent`／`response_format` 承接 bounded loop 與 structured output；model／tool call limit、retry、非權威摘要與唯讀工具結果清理由 LangChain built-in middleware 承接。OpenRouter SDK 自己的通用 retry 關閉；LangChain 1.3.15 `SummarizationMiddleware` 內建的獨立三次 retry 也由窄 subclass 關閉，所有主推論與摘要共用同一個 run attempt budget，避免框架內部出現無紀錄重試。
- 第一版固定單一 route 且禁止 fallback。adapter 保留 OpenRouter 回傳的實際 provider、model 與 cost；LangChain callback 對每個真實 attempt 各寫一張含 primary／summarization kind 的 payload-free receipt與 OpenTelemetry span。成功 attempt 若缺 route、usage，或在啟用 cost budget 時缺 cost，deterministic verifier 會在 semantic commit 前 fail closed。provider error 只保留安全分類／HTTP status，不把原始例外訊息或可能回顯的員工內容寫入 receipt／telemetry。
- `SummarizationMiddleware` 與 `ContextEditingMiddleware` 只處理非權威對話副本／舊唯讀 tool result；不能成為員工原話、核准文件或顧問理解的 owner。

## 最小充分 Context

每次實際模型推論都由 middleware 依目前 checkpoint snapshot 與 Store 重建 Context，不持久化第二份 Context packet：

1. bounded global orientation 讓模型知道目前已辨識的工作範圍、有效工作假說、核准 Duty／Task、目前工作、Gap 與待審數量；它不是只看核准文件，也不把舊版／retired 理解重新送回模型；
2. 載入目前焦點的核准文件 slice、目前有效且與焦點相關的可修訂理解、具體 Gap、待審 handles、最近有界顧問回合與必要澄清；
3. checkpoint message 只留帶 stable source ID 的 placeholder；本輪員工原話每次從 Store 逐字重載到明標「不可信 evidence」的 authority Context，明確 required evidence 必帶，相關近期來源在 token budget 內加入；
4. 只有本輪、required 與近期相關來源的 stable lookup handle 進 prompt；更早來源不列出全部 ID，模型可透過同文件 lexical search 再以 ID／correction lineage 按需讀取。現階段沒有設定 semantic index，也沒有連接 Reference／RAG bounded context；
5. Context selection receipt 只存 ID、hash、原因、revision、Skills、token 與降級資訊，不複製員工文字。

明確降級順序是：先捨棄非權威 dialogue summary，再壓縮 global orientation，再把最近兩個顧問回合縮成正在回答的上一回合，再略過超出預算的近期候選來源。本輪原話、required evidence、必要澄清、blocking Gap、焦點理解與焦點核准 slice 不會被摘要取代；這些 mandatory 內容本身超出 budget 時直接回 typed error。即使 LangChain 已把舊 message history 摘要化，middleware 仍會從 Store 重建 authority Context；tool loop 後續推論不會把員工回答重複追加到 ToolMessage 後面。

## 專業分析 Skills 與模型結果閘門

同一位主要顧問按當輪 eligibility 組合九個版本化方法 Skill：工作盤點、故事訪談、Task 邊界、Duty 分組、O、P、K、S 與完成度反方檢查。Skill 是方法與 context 載入邊界，不是多 Agent、固定 stage 或各自擁有狀態的子系統；Task 不必先永久穩定，已有局部證據即可同輪分析相關 O／P／K／S，後續結構變動再重驗 linkage。

- Deep Agents `SkillsMiddleware` 只掃描本輪選定 Skill 的 frontmatter；`FilesystemMiddleware(tools=["read_file"])` 提供唯一模型工具。production 使用自訂 `BackendProtocol` adapter 直接讀 package resources，不使用 host `FilesystemBackend`，也不暴露 ls／glob／grep／write／edit／delete／execute／subagent。
- `/skills/<id>/SKILL.md` 是唯一可讀路徑。backend 拒絕 traversal、未選 Skill、分頁式不完整讀取與同 run 第二次讀取；metadata discovery 不算模型讀取。互動 agent 不另接 checkpointer／Store，durable product graph只保存 semantic result／receipt；每次 invocation 重新投影 eligible metadata，並拒絕外部輸入夾帶舊 `read_file` ToolMessage，因此前一輪 Skill 全文、metadata 或 load warning 都不能流入本輪。
- interactive policy 最多三次 model call、兩個 lookup wave；同一個模型回應中平行載入數個 Skill 算一波，不把「多個方法可組合」錯誤限制成最多兩個 Skill。LangChain 既有 `ModelCallLimitMiddleware`／`ToolCallLimitMiddleware` 繼續管 call／tool 總量，Caliburn 只補框架沒有的「wave」語意。
- LangChain `response_format` 直接產生 Pydantic `ConsultantResult`：員工可見回覆、可修訂理解 delta、動態注意力／待處理 delta、具體 Gap、待員工審核的文件變更、至多一個主要問題與可重算充分性建議。這個 schema 沒有核准文件欄位、pause／finish lifecycle、Reference、能力級別或 A。
- 每個語意 claim 明列 employee source IDs、quote anchors 與實際使用的 Skill IDs。commit 前 deterministic verifier 驗同文件 scope、current source、quote byte-range、selected／loaded Skill、允許的 document path／operation／payload、O／P 單 Task、K／S 文件層多對多 refs，以及具體數量、法規、SOP、公司規則與外部主張的逐字 anchor。模型文字本身永遠不是 evidence。
- K／S 必須有有效員工 quote anchor；O 可以在操作型工作沒有獨立產出時保持空白，顧問改留下 Task-boundary gap，不為填表補造文件。能力級別與 A 連 model-facing enum 都不提供；職業／行業分類與 iCAP 配發代碼也不在允許的模型文件路徑。

`ConsultantResult.reviewable_document_changes` 是模型語意輸出；application 會把它轉成可審核的 typed patch action，配置 stable action ID、before／after、path read-set、dependency 與必要時的 atomic subgroup。模型仍不能直接寫入核准文件；只有員工 review command 或 direct edit 能進入 document authority graph command。

## 文件審核、authority 與必要澄清

LangGraph checkpoint、`StateGraph` command 與 `interrupt()`／`Command(resume)` 直接承接持久化佇列、流程恢復與必要澄清的暫停點；Pydantic 直接承接 typed action／command validation。Caliburn 不再維護另一套 Proposal workflow engine，僅保留框架不知道的文件與職務分析政策：

- 每個模型文件變更都可接受、員工修改後接受、拒絕或延後；同一展示 bundle 內的無關 action 可獨立決定，只有會造成非法中間態的明示 atomic subgroup 才全有或全無。
- `ADD`／`REVISE`／`WITHDRAW`／`MERGE`／`SPLIT`／`REASSIGN`／`REORDER` 都經 stable-ID path、before／after 與 path read-set 驗證。模型可處理職稱、工作描述、Duty、Task、順序與 O／P／K／S；能力級別、A 與官方代碼不在 model-authored path。
- unresolved Duty 結構或 Task 歸類只阻擋相依工作；安全旁支可繼續。審核結束只移除自己的 blocker，不會誤清必要澄清或理解校準 blocker。
- dependency 表示先後條件，不自動等於 atomic；例如新 Task 可先接受，依賴它的 OPKS 後接受。Duty 建立與對應 reassignment、merge／split 清理及必要排序交換才組成 atomic subgroup。
- direct edit 與 edit-accept 只有員工實際改寫的 delta 會成為新的 employee source。單純接受、拒絕或延後不是工作事實，不製造 evidence。
- 員工更正來源時，只把直接依賴該來源的 pending action 標 stale，並連帶失效同一 atomic subgroup；其他待審內容、其他 blocker 與核准文件不變。被拒內容沒有新相關 evidence 時不能換句話重新提案。
- 必要澄清只用在模型無法安全自行消解的重大歧義。它有原因、目前理解、選項與 affected branch；回答會成為員工 evidence，但不會順便接受文件變更。既有澄清未答前不得被下一輪模型替換，員工仍可直接編輯、補來源或繼續不相依的訪談。

真正的文件權威仍是一份 `ApprovedJobDocument`，但它不是舊 Current JD 元件的相容層：它是新 graph state 中由 deterministic authority command 唯一可修改的核准產物。框架負責 durable execution；Caliburn 只定義這份職務說明書什麼變更合法、誰有權核准，以及 evidence 如何約束變更。

## Adaptive interview、理解校準與可信進度

LangGraph `StateGraph`、typed checkpoint、`add_messages` reducer 與 PostgreSQL Saver 直接承接跨回合 routing、自然恢復、可見顧問回覆與 semantic transition；沒有另建自寫 session／pause／resume／finish engine。每個通過驗證的 `ConsultantResult` 由一個 deterministic node 在同一 checkpoint 一起提交：

- 一段可見顧問回覆與 run receipt；
- 有 stable identity／version／source dependency 的可修訂理解；
- 一個當前訪談重點、可見旁支與待處理工作；
- 具 reason code 的 Gap 與待審文件語意草稿；
- 可重算的理解校準與足夠性投影。

員工更正來源時，只把直接依賴舊 source 的理解標成 challenged、把相依工作提高為 correction priority，並使既有足夠性失效；無關理解、工作與來源歷史保持不變。工作或假說可以在 Task 尚未永久穩定時同時出現 Duty／O／P／K／S 變化，模型不能藉此改寫核准文件。

「AI 目前理解」是常駐、可收合 projection，不是第二份文件。一般新線索不跳卡；有意義修訂、久後返回或真正焦點切換可出 soft calibration，矛盾、高風險責任與結構前提才只阻擋相依 branch。確認會建立 employee source lineage 並把理解標成 employee-confirmed，但不接受任何文件變更；直接修正仍走新的員工來源，稍後處理不會變成完成或暫停狀態。

進度由同一 checkpoint 重建三個並列視角，不存假百分比：

1. 目前已知工作 coverage 與各自狀態；
2. 每個工作範圍的 Task boundary、Duty、O、P、K、S 分軸 depth；只把實際正在分析的軸標成 interviewing，Task 足夠不會連帶把 Duty／OPKS 標成足夠；
3. 待員工決定的文件變更，以及可展開的 Gap／reason code。

「目前已足夠」是 deterministic evidence 與模型白話判斷的交集：至少不能有 active／unvisited 工作、blocking Gap 或未決結構變更，且模型要說明理由、剩餘缺口與繼續訪談最可能改善之處。它不關閉對話、不建立 close／reopen lifecycle，也不等於匯出 readiness；新員工來源或 direct edit 會立刻標記需重新計算。

## 當前邊界

這個新 runtime 已有可替換模型 profile、LangChain agent harness、attempt receipt、Context middleware、真實顧問 Skills、adaptive interview routing、可見理解／Gap／語意進度、完整文件 patch／review command、deterministic authority 與 required-clarification interrupt。尚未完成的是 production API／跨語言契約、員工 Web 工作面、匯出接線與舊 production composition 的最終 hard cut。它沒有 RAG／Reference、能力級別／A 生成或正式品質 eval；舊 production composition 只維持到垂直切片完成，最終硬切後刪除，不雙寫。
