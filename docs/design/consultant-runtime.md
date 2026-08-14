# AI 職務顧問 runtime 設計

- 決策：[ADR 0060](../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)；Task 10 schema 修正：[ADR 0061](../adr/0061-compact-consultant-wire-progressive-skills-and-tools.md)；Tool 邊界：[ADR 0062](../adr/0062-bounded-consultant-read-tools-and-structured-authority.md)
- 狀態：Task 9 composition hard cut 已完成；目前 production 僅保留 LangChain／LangGraph 顧問 runtime、purpose-first API／Web、fresh-root storage 與 deterministic export。Task 10 已把 28 optional／20 union 的 rich provider schema 換成 0 optional／0 union／0 open object、depth 4 的 compact Pydantic wire＋pure mapper；ADR 0062 已把 model-facing surface 收斂為四個唯讀 Tool 與依賴驅動 lookup。GPT-5.6 Luna 第一輪付費 smoke、員工校準／文件審核及 live 缺口修復已完成；同 source 第二輪最終重跑仍待重新注入本機 OpenRouter key，UI smoke、正式品質 eval、最終複審與交付標記也尚未完成。
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
- 每個 HTTP authority command 另有 checkpoint-owned command receipt。receipt 綁定 stable command ID、command kind 與 canonical payload hash；精確重送在 revision 檢查前回放成功，同 key 換 payload 直接拒絕。receipt 與 authority update 在同一 LangGraph checkpoint，不另建 idempotency table；若 Store source 已先寫但 committed status 尚未補完，精確重送只完成該 crash reconciliation。
- 刪除先 tombstone catalog，再清 checkpoint thread 與完整 Store namespace；重跑仍安全。
- Store namespace 不接受自由字串，只能由 application-issued UUID 組成。

## 模型執行

- Versioned model profile 只決定 requested model、唯一 provider、有效參數與 timeout；versioned run policy 只決定 eligible Skills／tools、context／call／token／time／cost budget 與 retry。兩者在每次 run 前解析成 immutable `ResolvedExecution`，Skill 不能選模型。
- `ChatOpenRouter` 承接 provider wire。rich application result 不直接送 provider；LangChain `response_format` 使用 compact Pydantic `ConsultantModelOutput`，再由 fail-closed pure mapper 還原 rich `ConsultantResult`。Evidence 只在 `analysis_bases` 出現一次，回覆與各 effect 用 1-based ordinal 引用；越界、未引用與矛盾 payload 都拒絕。同一位顧問、同一 model profile 的 bounded `create_agent` loop 維持不變；四個唯讀 Tool 與 Skill progressive disclosure 依 ADR 0062，tool-free contingency finalization 只有 exact conformance 仍失敗時才評估。
- structured-output strategy 是 versioned model profile 的已解析能力，不由 LangChain 自動猜測或 fallback。現行 `ToolStrategy` 曾產生錯誤的多重輸出工具呼叫，因此 Opus 5／OpenRouter profile 只能選通過 exact conformance 的 provider-native strategy；換模型／provider 也必須重跑窄 canary。這保留可換模型，同時避免把所有 strategy 假定為可互換。
- model／tool call limit、retry、非權威摘要與唯讀工具結果清理由 LangChain built-in middleware 承接。OpenRouter SDK 自己的通用 retry 關閉；LangChain 1.3.15 `SummarizationMiddleware` 內建的獨立三次 retry也由窄 subclass關閉，所有 primary／必要 contingency finalization／摘要共用同一個 run attempt budget，避免框架內部出現無紀錄重試。
- 第一版固定單一 route 且禁止 fallback。依 [OpenRouter Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata) 的正式介面，adapter 送出 `X-OpenRouter-Metadata: enabled`，只從 permissive-decoded `openrouter_metadata.endpoints.available[].selected` 保留實際 provider／model，另保留 usage cost；LangChain callback 對每個真實 attempt 各寫一張含 primary／summarization kind 的 payload-free receipt與 OpenTelemetry span。成功 attempt 若缺 route、usage，或在啟用 cost budget 時缺 cost，deterministic verifier 會在 semantic commit 前 fail closed。provider error 只保留安全分類／HTTP status，不把原始例外訊息或可能回顯的員工內容寫入 receipt／telemetry。
- `SummarizationMiddleware` 與 `ContextEditingMiddleware` 只處理非權威對話副本／舊唯讀 tool result；不能成為員工原話、核准文件或顧問理解的 owner。

## 最小充分 Context

每次實際模型推論都由 middleware 依目前 checkpoint snapshot 與 Store 重建 Context，不持久化第二份 Context packet：

1. bounded global orientation 讓模型知道目前已辨識的工作範圍、有效工作假說、核准 Duty／Task、目前工作、Gap 與待審數量；它不是只看核准文件，也不把舊版／retired 理解重新送回模型；
2. 載入目前焦點的核准文件 slice、目前有效且與焦點相關的可修訂理解、具體 Gap、待審 handles、最近有界顧問回合與必要澄清；
3. checkpoint message 只留帶 stable source ID 的 placeholder；本輪員工原話每次從 Store 逐字重載到明標「不可信 evidence」的 authority Context，明確 required evidence 必帶，相關近期來源在 token budget 內加入；
4. 只有本輪、required 與近期相關來源的 stable lookup handle 進 prompt；更早來源不列出全部 ID，模型可透過同文件 `employee_source_search`，再以 `employee_source_get`／`employee_source_lineage` 按需讀取。model-facing 名稱不綁 lexical backend，但現階段沒有 semantic index，也沒有連接 Reference／RAG bounded context；
5. Context selection receipt 只存 ID、hash、原因、revision、Skills、token 與降級資訊，不複製員工文字。

明確降級順序是：先捨棄非權威 dialogue summary，再壓縮 global orientation，再把最近兩個顧問回合縮成正在回答的上一回合，再略過超出預算的近期候選來源。本輪原話、required evidence、必要澄清、blocking Gap、焦點理解與焦點核准 slice 不會被摘要取代；這些 mandatory 內容本身超出 budget 時直接回 typed error。即使 LangChain 已把舊 message history 摘要化，middleware 仍會從 Store 重建 authority Context；tool loop 後續推論不會把員工回答重複追加到 ToolMessage 後面。

## Model-facing Tool 與 authority 邊界

第一版只暴露四個小型、靜態、唯讀 Tool：

| Tool | 唯一目的 | 模型提供的輸入 |
|---|---|---|
| `read_file` | 完整讀取一份本輪 eligible 的職務分析 Skill | exact `/skills/<skill-id>/SKILL.md` path；`offset`／`limit` 省略 |
| `employee_source_get` | 已知 stable ID 時取回一筆員工原話 | `source_id` |
| `employee_source_lineage` | 原話被更正／取代時取回完整 lineage | `source_id` |
| `employee_source_search` | 不知道 ID 時搜尋同文件目前有效原話 | `query` |

`document_id`、權限、source namespace 與搜尋上限由 application 注入。來源回傳保留 stable ID、exact text、speaker、validity、timestamp 及 correction pointers；跨文件與不存在來源 fail closed。Tool 定義數只有四個，沒有 Tool Search、MCP catalog、keyword router、另一個 LLM selector 或 provider beta。

Tool Calling 不承載文件 authority：ADD／REVISE／WITHDRAW／MERGE／SPLIT、重新歸類與排序都在 provider-native Structured Output 中成為 typed review draft；accept／edit-accept／reject／defer 是員工透過 API 發出的 LangGraph command，模型不能呼叫。必要澄清同樣由 Structured Output 表達，再用 `interrupt()`／`Command(resume=...)` 處理；Focus、Gap 與 Progress 是 durable state／projection，不是 Tool。

lookup 由當下資料依賴決定：context 足夠可零呼叫；彼此獨立的 Skill／員工來源可在同一 model response 平行讀取；只有前一波結果產生新依賴才用第二波。最多三次 model call、兩個 lookup waves 與總 Tool／token／time／cost budget 不變。

## 專業分析 Skills 與模型結果閘門

同一位主要顧問按當輪 eligibility 組合九個版本化方法 Skill：工作盤點、故事訪談、Task 邊界、Duty 分組、O、P、K、S 與完成度反方檢查。Skill 是方法與 context 載入邊界，不是多 Agent、固定 stage 或各自擁有狀態的子系統；Task 不必先永久穩定，已有局部證據即可同輪分析相關 O／P／K／S，後續結構變動再重驗 linkage。

第一版可把九個方法的短 metadata catalog 交給 `SkillsMiddleware`，讓同一模型依完整員工回答發現意外的 Task／Duty／OPKS 線索；progressive disclosure 的節省點是只有實際使用的 `SKILL.md` 正文進 context。catalog 中的 Skill 是 **eligible／可發現**，不是 selected／已載入；`PackageSkillBackend.loaded_skill_ids` 與 verifier 必須證明 result 只引用真正完整讀過的方法。若日後 metadata catalog 本身造成可量測的品質／成本問題，再用 typed state narrowing；不得先用脆弱關鍵字 router 或另一個 LLM selector 阻止跨焦點發現。

- Deep Agents `SkillsMiddleware` 只掃描本輪 eligible Skill 的 frontmatter；`FilesystemMiddleware(tools=["read_file"])` 提供唯一 Skill 讀取工具，並以原生 `custom_tool_descriptions` 改成只描述完整讀取 `/skills/<id>/SKILL.md` 的短產品 contract，不把 editing／PDF／paging 等未開放能力送給模型。production 使用自訂 `BackendProtocol` adapter 直接讀 package resources，不使用 host `FilesystemBackend`，也不暴露 ls／glob／grep／write／edit／delete／execute／subagent。
- `/skills/<id>/SKILL.md` 是唯一可讀路徑。backend 拒絕 traversal、未選 Skill、分頁式不完整讀取與同 run 第二次讀取；metadata discovery 不算模型讀取。互動 agent 不另接 checkpointer／Store，durable product graph只保存 semantic result／receipt；每次 invocation 重新投影 eligible metadata，並拒絕外部輸入夾帶舊 `read_file` ToolMessage，因此前一輪 Skill 全文、metadata 或 load warning 都不能流入本輪。
- interactive policy 最多三次 model call、兩個 lookup wave；同一個模型回應中平行載入數個 Skill／source 算一波，不把「多個方法可組合」錯誤限制成最多兩個 Skill，也不固定第一波 Skill、第二波 Source。LangChain 既有 `ModelCallLimitMiddleware`／`ToolCallLimitMiddleware` 繼續管 call／tool 總量，Caliburn 只補框架沒有的「wave」語意。
- compact provider wire 保留員工可見回覆、可修訂理解 delta、動態注意力／待處理 delta、具體 Gap、待員工審核的文件變更、至多一個主要問題與可重算充分性建議；全欄 required，以明確 enum、中性 payload／空陣列降低 grammar，而不是刪能力。模型不再組自由 JSON Pointer 或任意 `after`；typed target／stable ID／field／payload 經 pure mapper 還原，sentinel、ordinal、payload 或 OPKS linkage 矛盾即拒絕。provider field 使用不歧義的 `top_level_value`／`whole_entity`；新實體 ID 與 collection-local order 由 application 配置，每個 ADD 是可獨立審核的一個實體，ADD target key 另含 canonical payload hash，避免同來源多個候選互相碰撞。單一 OPKS ADD 的 change-level linkage 是唯一權威；item 內為 MERGE／SPLIT replacement 保留的 strict-schema linkage slot 在 ADD 時只是中性占位，不得形成第二份權威。provider wire 沒有核准文件欄位、pause／finish lifecycle、Reference、能力級別或 A。
- 每個語意 claim 明列 employee source IDs、quote anchors 與實際使用的 Skill IDs。commit 前 deterministic verifier 驗同文件 scope、current source、quote byte-range、selected／loaded Skill、允許的 document path／operation／payload、O／P 單 Task、K／S 文件層多對多 refs，以及具體數量、法規、SOP、公司規則與外部主張的逐字 anchor。模型文字本身永遠不是 evidence。
- K／S 必須有有效員工 quote anchor；O 可以在操作型工作沒有獨立產出時保持空白，顧問改留下 Task-boundary gap，不為填表補造文件。能力級別與 A 連 model-facing enum 都不提供；職業／行業分類與 iCAP 配發代碼也不在允許的模型文件路徑。

`ConsultantModelOutput.reviewable_document_changes` 是 provider-facing typed semantic target／field／payload；pure mapper 先轉成 `ConsultantResult.reviewable_document_changes`，application 再建立可審核的 typed patch action，配置 stable action ID、before／after、path read-set、dependency 與必要時的 atomic subgroup。模型仍不能直接寫入核准文件；只有員工 review command 或 direct edit 能進入 document authority graph command。

## 來源支持、引用與執行證據

新 runtime 不建立單一 `EvidenceEngine`。通用責任直接使用成熟 primitive，只有產品無法外包的來源 authority／語意支持規則留在 `app.consultant`：

| 目的 | 機制 |
|---|---|
| 員工原話、更正與精確找回 | LangGraph `AsyncPostgresStore`＋checkpoint source refs |
| 模型回覆 citation transport | LangChain v1 `Citation` annotation；只在 adapter conformance 通過時啟用 |
| 員工來源內文字位置 | W3C Web Annotation `TextQuoteSelector`＋`TextPositionSelector` 對齊的 selector shape |
| quotation／revision／invalidation lineage | W3C PROV 語彙；不新增 RDF store |
| typed claim 與引用形狀 | LangChain structured output＋Pydantic validators |
| provider／tool 執行證據 | LangChain callbacks＋OpenTelemetry GenAI＋payload-free attempt receipt |
| 員工文件決策／恢復 | LangGraph checkpoint／`Command`／必要時 `interrupt` |

LangChain `Citation.start_index／end_index` 指向模型**回覆**文字，不能冒充來源內 offset。employee source 是 immutable，已有 stable source ID 與 `text_sha256`；核心 anchor 以 W3C-aligned exact quote＋Unicode start/end＋document scope 即可重驗，prefix／suffix 只作未來跨格式 projection 的選配。Anthropic 原生 citations 與 structured outputs 不能在同一 request 使用，剛好再次支持 analysis／finalization 分離；但目前 `langchain-openrouter==0.2.7` 的 response converter 未保留 citation annotations，所以第一版不依賴原生 citation。核心 truth 仍是 Store source＋W3C-aligned selector＋Pydantic result＋deterministic verifier；原生 citation 日後只能作可驗證的 analysis-stage enhancement，不能成為第二份來源或提前接 RAG。

deterministic verifier 仍判定：source 是否存在且 current、quote 是否逐字且同 document、speaker／capture mode 是否有權威、claim 是否使用已載 Skill、官方代碼與 document path 是否允許、Task／Duty／OPKS linkage 是否合法。框架 citation 只證明「指到哪裡」，不替產品判斷該段是否真的支持職務分析 claim。

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

## 跨語言契約與 API transport

新 `/api/v1/job-analysis/consultant-documents` surface 只輸出 purpose-first projection，不暴露 checkpoint raw state、command receipt、Context selection 或 model attempt 內部資料。JSON Schema 生成 Pydantic 與 TypeScript 型別；FastAPI native SSE 只發送帶 revision／run ID 的 refetch notification， durable snapshot 才是狀態權威。

- 建立／讀取／刪除文件、202 source-first answer admission、snapshot、review、calibration、required clarification、direct edit 與單一 export 都走同一 application-scoped runtime；同文件 admission lock 不再因 request-local dependency 而失效。
- model factory 只在 composition root 注入；`app.consultant` 不直接依賴 OpenRouter adapter。三個 LangChain employee-source tools 已接到真正 agent surface，且只允許同文件 stable-ID get／correction lineage／bounded search；目前 search backend 仍是 lexical，沒有 semantic retrieval、Reference 或 RAG tool。
- export readiness 有具體 gap 時回 409，員工以同一入口 `force=true` 明確確認後仍可匯出；pending changeset 不會被匯出或暗中接受。
- production 只保留 `/consultant-documents` surface；舊 route、舊契約定義與舊 writer 已在 Task 9 同一 hard-cut 移除。沒有 DTO alias、雙寫或 compatibility layer。

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

## 員工顧問工作區

Next App Router 頁面只負責掛載 purpose-first Client Component；TanStack Query 管文件庫與 durable snapshot 的 server cache、mutation 與 invalidation，瀏覽器標準 `EventSource` 只負責斷線重連與通知 refetch。Web 不保存第二份訪談狀態，也不解讀 raw LangGraph checkpoint、interrupt、attempt receipt 或 Context receipt。

- 首頁建立或重開彼此隔離的職務文件；關閉頁面只是停止互動，下次直接由 durable snapshot 恢復，沒有 pause／resume／finish 操作。
- 同一工作區清楚分開「訪談對話」「AI 目前理解／焦點／Gap／語意進度」「AI 待審文件變更」「員工核准正式文件」。必要澄清只顯示 affected branch，回答區與不相依操作不被整頁鎖住。
- 員工逐字回答與更正 lineage 都會在重開後重建為可見對話；`source_saved`、`completed`、`failed` 取自 durable run。相同內容重試沿用原 run／source；若員工要改掉失敗回答，則用明確 `supersedes_source_id` 建立新來源，不能以無關回答繞過 failed-run admission。
- 待審 changeset 支援 accept、edit-accept、reject、defer；atomic subgroup 與 accept 時必要 dependency 由 typed contract 決定。結構化 Duty／Task／OPKS 變更以員工欄位、職責名稱與工作名稱編輯，穩定 ID、來源與內部排序欄位由系統原樣保留，不要求員工修改 JSON。純重新歸類或排序的 edit-accept 不假裝產生員工文字 evidence。UI 不把 JSON pointer、framework state 或內部 enum 當員工進度。
- 正式文件 local draft 是 document-scoped、可在離開／返回後恢復的瀏覽器本機草稿，不是 authority 或第二份 server document store；background refetch 不覆蓋 dirty draft。所有 mutation response 依 semantic revision 單調寫入 TanStack cache，409 會重抓 durable snapshot 並保留本機選取／草稿。送出前會清理已刪 Task／indicator 造成的懸空 OPKS 關聯，server 仍重驗完整 invariant。能力級別與 A 只有員工可直接編輯。
- server 投影的 blocked branch 會顯示實際原因；只有在沒有安全旁支時停用一般 AI 訪談回答。更正原話、文件審核、員工直接編輯與匯出仍可使用，避免把 branch-level blocker 誤做成整頁鎖定。
- 匯出只有一個入口；有具體 readiness gap 時先顯示問題，員工明確確認才以 `force=true` 匯出目前核准內容。待審變更不會暗中被接受。

目前 UI 沒有 RAG／Reference 控制、consumer 或提示；同文件 stable-ID 原話查詢仍是顧問記憶的一部分，不等於外部知識檢索。

## 當前邊界

這個 runtime 已有可替換模型 profile、LangChain agent harness、attempt receipt、Context middleware、真實顧問 Skills、四個受限唯讀 Tool、adaptive interview routing、可見理解／Gap／語意進度、完整文件 patch／review command、deterministic authority、required-clarification interrupt、generated contract／production API transport、員工顧問工作區與 deterministic XLSX export。Task 9 已完成舊 composition／writer／route／contract／migration hard cut；fresh root 只建立最小 catalog，LangGraph 官方 setup 擁有 Saver／Store tables。Task 10 的 compact provider wire＋pure mapper 與 ADR 0062 Tool surface 已完成 focused gates；GPT-5.6 Luna 第一輪付費 smoke 已驗證真實 route、使用量、員工審核與文件 authority，第二輪則實際找出並修正 OPKS wire 缺口，最終同 source retry 仍待本機 key。它沒有 RAG／Reference consumer、能力級別／A 生成或正式品質 eval，也沒有雙寫或 compatibility layer。
