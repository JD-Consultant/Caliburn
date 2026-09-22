# A 證據與 JD 來源接線施工計畫

- 日期：2026-09-20
- Topic：`JD-R002 / MEM-L001 / A-R001`
- 依據：[跨顧問、Memory 與 JD 的模型安全證據契約](../specs/2026-09-20-cross-agent-evidence-and-jd-context-contract.md)
- Stage：G7 Task 6 離線驗收完成；Task 0–5 已完成；自然模型、完整瀏覽器旅程與 production authority 仍是後續 gate
- 範圍：A model-view、Working State source handles、JD model adapter、layered C read proof、request-only compaction／resume 回歸

## 1. 不變量

- 不新增 Agent、資料表、Memory 層、source owner、queue、provider 或 credential。
- 不改 B1／B2 已驗 stage／publication 語意；只跑相鄰防退化測試。
- 不改 relational JD domain／DB schema、共同人機業務邏輯、transaction、receipt 或撤回範圍。
- 不把 summary、Working State、案例或理解升格為 canonical 原話。
- 不做付費模型、production 切換、完整瀏覽器或任意歷史功能。

## 2. Task 0：先固定每個 model schema 的參數 owner

施工前依[共同權責表](../specs/2026-09-20-cross-agent-evidence-and-jd-context-contract.md#3-模型runtime-與程式的完整參數權責)逐一列出正式 schema diff 並以契約測試固定：

1. 模型只撰寫語意內容，或選 Runtime 已發出的 handle／enum；不能產生 scope、version、source locator、cursor state、ID、digest、position、receipt 或執行政策。
2. `ToolRuntime`、document／run、Memory basis、JD base、operation、new IDs、source resolution 與 read proof 必須由 composition root／middleware／domain 注入或推導，不出現在 model-generated arguments。
3. 保留既有 JD read 的窄例外：模型可原樣帶回 App-issued cursor 表示續頁，但 App 擁有 cursor、綁定版本及下一頁位置；A／B1／B2 evidence read 不採此例外。
4. Working State 尚未實作，先固定 create／patch／lifecycle 最小輸入，不把完整 stored object 交模型重填。
5. 紅燈必須證明額外 Runtime 欄位、未知／跨 scope handle、模型自造 ID／cursor 與矛盾 lifecycle input 在任何 stage／domain effect 前被拒絕。

以下原 Tasks 1–6 順延為施工序列；Task 0 只固定契約，不新增產品功能。

## 3. Task 1：固定 model-view 隱私與 key 生命週期紅燈

新增最小反例，證明目前 A request 仍可看見／回填 signed refs，並固定目標：

1. `read_case` model content 不得含 signed ref、Memory version、offset／cursor；private artifact 必須完整保留。
2. 同 run resume 後同一 scope/source key 不漂移；新 run 重新發配。
3. 同 source 支持兩案例時 keys 不同，case A 的 read proof 不滿足 case B。
4. 未知／跨 run／跨 document key 在任何 tool/domain effect 前拒絕。
5. 正式 OpenRouter request serialization 不包含 private artifact。

先保存首敗；不直接 mock 最上層 Agent 回一個整理好的 ToolMessage。

## 4. Task 2：A read tools 的 content／artifact 分工

1. 以鎖定 LangChain `content_and_artifact` 建立 A evidence record。
2. `read_case` 返回案例正文＋owner-ordered keys；artifact 保存 case/source、固定 Memory basis、順序與 cursor。
3. 新 model-facing `read_evidence(evidence_key)` 重用既有 source owner，取代 raw-reference `read_conversation`；模型不填 offset。
4. 連續分頁、完成 proof、Unicode／角色／換行與錯誤分類沿既有 source reader，不另造 parser。
5. `layered_read_proof` 從可信 artifacts／checkpoint-private records 重建，不相信 model content。

## 5. Task 3：Working State source projection

1. 持久 Working State 繼續保存 formal source refs；model-view 改發 evidence keys。
2. model tool 的 source 欄位改收 `source_evidence_keys`，由 Runtime 解析、驗 scope／read status 後保存。
3. related case／understanding／JD handles 保持既有語意。
4. 覆蓋第一輪無 Memory、跨回合恢復、partial answer、park／reopen、captured-pending-memory 與 remove reason。

## 6. Task 4：JD model contract 與共用 domain 接合

1. 從正式契約 SSOT 修改 model input，將各 mutation 的 `basis_refs` 改成 `basis_evidence_keys`，再生成 Python／TypeScript；不手改生成檔。
2. A adapter 在 domain command 前解析 keys 成 canonical refs；operation digest 使用 resolved refs。
3. current-turn visible evidence 可使用；較早來源須 complete read。
4. `jd_read`／`jd_change_read` 的 model projection 隱藏 source refs，顯示 keys＋basis/readability 狀態；內部與人類 UI owner 不改。
5. domain、source resolver、`jd_source_link`、basis digest、transaction、receipt、change read 與整輪 JD 撤回保持不變。
6. 補同一 employee source 支持多個 JD targets、空 evidence 保留舊 links、non-empty refresh、stale JD base 與 operation reconcile 反例。

## 7. Task 5：C、compaction 與恢復接合

1. C 只接受 A 已讀且屬同一 latest Memory 基準的 case-bound keys；現有 stable-ID schema 及完整 bundle CAS 不改。
2. request-only compaction 後由 Runtime 重投影 active evidence catalog；summary 不建立 key、read proof 或 JD basis。
3. checkpoint serialization／deserialization、graph rebuild、取消／中斷與新程序恢復後 mapping 仍一致。
4. artifact 缺失、被篡改、格式未知或 tool identity 不符時 fail closed；不 fallback raw token／latest。

## 8. Task 6：受影響驗證與文件收尾

最小測試集合依實際 import graph決定，至少包括：

- A Memory context／typed reads；
- Working State；
- JD generated contract、tools、source links、operation binding／reconcile；
- layered C admission／read proof；
- request-only compaction、OpenRouter request capture、checkpoint resume；
- B1／B2 evidence contract 的相鄰防退化集合。

完成後記錄首敗、最終結果、跳過項及未驗項；更新 current decisions 與本計畫結果。沒有新的程式差異或可重現風險，不重跑完整舊研究考卷。

## 9. 停止線

遇到以下任一情況先回產品／架構討論，不自行擴張：

- 需要新 DB registry、第二個 source owner 或另一套 Memory 才能完成；
- 必須改 B1／B2／C、JD authority 或 compaction 的已確認產品語意；
- 鎖定框架無法可靠保存 private artifact，且只能靠模型回填 raw refs 才能運作；
- generated JD contract 的改動會破壞人工共用 domain，而不能在 model adapter 層隔離；
- 必須切 provider／credential、呼叫付費模型或改 Prompt／Skills 才能驗證核心正確性。

## 10. 交付條件

- raw source refs 不再出現在 A／JD model request；
- keys 不持久進 Memory／JD，resolved refs 與順序正確；
- A／Working State／C／JD 在 compaction、resume、stale 與失敗下保持各自 authority；
- 受影響離線與必要真 PostgreSQL 回歸通過；
- 自然 Luna、完整 browser journey 與 production G6 明確保留為後續 gate。

## 11. 2026-09-21 第一施工單位結果（Task 0–2）

已完成：

1. A 的 layered `read_case`／`read_work_understanding` 改用鎖定框架的 `content_and_artifact`；模型內容不再包含 signed source reference、Memory revision／version、case digest 或 evidence offset。
2. `read_evidence` 的 model schema 只有 Runtime 發出的 `evidence_key`。Runtime 從同一 run 的可信 ToolMessage private artifacts 解出案例、正式來源與下一頁位置；未知、跨 run、跨 document、篡改或 call/result 不一致會在來源讀取及 domain effect 前失敗。
3. key 綁定 dataset／document／run／case／source：同 run resume 對同一案例來源穩定；同一來源支持兩案例時 keys 不同，讀完其中一案不能滿足另一案。
4. layered C read proof 改由 private artifacts 重建，並要求每個 `(case_id, evidence_key)` 都實際讀完；不再相信模型可見內容或 raw-reference 參數。
5. 鎖定 `langchain-openrouter` adapter 的實際轉換測試確認 private artifact 不進 OpenRouter wire；真 PostgreSQL Saver／Store 測試確認 artifact 經關閉重開後仍完整恢復。request-only compaction 回歸確認被摘要取代的是模型 view，canonical ToolMessage artifact 不會被刪除。

驗證：補入 compaction artifact 反例後，受影響離線廣集為 **309 passed／13 skipped／0 failed**，其中核心集合為 **90 passed／0 failed**；明示啟用的精確 PostgreSQL／OpenRouter-wire 合成回歸另為 **1 passed／0 failed**。warnings 是既有 Pydantic context serializer 警告；全程零 provider request、零正式資料、零付費。

本單位未完成、也未宣稱完成：Working State projection（Task 3）、JD generated model contract／adapter（Task 4）、compaction 後 active evidence catalog 的明示重投影與全部恢復情境（Task 5）、自然 Luna、完整 browser journey 與 production authority。舊兩檔讀取 helper 只留作歷史測試程式，未再暴露給正式 layered A 工具集合；沒有新增 DB registry、資料表、Agent、來源 owner 或 Memory。

## 12. 2026-09-21 Working State 核心施工結果（Task 3）

已完成：

1. `ConsultantState`／document checkpoint 增加唯一 typed `interview_working_state`；沿 LangGraph 原生 `Command(update=...)` 合併與既有 Saver 保存，沒有自訂 state merger、資料表、registry、Agent、planner 或 queue。
2. 正式工具只有批次 `update_interview_working_state` 與按 ID 讀取 `read_interview_working_item`。create 只收核心語意，revise 採 patch，park／reopen／mark-captured／remove／set-focus 各自只有一種表達；非法 batch 不部分生效。
3. current-turn 與 Working item 的 model view 只發 Runtime-issued evidence keys。模型不能提交 signed source、document／run、Memory revision、offset、digest、時間或 receipt；Runtime 解析 scope／讀取狀態並在 private checkpoint state 保存正式 refs。
4. Focus 與 correction／conflict item 直接展開；其餘項目保留完整目錄並沿同一 state 的 read-by-ID 工具按需讀取。Working State 不成為 B1／B2／JD evidence，也沒有複製成第二份 Memory。
5. checkpoint-only 更新使用 private ToolMessage receipt 綁定原始參數 digest 與更新後 state digest；App closure 核對最後 digest。真 PostgreSQL Saver 的關閉／重開保留同一 state，request-only compaction 只更新自己的 summary 欄位，不刪 Working State。
6. current-turn 安全 key 的完整 Agent 往返已證明：模型 request 看不到 raw source，工具只提交 key，Runtime 才保存 resolved source。模型工具 schema 亦固定不含 Runtime-owned 欄位。

驗證：受影響離線集合 **334 passed／0 failed**；精確真 PostgreSQL Saver 關閉／重開回歸 **1 passed／0 failed**。warnings 為既有 Pydantic context serializer 與本機 pytest cache ACL；全程零 provider request、零正式資料、零付費。

Owner 已裁決不增加這個候選訊號：Working State 是 A 的訪談工作面，不是 B1／B2 publication 的同步投影。全域 `memory_basis_revision` 已移除；每個 A 回合的固定 Memory 版本仍由既有 Runtime session 管理。背景新版只在與目前訪談相關時，透過 guide／按需讀取造成個別 item 的語意更新；不要求全表掃描或空更新。只有以 `memory_reconciled` 移除個別 item 時，仍須提供本回合固定版本的相關已讀 Memory handle。

裁決落地後的受影響回歸為 **246 passed／14 skipped／0 failed**；另明示啟用的精確真 PostgreSQL Saver 關閉／重開回歸為 **1 passed／0 failed**。skip 是未在該離線集合啟用的 PostgreSQL 案例；warnings 為既有 Pydantic context serializer 與本機 pytest cache ACL。全程零 provider request、零正式資料、零付費。

截至本段記錄仍未完成、也未宣稱完成：JD related handles／generated model contract 與 adapter（Task 4）、compaction 後 active catalog 的全部明示重投影／恢復情境（Task 5）、自然 Luna、完整 browser journey 與 production authority。Task 0–2 的既有證據直接沿用，沒有重做 B1／B2、Memory、Prompt 或 compaction 設計；Task 4 的後續結果見 §13。

## 13. 2026-09-21 JD model adapter 施工結果（Task 4）

### 13.1 已完成

1. 新增獨立的 model-facing generated contract `jd-model-work.schema.json`，由既有 contract generator 產生 Python／TypeScript；人工／domain 的 `jd-work.schema.json` 與 `basis_refs` 不改。模型工具的來源欄位改為 `basis_evidence_keys`，避免模型接觸 signed source locator。
2. A adapter 在 domain command 前將 Runtime-issued `evidence_key` 解析成 canonical `basis_refs`，檢查 scope、同一 run、去重與 read status；operation binding digest 依解析後 canonical arguments 計算，domain、source resolver、transaction、receipt、change read 與撤回語意保持既有實作。
3. `jd_read`／`jd_change_read` 將 source record 投影成 `evidence_key`、basis／readability 狀態及原有順序提示；完整 canonical read result 與 key→source mapping 只留在同一可信 ToolMessage private artifact。模型可看到 `available`，但較早 JD source 尚未經 `read_evidence` 完整讀取時不能提交為 basis；current-turn 原話則沿既有 `visible` 規則可用。
4. JD 的 `read_evidence` 重用既有 conversation source owner、頁面格式與進度 proof，不建立第二個 reader。Memory／B1／B2 的純讀取路徑不會因沒有 JD read 而掃描 JD catalog；既有 layered Memory repair／read flow 保持原語意。
5. 針對舊測試中仍把 `basis_refs` 當模型輸入的夾具，改為提供合法 Runtime-issued key；沒有放寬 production adapter，也沒有把 canonical ref 重新暴露給模型。

### 13.2 審核界線

使用者提供的短代號／Runtime 還原概念可作為參考，但不是本案的新 authority。正式依據仍是 §3 權責表、§5 evidence lifecycle、§7 JD 接合與既有 JD／Memory／source owner 文件。`evidence_key` 是本案的 model-view handle，不是資料庫主鍵、signed reference 的別名，也不是要求 OpenAI／Anthropic 必須採用的固定 schema。

本次沒有新增 Agent、資料表、source registry、queue、Memory 層、provider、credential、Prompt 或 Skills；沒有改 B1／B2／C 的 publication、版本、引用或 compaction 產品語意。短 key 不會持久進 Memory／JD，保存時仍只保存既有 canonical refs。

### 13.3 驗證結果

- contract generation check：通過，Python／TypeScript 產物一致。
- `compileall`：通過。
- 直接相關離線集合（JD transport／provider wire／schema projection／JD command flow／consultant tools／source failure／Memory repair／Working State）：**172 passed／0 failed**；只有既有 pytest cache ACL warning。
- 首輪完整離線集合曾得到 **3024 passed／322 skipped／18 failed／44 errors**。後續已修正其中屬本次 model contract 的舊 fixture／Memory-only catalog 牽連；其餘主要是 Windows Credential Manager／設定檔 ACL 與既有 runtime restart／inspection 類現場，尚未形成完整全套重新驗證，不把它宣稱為全套通過。
- 全程零 provider request、零正式 JD／Memory／對話資料、零付費模型呼叫；沒有 commit／push。

### 13.4 下一個未完成範圍

Task 5 仍只處理 request-only compaction／checkpoint serialize-deserialize／graph rebuild／取消中斷／新程序恢復後，如何由既有 private artifacts 明確重投影 active evidence catalog；summary 不建立 key、read proof 或 JD basis。自然 Luna、完整 browser journey 與 production authority 另列後續 gate，不在本 Task 偷接。

## 14. 2026-09-21 Task 5 施工結果：active evidence catalog 重投影

### 14.1 施工前核對

本單位先核對目前決策、跨顧問 evidence contract、既有 request-only compaction 設計、LangGraph checkpoint／ToolMessage artifact 保存方式，以及現有 A／JD／Memory read path。沒有發現需要重做 Memory、B1／B2、C、JD domain 或 provider 的語意衝突。

OpenAI 官方 Compaction 文件只支持本案的 transport 邊界：compaction 是供下一個模型 request 延續的資料，opaque item／summary 不等於產品來源權威；本案仍以 canonical conversation、private artifacts、Working State 與既有 Memory read proof 為權威。不能把官方的 server-side compaction item 當成 Caliburn 的 `evidence_key` 或 JD basis。

### 14.2 最小實作

1. 將既有 `_a_evidence_catalog` 明確命名為 `reproject_active_evidence_catalog`。它仍只組合既有三個 owner：JD source artifacts、Working State projection、Memory layered read proof；沒有建立第四個 registry、cache 或資料表。
2. A 每次準備 JD mutation 時，仍從當下 checkpoint state 的 canonical `messages` 與 private artifacts 重投影，而不是從模型 request view、compaction summary 或模型回填的 key 取得資料。
3. `read_evidence`、JD adapter 與 C 的既有 scope／digest／cursor／read-status 檢查不改；它們各自沿原有 owner 再驗證，沒有新增平行 resolver。

### 14.3 驗收反例

新增回歸涵蓋：

- compaction 前後 active JD evidence key 與 source mapping 相同；
- ToolMessage private artifact 經 message serialization／deserialization 後仍可重投影同一 mapping；
- detached summary 即使提到某個 key，也不會自行產生 evidence catalog entry；
- private artifact 被竄改時重投影明確 `invalid_jd_evidence` fail closed。

既有 compaction middleware、Working State、Memory read／C proof、JD adapter 及 checkpoint／graph resume 測試直接沿用，沒有重跑不受影響的完整舊研究考卷。

### 14.4 結果與邊界

- 本次直接相關集合與前一施工單位合計 **173 passed／0 failed**；本次新增重投影回歸為 **1 passed／0 failed**。
- `compileall`／contract generation／`git diff --check` 持續通過；全程零 provider、零正式資料、零付費。
- Task 5 的 active catalog 重投影已完成；本切片不宣稱自然 Luna、完整 browser journey、完整 production authority 或 OpenRouter native compaction server capability 已驗證。
- 沒有新增 Agent、資料表、queue、watermark、Memory layer、provider、credential 或 recovery system。

## 15. 2026-09-21 Task 6 離線整體驗收結果

### 15.1 驗收範圍

本單位依 current decision、跨顧問 evidence contract 及本計畫 Tasks 0–5，驗證新 JD App 的整體離線回歸。核對 A、Working State、JD model adapter、B1／B2／C 的既有 evidence／Memory 接點、request-only compaction、checkpoint restore、取消／恢復、設定檔與 App 入口；沒有重新設計 Memory、compaction、B1／B2 或 JD domain。

### 15.2 唯一修正

全套回歸首次仍有 restart／inspection 紅燈。逐步追查後確認是測試夾具把 domain canonical `basis_refs` 直接放進模型 ToolMessage；現行正式 model contract 已要求模型使用 `basis_evidence_keys`，由 Runtime 在 adapter 邊界還原 `basis_refs`。因此只更新 `test_ai_runtime.py` 的合成 receipt fixture，以及 `test_ai_run_inspection.py` 的合成 call fixture；沒有修改 production runtime、DB、Prompt、Memory、provider 或工具語意。

### 15.3 實際結果

- restart／run inspection 受影響窄回歸：**24 passed／0 failed**。
- Windows DPAPI／設定檔與 App operator 入口：**38 passed／0 failed**；使用專案內新的測試暫存位置，避免既有暫存目錄 ACL 造成假錯誤。
- 新 JD App 全套離線回歸：**3080 passed／322 skipped／0 failed／0 error／95 warnings**。
- warnings 仍是既有 Starlette AnyIO deprecation 與 Pydantic serializer warnings；沒有因此改第三方或擴張產品。
- 全程零 provider request、零自然 Luna、零正式 JD／Memory／對話資料、零付費；未做 production authority 切換或 browser journey。

### 15.4 驗收結論與後續界線

Tasks 0–5 的離線接線與目前可驗證的整體回歸已完成，且沒有發現需要新增元件或重開既有設計的衝突。這不等於自然 Luna 品質、完整瀏覽器旅程、production authority 或 OpenRouter 服務端原生 compaction 能力已驗證；這些仍依 current decision 的後續 gate 另行處理。

## 16. 2026-09-22 after-model state 接線追補

### 16.1 發現與最小修正

在以真 managed host／LangGraph／PostgreSQL／Saver、離線合成模型重跑 JD tool 旅程時，`jd_create_task` 在保存前得到 `invalid_memory_session`，writer 沒有執行。逐項診斷確認 Memory session 的 scope、thread、Store identity 與回合 Memory view 都正確；真正不符的是 LangChain node-style `after_model` 的 hook runtime 沒有 `state` 屬性。既有 `reproject_active_evidence_catalog(runtime, state)` 已收到正確 state，卻在內部呼叫 `memory_session(runtime)`，漏掉這個參數。

修正只在同一 projection 接點以既有 validator 讀取 `context`、hook state 與 `runtime.store`；沒有放寬驗證、改 Memory publication 基準或建立新 owner。新增一個 regression test 固定這個框架契約。

### 16.2 結果與界線

- 受影響窄回歸：**62 passed／0 failed**。
- 真 PostgreSQL／Saver／managed host／JD tool 的直接 HTTP 旅程完成 `jd_read → jd_create_task → 無工具收尾`；模型 3 次、writer 1 次、提交成功，稍後查回同一 run 為 `completed`。
- 一次 closure 尚未完成時的查詢得到暫時 `503 service_unavailable`；沒有重送模型或 writer，後續原 run 查回成功。此列為既有查回時序觀察，不改 unknown／receipt 語意。
- Chrome CDP 本輪在瀏覽器啟動階段得到 `chrome_devtools_unavailable`，沒有取得新的 Stable Chrome 頁面證據；完整 browser journey 維持 `UNVERIFIED`。

完整證據見[after-model state 接線驗收](../specs/evidence/jd-relational-ui-restore/2026-09-22-after-model-state-forwarding.md)。

## 17. 2026-09-22 strict wire model-facing adapter 收斂與下一個 test-only gate

### 17.1 研究與正式界線

本段先核對 current decision、Working State 設計、跨顧問 evidence contract、鎖定 LangChain／OpenRouter adapter 與 OpenAI／Anthropic 官方 tool schema 文件；沒有重開 Memory、B1／B2、C、JD domain、Prompt、Skills 或 compaction。官方差異需保留：OpenAI strict 要求每個 object 的 `additionalProperties=false` 且所有 declared properties 列入 `required`；Anthropic 的 user-defined tool schema 可用一般 `required` 清單表達 optional property，即使啟用 strict tool use 也不應直接把其 omission 表達套到 OpenAI-compatible wire。

本案正式不變量為：

```text
沒有 mutation intent → preserve
explicit set        → 修改
explicit clear      → 清除
```

這三者是 Domain mutation semantics，不是由 provider 的 nullable／required 格式決定。模型只表達語意意圖；adapter 只負責 model-facing strict representation 與既有 Domain input 的轉換；Runtime 仍擁有 ID、scope、版本、引用、transition、權限及 persistence；Domain parser／validator 維持 authority。

### 17.2 已取得的零付費證據

使用正式新 JD App 的 `build_consultant_tools()`、鎖定 `openai/gpt-5.6-luna` profile、OpenAI-only provider route、`parallel_tool_calls=false` 與 `bind_tools(strict=True)` 進行離線 wire capture；沒有 provider request、正式資料或費用。結果為 20 個工具、strict=true，並重現 5 類 model-facing schema 缺口：

1. `update_interview_working_state` 的 create variant required 與 properties 不一致；
2. 同工具的 revise variant required 與 properties 不一致；
3. 同工具的 remove variant required 與 properties 不一致；
4. `repair_memory.understanding_updates` 內層 optional properties 未符合 strict required 集合；
5. 零參數 `request_memory_consolidation` 沒有明確的空 `required` 表達；先列為 normalization／completeness finding，不單獨視為已證 strict defect。

這些是 model-facing wire defects，不是已證明 OpenRouter HTTP 400 的唯一根因；自然 Luna 在取得供應商詳細錯誤前仍維持停止線。

### 17.3 下一個 test-only prototype

只在測試／隔離 capture 比較以下候選，不直接改正式 tool schema：

- `explicit changes[]`：每筆明確指出要 set 或 clear 的語意變更；
- `field-mask + values`：由 mask 表達本次 mutation 範圍，值保持與欄位型別一致；
- `typed mutation variants`：以既有 operation 責任分離 set／clear，而不是用 nullable 猜測 omission；目前 `oneOf` 版本不採用，若保留候選，必須改成 nested `anyOf` 後重新做 serialized-wire audit。

每個候選都必須通過：strict serialized-wire audit、create／revise／remove、preserve／set／clear round-trip、未送欄位保持、`why_it_matters` 明確清除、remove guard、repair nested semantics、Runtime-owned 欄位不外洩，以及完整 20-tool 零付費組裝。prototype 不得使用 `null = unchanged`、magic string、完整 Working State replacement、每欄一個 tool、全域關閉 strict 或第二套 Domain validator。

### 17.4 Production gate

候選 prototype 與 round-trip 證據完成前，不修改 production adapter、不更新正式 tool wire、不再送 Luna。通過後才回報候選的語意差異、模型填寫負擔、strict 相容性與最小修改範圍，另行裁決正式接線。

## 18. 2026-09-22 test-only prototype 第一輪結果

### 18.1 已驗證

以目前正式 `WorkingStateUpdateInput` 作為 Domain authority，研究暫存 prototype 沒有替換 production tool schema、parser 或 Runtime：

- `explicit changes[]` 通過 strict object audit：所有 object properties 都列入 `required`，`additionalProperties=false`，沒有依賴 `oneOf`；
- `set` 變更可精確轉為既有 `revise` patch，Domain parser 的 `model_fields_set` 只包含實際修改欄位；
- `clear why_it_matters` 可明確轉為既有允許的 `why_it_matters=null`，且 `why_it_matters` 出現在 `model_fields_set`；
- preserve 不是某個 nullable sentinel；它表示該欄位沒有 mutation entry，同一次 partial patch 仍可對其他欄位 set／clear，未列出的欄位保持不變；
- 全程零 provider request、零正式資料、零 production 變更。

### 18.2 候選比較

| 候選 | 第一輪結果 | 目前判定 |
|---|---|---|
| `explicit changes[]` | strict shape 通過；set／clear round-trip 通過 | 暫列首選，但仍需補齊 create／remove／lifecycle／repair 與完整工具組裝 |
| `field-mask＋values` | strict shape 通過；尚未完成語意 adapter | 保留比較，不先採用；需確認欄位 mask、clear 與 nullable value 不會混淆 |
| `typed mutation variants` | 語意清楚，但目前候選使用 `oneOf`；本案不採用 | 若仍需比較，先改成 nested `anyOf` 再做 serialized-wire audit |

### 18.3 下一個 test-only gate

先沿 `explicit changes[]` 補測：

1. create 的必要核心欄位與選填內容；
2. revise 多欄 set、未提欄位 preserve、明確 clear；
3. park／reopen／mark-captured／remove／set-focus 的責任分離與 guard；
4. 先逐欄確認 `repair_memory.understanding_updates` 是完整 replacement 還是 partial update；只有具備 preserve 語意的欄位才套 mutation adapter，其餘完整值欄位直接做 strict required；
5. 完整 20-tool strict serialization 與工具名稱／Runtime-owned 欄位檢查；
6. 非法組合：同一欄位重複 mutation、同批 `set + clear`、不可清除欄位執行 clear、錯型別／不允許的 null、未知欄位，以及空 `changes[]` 的明確政策；
7. adapter 輸出重新交既有 Domain parser，確認 fail closed 且不引入第二套語意驗證。

通過前仍不修改 production、不改既有 Domain tool input、不關閉全域 strict、不送 Luna。通過後才提出正式 adapter 的最小差異與是否採用。

### 18.4 過度設計停止線與測試分層

本階段固定以下停止線：

1. `explicit changes[]` 只解決 `revise` 的 partial-update；create、park、reopen、mark-captured、remove、set-focus 保留各自最小且自然的 semantic input，不強迫全部操作使用同一種 changes 語言。
2. `explicit changes[]` 完整 gate 通過後，停止把 `field-mask＋values` 或 typed variants 做成完整 production 候選；只有出現具體反例，才重開相應候選。`oneOf` 不採用；若確有必要研究 typed variant，先改成 nested `anyOf` 再做新的 serialized-wire audit。
3. adapter 只翻譯 model-facing wire 與既有 Domain input，不建立 generic patch framework、provider schema compiler、跨 provider semantic translator、generic field-mask engine 或第二套 business validator。
4. 目前 20 個工具可以維持，不因此拆 Agent；OpenAI 的「少於 20 個起始工具」是 soft suggestion，不是本案硬上限。未來要增加常駐工具時，先檢查選擇歧義、context 成本及是否應延後載入，不能自然增長。
5. 測試分層：wire/schema 測試驗格式約束，adapter 測試驗 `representation → Domain semantic`，既有 Domain 測試驗業務規則，跨接點測試只驗責任交界；不在每一層重複測同一條規則。

這些停止線是本輪的工程範圍，不改變既有 Working State、Memory、JD、Prompt、B1／B2 或 production provider 決策。

## 19. 2026-09-22 strict wire test-only gate 2 結果

### 19.1 通過的 operation-level 證據

隔離腳本 `.research-tmp/working_state_gate.py` 只使用現有 production Domain parser，不被 production import：

- `revise` 的 `explicit changes[]` strict shape 通過；單欄 set、多欄 set＋clear、未列欄位 preserve 均能回到既有 `revise` patch，`model_fields_set` 保留實際修改範圍。
- duplicate field、同欄 set＋clear、不可清除欄位、缺少 set 值、未知欄位、錯型別與空 changes 都 fail closed；remove 三種 reason 的 guard 衝突也由既有 Domain parser 拒絕。
- create、park、reopen、mark-captured、remove、set-focus 均以各自自然的 strict shape 通過 wire audit，並交既有 `WorkingStateUpdateInput` round-trip；沒有把 `explicit changes[]` 擴成全操作通用語言。
- `repair_memory` 的 test-only strict candidate root／nested shape 通過；既有 parser 對 `revise` 與 `revalidate` 均能接受，`revalidate` 帶 diff 的反例被拒絕。這是完整值／動作語意的 adapter 對齊，不是新增 Working State patch。
- 顧問工具清單為 20 個且名稱唯一；此項只確認 inventory，不宣稱完整 20-tool strict wire 已通過。

### 19.2 尚未通過或尚未宣稱的部分

現有 production `LayeredRepairInput` schema 的 root 與 `LayeredUnderstandingRepairInput` 仍各有 required 集合不一致；本輪只建立 strict candidate，沒有修改正式 schema。先前正式 20-tool capture 的 Working State variant 與 nested repair 缺口仍然存在，零參數 consolidation 的空 `required` 仍是 normalization／completeness finding，不能用本輪 operation-level 通過結果掩蓋。

因此本輪結論是：**operation-level test-only gate 通過；production gate 與完整 20-tool model-facing assembly 仍 OPEN。**下一步只做一次完整 candidate assembly：沿 `revise` 的 `explicit changes[]`、各 lifecycle natural shape 及 repair natural shape 組裝 model-facing tool projection，重新做 20 個工具的 strict serialized-wire audit；仍不改 production、不改 Domain parser、不送 Luna。

### 19.3 完整 candidate assembly 結果

第二階段隔離投影已完成：

- 20 個工具全部保留，名稱唯一；只有 `update_interview_working_state` 與 `repair_memory` 使用本輪 candidate projection。
- Working State 的 root 仍是 object；create、revise、lifecycle、remove、focus 各自保留自然 shape，operation union 只位於 `operations.items` 的 nested `anyOf`，沒有 root-level union。
- `repair_memory` 使用所有 declared properties required 的 strict candidate；既有 `LayeredRepairInput` parser 仍負責 revise／revalidate 及其他業務語意。
- `request_memory_consolidation` 只補空 object 的 `required=[]` normalization，不把它升格成新的業務設計。
- 完整 candidate projection 的 strict audit：20 個工具、root object、所有 object `required` 對齊、`additionalProperties=false`，**0 issues**。

這仍是隔離投影，不是正式接線；沒有 provider request、正式資料寫入、Domain／Runtime 修改或 Luna 呼叫。下一個工作單位是 production adapter design review：只提出把這個已驗證 projection 接到現有工具邊界的最小差異，確認 Runtime-owned 欄位與既有 parser 不變，再另行決定是否施工。

## 20. 2026-09-22 production adapter 最小修改設計審查（只定義、不施工）

### 20.1 審查結論與責任邊界

本節把 §19.3 已通過的隔離 projection 收斂成 production adapter 的最小設計；本節不是 production 切換授權，也不改寫既有 Working State、Memory、B1／B2、C、JD、Prompt、Skills 或 compaction 決策。

正式責任固定為：

```text
模型：表達本次想做的語意操作
model-facing strict contract：表達可被 strict wire 接受的參數形狀
thin adapter：把 wire intent 翻成既有 Domain input
Runtime：擁有 ID、scope、版本、引用、digest、offset、receipt、transition、權限與 persistence
Domain parser／validator：維持業務語意 authority
既有工具／session／publication：維持現有執行與發布流程
```

這個分層直接對應目前已存在的 owner，不建立跨工具的通用轉換引擎。OpenAI 官方 strict function-calling 文件要求每個 object 使用 `additionalProperties:false`，並將所有 declared properties 列入 `required`；這是 model-facing wire 的格式契約，不是把 Domain 的 partial-update 語意改成「每欄必須真的修改」。可為 wire-required 欄位使用 nullable value 表示值本身允許為空，但不能把 `null` 全域定義成 no-op。[OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)

### 20.2 Working State 的正式接點

第一版不新增共用 contracts module。model-facing strict schema 與 translator 由既有 `working_state.py` 的工具 owner 管理，緊鄰 `build_working_state_tools()`；這避免把 Working State 的 wire 形狀散落到 generated JD contract 或新 generic component。

工具名稱與 description 責任不變：仍只有一個 `update_interview_working_state`。正式 `args_schema` 改為已在 §19.3 通過的 model-facing projection：

- root 是 object，`operations` 是非空批次；union 只在 `operations.items` 使用 nested `anyOf`，不使用 root-level union；
- `create`、`park`、`reopen`、`mark_captured`、`remove`、`set_focus` 保留各自自然 shape；
- 只有 `revise` 使用 `changes[]`，每筆 mutation 明確表示要 `set` 或允許的 `clear`；
- Runtime-owned 的正式 ID、scope、版本、source reference、digest、offset、receipt、時間與權限欄位不進 model schema。

工具執行順序固定為：

```text
model-facing arguments
    ↓ strict wire shape／adapter fail closed
既有 WorkingStateUpdateInput
    ↓ strict Domain validation／model_fields_set
既有 _apply_update
    ↓
既有 checkpoint、private receipt、digest 與 closure
```

translator 只處理 representation，不重做業務規則：

- `changes[]` 沒有某欄 mutation entry → 該 Domain 欄位不進 `model_fields_set`，保持 preserve；
- `set` → 欄位和值進既有 patch；
- `clear` → 只允許既有 Domain 明確允許清除的欄位與值；目前不能清除的欄位由 adapter／既有 parser fail closed；
- 同欄重複、同批 `set + clear`、缺值、錯型別、未知欄位、空 `changes[]` 均拒絕；不在 adapter 另造第二套 Working State validator。

### 20.3 `repair_memory` 的正式接點

`repair_memory` 的 model-facing strict schema 由既有 `memory_repair_session.py` 的 `build_repair_tool()` owner 管理；低層 `memory_repair_records.py` 的 `LayeredRepairInput`、`LayeredUnderstandingRepairInput` 與 `parse_layered_repair_input` 維持 Domain／repair authority，不改成 provider schema。

正式工具執行順序固定為：

```text
model-facing strict repair arguments
    ↓ 薄 projection／不暴露 Runtime-owned 欄位
既有 parse_layered_repair_input
    ↓
既有 repair_session.prepare／handoff
    ↓
既有版本條件、引用讀取證明、C repair／revalidate、原子發布
```

此處不假定 `understanding_updates` 是 Working State 同型的 partial patch。它目前保留既有 `revise`／`revalidate` 完整動作語意；只把 wire required／nullable 表達調整到 strict 可承接的形狀。既有 parser 繼續判斷：`revise` 是否有合法 diff、`revalidate` 是否禁止 diff／route note、supporting cases 是否有效、大小／重複／scope 是否合規。不可因 provider strict 而新增第二套 repair validator，也不自動把舊 diff 換版本號或跳過既有 publication 檢查。

### 20.4 不改動的正式物件

本次 production adapter 施工不得修改：

- `WorkingStateUpdateInput`、各 Domain operation、`model_fields_set`、`_apply_update`；
- `LayeredRepairInput`、`LayeredUnderstandingRepairInput` 的業務規則與 `parse_layered_repair_input`；
- Runtime 發出的 evidence key、canonical source ref、Memory revision／version、JD basis、receipt、digest、scope 與 persistence；
- `repair_session` 的版本條件保存、C 修補／revalidate 與 stale handling；
- A／B1／B2／C 的 agent 分工、既有 Prompt／Skills、JD 業務邏輯、DB schema、Saver／Store；
- 工具名稱、工具數量與目前的 `request_memory_consolidation` 行為。

`request_memory_consolidation` 若在正式 serialized audit 中仍需要明確空 object 的 `required=[]`，只做工具 schema normalization；它仍只是收到背景整理請求，不在模型回合執行背景整理，也不新增 dispatcher／queue／watermark。

### 20.5 生產施工前的必要 gate

正式接線前，必須在不送 provider 的情況下完成：

1. 從正式 `build_consultant_tools()` 產生 20-tool wire，確認名稱唯一、每個 root parameters 是 object、nested objects 的 `required`／`additionalProperties` 合規，並保存 serialized audit 結果；
2. `update_interview_working_state` 的 adapter round-trip：create、revise 多欄 set／preserve／clear、各 lifecycle、remove 三種 guard、set-focus 與非法組合；
3. `repair_memory` 的 revise／revalidate、nested updates、未知／缺失／不相容欄位 fail closed，且所有成功輸入仍交既有 parser；
4. 受影響的 Working State、repair session、consultant tool／wire、JD／Memory evidence 與 checkpoint／receipt regression；
5. full relevant offline suite 與 `git diff --check`。已通過且未受影響的證據直接沿用，不重新設計或重跑整批 Memory／B1／B2／compaction 研究。

以上 gate 通過後，才另行決定是否做一次受控 Luna／OpenRouter smoke；那次只驗證正式 wire 與實際 provider tool path，不再用付費呼叫猜 schema。若 gate 失敗，保留具體 wire／adapter／Domain 邊界證據，不關閉 strict、不改成全歷史重送、不切換 credential 或 provider。

### 20.6 回滾與非目標

若正式接線出現回歸，回滾單位限於兩個工具的 `args_schema` projection 與 translator wiring；既有 Domain、Runtime、Memory publication、JD persistence 與 receipt 不回滾、不清資料、不重做已成功操作。這不是新增一個平行 production path，而是同一工具在 model-facing wire 與既有 Domain 之間的薄邊界。

本節明確不做：field-mask／typed variants 的新 production 方案、generic patch engine、provider schema compiler、跨 provider translator、第二套 Domain／Memory validator、新 Agent／資料表／queue／watermark、Prompt 重寫、B1／B2 重做、OpenRouter native compaction 切換。

## 21. 2026-09-22 production adapter 施工與離線 gate 結果

### 21.1 實際施工

本節承接 §20 的最小修改設計，記錄已完成的 production adapter 接線；不改寫 §20 當時「只定義、不施工」的歷史狀態。

實際修改只停在既有工具 owner 與測試邊界：

- `working_state.py` 新增 model-facing strict schema 與一個局部 translator。只有 `revise` 將 `changes[]` 翻成既有 partial patch；未列出的欄位保持 preserve，明確 `set`／允許的 `clear` 才進既有 `model_fields_set`。create、lifecycle、remove、focus 不被改成通用 mutation DSL。
- `memory_repair_session.py` 新增 model-facing strict repair schema；成功輸入仍交既有 `parse_layered_repair_input`、repair session、版本條件、引用／read proof、C repair／revalidate 與 publication 流程。
- `memory_context.py` 僅將既有 `request_memory_consolidation` 投影為 strict empty object（`required=[]`），並把既有 Working State tools 納入正式顧問工具組裝；沒有新增背景 Agent、dispatcher、queue 或 Memory owner。
- 受影響測試只驗 wire schema、adapter 語意 round-trip、既有 parser 邊界與完整顧問工具 inventory；沒有把 Runtime-owned ID、scope、版本、引用、digest、offset、receipt 或 persistence 交給模型生成。

沒有修改：Working State／Memory 的 Domain authority、JD domain／DB、A／B1／B2／C 分工、Prompt／Skills、compaction、Saver／Store、provider routing、credential 或正式資料。沒有新增 generic patch engine、schema compiler、跨 provider translator、第二套 validator、Agent、資料表、queue、watermark 或平行 production path。

### 21.2 驗證結果

- 受影響窄回歸：**152 passed／0 failed**。
- Python `compileall`：通過。
- `git diff --check`：通過；工作區既有 CRLF／未提交變更均保留。
- 新 JD App 完整離線集合：排除兩個已知 Windows pytest 暫存目錄 ACL 阻塞檔 `tests/test_config_file.py` 與 `tests/test_operator_entry.py` 後，**3,048 passed／322 skipped／0 failed**。
- 未排除的完整執行仍出現 **37 個 `WinError 5`**，集中於上述兩檔建立／清理 pytest 暫存目錄；這是本機測試環境權限問題，不能標成產品通過，也不能把兩檔標成已驗收。

這組證據證明正式工具 wire 已能經 strict projection、薄 translator 與既有 Domain／repair authority 往返；不證明 OpenRouter／Luna 服務端 tool path、原生 compaction 或完整真人 App 旅程已通過。全程零 provider request、零正式資料、零付費。

### 21.3 下一個 gate 與停止線

目前離線施工單位可結束。若要繼續使用真實模型，下一步是另行核准的一次受控 Luna／OpenRouter tool-path smoke，目的改為驗證已通過離線 audit 的正式 wire 能否被實際 provider 接受；不再用付費呼叫猜 schema，也不自動切換 provider／credential。若尚未取得費用授權，維持目前接線與 evidence，先不送出請求。

本節不重新開啟 Memory、B1／B2、C、JD、Prompt、compaction、field-mask／typed variants 或通用 patch framework 設計；如真實 smoke 出現錯誤，只在取得具體 wire／provider／runtime 證據後，回到對應工具邊界處理。

## 22. 2026-09-22 model-facing description／OpenAI base subset gate

### 22.1 小範圍補強

承接 §21 的 production adapter，這一單位只處理兩個已確認的 smoke 前缺口：

1. 在 `working_state.py` 的 model-facing `revise.changes[]` 補充 `field`、`action`、`text`、`priority`、`evidence_keys`、`related_handles` 的精確使用說明，明確指出哪個 field 使用哪個 value slot，以及未使用 slot 必須填 `null`。
2. 在 `memory_repair_session.py` 的 model-facing repair schema 補充案例欄位、`action`、V4A `diff`、supporting case IDs、route note 的責任與限制。這些是 wire description，不是第二套 Domain validator，也不是 Prompt 重寫。

沒有修改既有 parser、Runtime-owned identity、引用／read proof、版本條件、publication、JD、Memory 或 Agent 分工。

### 22.2 OpenAI base-model subset audit

既有 `test_consultant_runtime.py` 的 recursive audit 維持原本三類檢查：

- root parameters 必須是 object，不能是 root-level `anyOf`；
- 每個 object 必須 `additionalProperties=false`，且 `required` 與 properties 完整對齊；
- nested union 仍可使用 `anyOf`。

本輪再加入目前 OpenAI Structured Outputs base-model subset 明確不支援的 composition keyword：`allOf`、`not`、`dependentRequired`、`dependentSchemas`、`if`、`then`、`else` 與 `oneOf`。沒有把一般模型支援的 `minItems`／`maxItems` 列為禁用；fine-tuned model 的額外 keyword 限制另屬不同 profile，不混入目前 Luna route 的 gate。audit 保持為本地窄檢查，不建立完整 JSON Schema engine。

### 22.3 驗證結果與停止線

- Working State、repair schema description regression 與 20-tool audit：**46 passed／0 failed**。
- warnings 仍為既有 Pydantic serializer 及 pytest cache ACL 警告，未形成測試失敗。
- 全程零 provider request、零正式資料、零付費。

因此這個零付費 gate 結束。下一步是另行受控的 Luna／OpenRouter tool-path smoke，固定分成：

```text
A Provider/Wire acceptance
B Model tool generation
C Application semantic execution
```

未經新的費用／真模型執行確認，不自動發送 provider request；也不因本 gate 重新設計 nullable placeholder、create defaults、20 tools、Memory、B1／B2／C 或 compaction。

## 23. 2026-09-22 真實 Luna／OpenRouter tool-path 重測結果

### 23.1 A／B／C 分層結果

在同一隔離 PostgreSQL fixture、新 JD App 正式 runtime、Windows Credential Manager 的既有 OpenRouter credential 與 OpenAI-only `openai/gpt-5.6-luna` 路徑執行受控重測。實際送出 5 次 provider request，全部 HTTP `200`；provider metadata 為 `OpenAI`，觀察到的 usage cost 合計 **US$0.01429579**，hidden retry 維持 0、沒有 fallback。

自然模型實際走過：

```text
jd_read
→ read_evidence
→ jd_insert_item（confirmed／committed）
→ request_memory_consolidation（只收到通知，不代表背景完成）
```

因此：

- A Provider／Wire：**PASS**。
- B Model tool generation：**PASS**，已觀察到真實工具選擇與回傳往返。
- C JD persistence／receipt：**PASS**，JD revision 與 committed receipt 已查回。
- C natural final response：**OPEN**；同一回合沒有保存 assistant final message。

### 23.2 已發現的收尾邊界

第二個自然回合查回為 `run_status=failed`、`input_state=saved`、`jd_effects.state=settled`、`response_message_id=null`；已保存 JD 修改的 receipt 為 confirmed，沒有重送或重做操作。這證明目前「副作用先以 receipt 保存，最後回答失敗不回滾／不偽造 assistant 歷史」的安全邊界在真實模型下確實被觸發。

新 Web 已有固定狀態文字「原話已保存，回覆未完成」，並列出已保存改動及其查看入口；但本次尚未以瀏覽器完成來源查看與撤回，也尚未證明模型為何在工具路徑後沒有產生可保存的收尾回答。非敏感 provider metadata 不足以把原因猜成 schema、Prompt、Memory 或 OpenRouter 服務端錯誤。

### 23.3 下一步與停止線

本次結果不授權新增 fallback assistant artifact、第二套 receipt／conversation、重送同一回合或改寫既有 failed-final 語意。若要提升使用者看到的收尾，先由產品決定是否接受現有固定 App 狀態與改動入口，或要另行裁決「failed-but-committed 是否需要 UI-only 固定提示」；canonical history 仍不能偽造模型未產生的回答。

在該裁決前，不修改 Prompt、Memory、B1／B2、compaction、tool schema、provider route、JD domain 或 receipt 語意。完整 App journey 仍需另外驗收：瀏覽器顯示、來源查看、當輪 JD 撤回，以及日常聊天的自然收尾。

## 24. 2026-09-22 `request_memory_consolidation` 通知接線修復與驗證

### 24.1 先固定既有設計語意

回看 `2026-09-17-layered-memory-background-workflow-design.md`、`2026-09-17-managed-app-background-callback-design.md`、`2026-09-16-layered-case-and-work-understanding-memory-alignment.md` 與 `caliburn_memory.requests` 後，確認 `request_memory_consolidation` 是純通知工具：

- 只產生 `memory_consolidation_requested` receipt；
- 不執行 B1／B2、不寫入 Memory、不回報背景已完成；
- 主顧問收到通知結果後仍須完成本輪回答；
- 前景安全結束後，既有 Runtime `_wake_background()` 才交 dispatcher 依 durable admission／checkpoint／publication 狀態評估是否啟動或恢復背景工作。

本次修正沒有改變以上責任，也沒有新增 Agent、queue、watermark、同步等待或另一套通知機制。

### 24.2 根因與最小修正

2026-09-22 真實 Luna 首次 JD tool-path 出現「JD 已保存但 assistant final 缺失」。沿實際程式與 checkpoint 對照後，根因是新 JD App 的 `AiToolMiddleware._call_identity()` 與 `AiToolSession.prepare()` 沒有把已註冊的 `request_memory_consolidation` 列入可執行工具。模型的通知 call 因而沒有產生成功 ToolMessage；settle／recovery 只能補上 `memory_consolidation_not_requested` 並停止，模型沒有機會收到通知 receipt 後再收尾。

最小修改只把既有 `REQUEST_TOOL_NAME` 加入 middleware identity／prepare allowlist。通知仍由原生 ToolNode 立即呼叫純 receipt function；此「立即」只代表產生通知結果，不代表等待背景整理。

### 24.3 驗證結果

- 新增 framework-native loop regression：`Human → AI request_memory_consolidation → success ToolMessage(artifact=memory_consolidation_requested) → AI final`；通過。
- 受影響相關離線集合：**157 passed／18 skipped／0 failed**；既有 Pydantic／pytest cache warnings 不構成失敗。
- Python compileall 與 `git diff --check` 通過。
- 修正後一次真實 Luna follow-up：4 次 provider request、全部 HTTP 200、保存 assistant final；但自然模型本輪未選 `request_memory_consolidation`，且沒有 JD mutation，因此這次只證明一般 tool／read 路徑能正常收尾，不能冒稱真實 notification→final 路徑已重跑。
- 隨後以同一隔離 App／PostgreSQL 與 OpenAI-only Luna 做受控通知驗收：6 次 provider request 全部 HTTP 200，實際模型為 `openai/gpt-5.6-luna`、provider 為 `OpenAI`，觀察費用 **US$0.00573776**。durable checkpoint 確認完整鏈為 `Human → AI(request_memory_consolidation) → success ToolMessage(artifact=memory_consolidation_requested) → AI final`；run 為 `completed`、`closed=true`，最後回答已保存，且通知結果明確表示背景尚未執行／Memory 尚未更新。查回同一隔離資料庫的 `jd_memory_admission` 仍為 `idle`、target/source 為空、`recovery_count=0`，沒有啟動 B1／B2。這次證明修正後的真實 notification→final 路徑通過，前景沒有等待或執行 B1／B2。
- 同一測試第一次立即查詢 active run 時曾收到一次 `503 service_unavailable`，之後以同一 run 查回 durable `completed`；這是狀態觀察時序證據，不是 provider／ToolMessage／final 失敗。由於目前只有一次、且沒有造成資料或回合遺失，先記錄為獨立的 status-observation finding，不在本切片猜測或修改 API。

### 24.4 當前 gate

```text
通知工具語意與背景責任        PASS（文件／程式對齊）
通知工具 framework loop        PASS（離線真實 graph loop）
修正後一般 Luna final          PASS（4 次 HTTP 200，assistant final 已保存）
修正後 Luna notification path  PASS（6 次 HTTP 200；durable ToolMessage／receipt／final 已確認）
JD mutation＋自然 final         PASS（8 次 HTTP 200；confirmed／committed JD receipt 與 assistant final 已查回）
本輪 JD 撤回（HTTP／DB）         PASS（manual undo receipt committed；對話保留）
同輪 notification receipt        沿用獨立 notification PASS；本次 journey 的 probe 未另存 checkpoint receipt 證據
來源查看／完整 UI                OPEN（本次新增 task 沒有 basis_refs，未產生 source ref）
```

下一步不再修改通知語意、不新增同步背景執行、不偽造 assistant 歷史，也不重做 Memory／B1／B2 設計；只剩來源 ref 實際旅程與瀏覽器畫面驗收。active run 的一次性 `503 service_unavailable` 另列 status-observation finding，若後續在正常產品旅程可重現，再單獨提出最小 status API 修正方案。

### 24.5 真實 JD mutation／undo journey

同一隔離 fixture 再做一次有界自然 Luna 旅程，明確要求模型先讀取 JD、建立一項最小工作責任、通知背景整理，再以繁中完成收尾。實際結果為：

```text
JD read
  → JD task create：confirmed／committed
  → assistant final：已說明 JD 修改與背景通知尚未完成
  → manual undo_ai_turn：committed
  → JD 回到本輪前內容；conversation 仍保留
```

8 次 provider request 全部 HTTP `200`，實際模型為 `openai/gpt-5.6-luna`、provider 為 `OpenAI`，usage cost 合計 **US$0.01797905**，無 hidden retry／fallback。Run 查回 `completed`、`input_state=saved`、`response_message_id` 非空；JD run change 有 1 個 captured operation，操作 receipt 為 confirmed／committed。撤回使用 App 既有的 employee-only `undo_ai_turn`，以當回合 `result_revision_ref` 作條件，回應 `committed`；撤回後 public conversation 仍為原本 2 則訊息，沒有刪除原話或偽造 assistant 歷史。

這次模型建立的是沒有 `basis_refs` 的新 task，因此 run change 沒有 source ref；這是**測試資料未覆蓋來源旅程**，不是來源 API 的失敗證據。來源功能的既有離線／HTTP 回歸沿用，下一個真實來源 gate 必須先有一個由 Runtime 驗證、附著到 JD 變更的 source ref，才驗收「改動 → 來源」畫面；不為此新增第二套引用或手動偽造 source。

本次隔離服務已正常關閉，沒有正式文件、Memory 或對話資料進入測試；已觀察的 provider metadata 與結果摘要留在本機 `.research-tmp`，不進產品或正式資料。原始 provider ledger 後來因同一 fixture 的零請求瀏覽器殼層重啟而被覆蓋，故不把它宣稱為仍存在的 raw capture。

### 24.6 新架構瀏覽器殼層續驗

以同一個新 `experiments/jd-relational-app` Web（`127.0.0.1:3002`）連回隔離 API，瀏覽器先觀察到既有暫存建立操作的「尚待確認」狀態；按既有「查回並繼續原建立」後，成功進入文件頁。畫面可見聊天顧問、可輸入的訪談欄位、六個 JD 章節導覽，以及六章的編輯區：基本資料、職務目的、職責與任務、所需知識、所需技能、適用條件與責任邊界。這確認目前頁面是新 JD App，且未知建立結果的查回狀態能被 UI 呈現與恢復。

本次沒有在瀏覽器再送第二次真實模型請求，也沒有把舊的暫存建立操作當成新 mutation／source／undo 證據；因此「瀏覽器內送出訪談 → 顯示模型回答 → 顯示本輪改動 → 來源查看 → 撤回」仍是 OPEN。隔離 API 服務已正常停止，沒有留下持續執行的驗收程序。

## 25. 2026-09-22 首輪原話讀取接線回歸與 JD 來源驗收範圍

隔離真實 Luna 的單輪來源測試保存了員工輸入，但 run 為 `failed`，沒有 JD effect、assistant final 或 JD source link。此結果本身不足以判定 provider 失敗原因。定向離線反例使用正式 source owner、`ToolNode` 與同一 run 的 `current_turn` key，重現「尚無 `interview_working_state` 時，`read_evidence` 回 `unknown_evidence_key`」；這與 §5.3 的 current-turn 來源可用、§7.2 的可作 JD basis 契約不符。

最小修正只讓 `read_evidence` 在有 `source_notice` 時取得本回合已保存來源，不再以 Working State 是否存在作為前提；模型可見的工具描述同步列明來源通知 key。來源 owner、key scope、canonical ref、分頁、read proof、JD domain 與 Memory 分層均未改。新增首輪無 Working State 的真實 `ToolNode` 回歸：修正前精確得到 `unknown_evidence_key`，修正後返回原始問答，正式 ref 只在 private artifact。受影響測試 **113 passed／0 failed**；未重送付費模型請求。

這個測試只證明本輪原話引用接線。JD 寫作的產品基礎仍是跨案例的穩定工作理解、相關案例與必要原話；不能把單一合成回合產生的 JD 當作完整職務分析品質驗收。現行 JD `jd_source_link` 指向 canonical 原始訪談，B2 工作理解及案例供顧問分析與逐層回查。Owner 提出可考慮直接引用工作理解；此事會改變可見來源語意，尚未裁決，不在本接線修正中暗改。下一個真實模型品質情境應先有多輪訪談及相關 B1／B2 內容，再觀察 A 如何使用它們寫 JD；來源顯示範圍另行對齊。完整瀏覽器旅程仍 OPEN。
