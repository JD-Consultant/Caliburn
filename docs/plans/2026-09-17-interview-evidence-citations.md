# B1／B2 訪談證據引用與 Runtime 權責施工計畫

- 日期：2026-09-17
- Topic：`JD-R002 / MEM-L001`
- Stage：G7 前置正確性切片
- 依據：[MEM-L001](../specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md)、[背景 Workflow 設計](../specs/2026-09-17-layered-memory-background-workflow-design.md)、[模型／Runtime 參數權責審核](../specs/2026-09-17-model-runtime-parameter-ownership-review.md)

## 1. 目標

修正目前 B1 將整批 `window` 自動附到每個改動案例的過粗行為，讓 B1 能從已實際閱讀的完整訪談交換中選擇證據，並由 Runtime 保存為 canonical 順序的既有 `purpose="source"` references。B2 沿案例引用按需回查時，看到相同的前後關係、role 與原文。

本片完成後只證明引用與讀取接點正確；B1／B2 結果仍是 staged，不接共同 publication、dispatcher、C、compaction、provider 或正式 App authority。

## 2. 已確認契約

- `window`：本次背景工作範圍及 `processed_source` 游標，不是案例證據。
- `source`：現有已簽名、固定 checkpoint 的完整訪談交換；包含該輪使用者回答與其前一則公開顧問問題／上下文。
- `context`：window 閱讀時的暫時消歧資料，不是案例證據。
- 同一 `source` 可支持多個案例；同一案例可保存多個 `source`。
- 多筆來源必須按 source owner 對 canonical conversation 證明的 message order 保存及展示；settled failed／cancelled 的員工原話仍可成為來源，第一個 unsettled gap 後不列出。不得依 reference、UUID、字典序或時間戳排序，也不把全域輪次欄位當成必要產品契約。
- Runtime 將當次已提供／已讀來源放入明示 `oldest_to_newest` 的 ordered blocks，配置 checkpoint-stable、attempt-scoped `evidence_key`。模型只選既有 key；Runtime 解析、驗證並 canonicalize 真正 reference。key 不是輪次、時間或持久 citation。
- 模型不產生 reference、offset、cursor、sequence、document、版本或完成 outcome；這些由 Runtime／source owner 決定。
- 一筆交換不足以說明案例時，B1 選入較早的相關問答、補充及更正。效果要求是只看引用也能理解案例，不能只通過結構驗證就宣稱語意充分。

## 3. 範圍與步驟

### Task 1：來源 owner 提供歷史安全交換與 canonical order proof（已完成）

修改：

- `experiments/jd-relational-app/src/jd_relational/conversation_sources.py`
- `experiments/jd-relational-app/tests/test_conversation_sources.py`
- 視既有測試責任補 `test_interview_window_source.py`

先寫反例，再新增最小 owner API：

1. 沿用 `AiRunHistory.find()` 與每輪自己的 terminal observation，為已安全完成的歷史使用者輪次簽發既有 `_SourcePosition`；不建立新 token purpose、第二份對話或文字 offset。
2. 對同一 fixed／canonical lineage 回傳 ordered source records：`source_reference` 及 source 中的 message metadata；順序來自真正 conversation message order。可有 owner 私有 ordinal／比較資訊，但不成為模型欄位或持久 citation。
3. 能列出某個已簽 `window` 內的 source exchanges，也能以有界分頁按需瀏覽同文件安全歷史；遇第一個 unsettled turn 停止，沿用現有 fail-closed 規則。
4. 驗證外文件、兄弟 branch、缺 checkpoint、超過 ancestry bound、倒序與範圍外 reference 明示失敗，不 fallback latest。
5. source 內容仍是「最近公開 AI 問題＋本輪 Human」，不把 tool／system／thinking／provider metadata 或時間戳投影給模型。

必要反例：反 UUID／反字典序仍按對話先後、同內容兄弟 lineage、較早歷史輪、failed／cancelled 但已安全保存的員工原話、unsettled gap、跨頁順序、單一 source 被兩個 consumer 重用。

### Task 2：package source port 與 App adapter（已完成）

修改：

- `packages/consultant-memory/src/caliburn_memory/sources.py`
- `experiments/jd-relational-app/src/jd_relational/extraction_app.py`
- 對應 package／App adapter tests

新增最小 typed／validated port，讓 package 只看見：

- 固定 window 內按順序的 evidence exchanges；
- 同文件歷史安全 exchanges 的有界按需讀取；
- exact `source` 的有界分頁讀取。

App adapter 只轉譯 source owner 的既有錯誤與資料，不自行重排、重簽或保存另一份索引。現有 window／context pair 驗證與 admission cursor 不變。

實作結果：既有 `source` 已可為安全歷史輪次重新簽發；固定 `window` 可列出 canonical 順序的逐輪 records，同一 `window` 也可作歷史分頁上界。清單只帶 signed reference 與 message ID／role，不攜帶全文、時間或 provider metadata；全文由 exact-source 3000 字元頁面讀取。package port 使用 immutable typed records，App adapter 只作資料與固定錯誤轉譯。後續 `evidence_key`、attempt cursor 與已讀集合仍屬 Task 3，沒有提前放進 source owner。

### Task 3：B1 stage 保存「已提供／已讀」證據 key，不保存原話副本（已完成）

修改：

- `packages/consultant-memory/src/caliburn_memory/case_maintenance.py`
- `packages/consultant-memory/tests/test_case_maintenance.py`
- `packages/consultant-memory/tests/test_case_maintenance_agent.py`

1. 升級 B1 checkpoint stage 格式，保存 Runtime 已交付／已讀的 `evidence_key → source_reference` 對照、canonical order proof 與必要 read evidence；不複製原始訪談文字。
2. `_load_window` 在提供 `NEW_SOURCE` 時一併提供 owner 已排序的 evidence blocks，並把 keys 登記為模型可選證據；容器明示 `order="oldest_to_newest"`。
3. 新增 B1 受控讀取動作，讓模型按需讀既有案例引用及有界歷史交換；Runtime 保存 paging cursor，模型不填 offset。工具回傳 key、role、全文與是否尚有下一頁，不能把 window／context 當 evidence。
4. `read_case` 回傳每筆既有 source 對應的 ordered evidence block；如果 owner 無法證明 canonical order，明示失敗，不照 tuple／字串原順序猜測。
5. stage serialize／resume 後保留同一映射；同 attempt 不因 latest conversation 前進而偷偷改序或擴大已提供集合。

實作結果：`CaseMaintenanceStage` 已升為 v2，在原 stage 內保存短 key、signed source、message ID／role、Runtime-private order proof、歷史下一頁與每筆 exact-source 下一頁；原話不進 stage。窗口載入同時登記 owner-ordered blocks；新增的 `browse_interview_history()` 沒有模型參數，`read_more_evidence(evidence_key)` 只收已展示 key。`read_case` 從 attempt 固定的 window 上界分頁掃描 owner metadata，全部引用都定位後才回正文與 ordered evidence；缺漏、重複、順序漂移或 paging 不前進皆拒絕，失敗不留下 read evidence。transport resume、反 artifact tuple 順序、Runtime-only cursor、無 raw-text checkpoint 及 fail-closed 反例已納入 package 回歸。Task 4 已在下一節接續完成。

### Task 4：B1 語意工具改為選擇證據（已完成）

工具只接受 Runtime 已提供的 `evidence_key`，由 Runtime 解析成 references：

- `create_case`：必填完整的 `evidence_keys`。
- `revise_case`：使用 `add_evidence_keys`／`remove_evidence_keys` 做增量調整；未列出的既有證據保留，避免每次重填整組。
- `split_case`：每個 replacement 各自提供完整 `evidence_keys`，不能把舊案例的全部來源複製給每個新案例。舊來源若不再支持任何 replacement，必須明示捨棄及原因，不能因漏填靜默遺失。
- `merge_cases`：Runtime 先建立已讀 cases 的來源聯集；模型只提供 add/remove 語意差異，避免重抄整組時漏掉來源；套用後仍驗證至少一筆及 canonical order。
- `retire_case`／`set_case_route`：不新增來源選擇。
- `finish_case_maintenance`：改為零參數完成動作，`changed/no_op` 由 Runtime 依 stage 計算。

Runtime 拒絕未知／重複 key、同時新增及移除同一 key、空證據、跨文件、非 `source` purpose、模型直接提交 token，以及新增／移除後無法支持資料結構的請求。工具回應回傳實際接受的 ordered evidence keys，讓模型可修正錯誤；失敗不得部分修改 stage。

Prompt 只補來源選擇與分配規則，不重寫案例分析方法、B1/B2 分層或主顧問 Prompt。

實作結果：B1 create／revise／split／merge 現只接受 attempt 內已展示的 `evidence_key`，Runtime 解析正式 signed references、依 source owner 順序 canonicalize，並拒絕未知、重複、add/remove 衝突及空證據。revise 保留未提及引用，且允許 `diff=null` 完成純引用修補；split 對每個 replacement 要求完整 keys，未分配的舊引用須帶一行理由明示捨棄；merge 從已讀案例引用聯集套用 delta。工具成功結果回傳實際接受的 ordered keys，模型不能提交 reference、offset 或 outcome；`finish_case_maintenance()` 已為零參數並由 Runtime 計算 `changed/no_op`。所有輸入先驗證再配置新案例 ID，失敗不修改 stage 或消耗 identity。Prompt 只加入上述選擇規則；案例分析方法、B1／B2 邊界及主顧問 Prompt 未改。完整 package 回歸已涵蓋精確 window 引用、倒序輸入 canonicalize、引用-only revise、split 分配／捨棄、merge 聯集 delta、schema 隱藏及 transport resume；Task 5 已接續完成 bundle／B2 讀取。

### Task 5：Memory bundle 與 B2 讀取保持相同順序（已完成）

修改：

- `packages/consultant-memory/src/caliburn_memory/memory.py`
- `packages/consultant-memory/src/caliburn_memory/understanding_workflow.py`
- `experiments/jd-relational-app/src/jd_relational/memory_sources.py` 或既有正確 adapter 接點
- 對應 package／App tests

1. `save_bundle()` 不再只相信 caller tuple 順序；經 source port 驗證 references 都屬同文件及同一 canonical lineage，再按 owner order proof 保存。
2. B2 `read_case` 顯示 ordered evidence blocks；exact source read 只收 `evidence_key`，key 已綁 case／reference，Runtime 從 checkpoint 取得 paging cursor，不讓模型填 `source_reference` 或 `offset`。
3. B2 的 read evidence 仍以 `(case_id, source_reference)` 隔離；排序欄位不改變授權，不能把 case A 已讀冒充 case B 已讀。
4. 工作理解只引用案例身分／精確 case digest；不把 raw source references 複製成另一套 B2 citation authority。
5. `request_case_rework` 的模型輸入只保留 `evidence_key＋reason`；Runtime 解析正式 case/source。B2 finish 同樣改為零參數並由 Runtime 計算 outcome。

實作結果：`save_bundle()` 現要求 Runtime 提供本次 B1 工作原有的固定歷史上界；它先驗證案例來源可讀，再從 source owner 的 `oldest_to_newest` 歷史一次證明同文件／同 lineage 及位置，最後依 owner order 寫入 manifest，不再相信 caller tuple、reference 或時間。這個上界只是 Runtime 驗證參數，不成為案例 evidence。B2 stage 已升為 v3；`read_case` 只回案例正文、按 owner 順序排列的案例專用 `evidence_key` 及 role metadata，不預載原話。`read_case_source(evidence_key)` 從同一 checkpoint 解析 case/source 與下一頁 cursor，回傳該頁 role／原文而不暴露 reference、message ID 或 offset；同一 source 支持兩案例時配置不同 keys，正式已讀證據仍以 `(case_id, source_reference)` 隔離。`request_case_rework` 只接受已讀 key＋reason，正式 issue 由 Runtime 解析；B2 finish 已為零參數。工作理解 artifact／binding 仍只保存 case ID＋精確 digest，沒有新增 raw-source citation authority。

### Task 6：驗證與文件收尾（已完成）

至少覆蓋：

1. 顧問完整問題＋員工簡答形成一筆 source；跨回合補充／更正形成有序多筆來源。
2. 同一 source 支持 A、B 兩案例；A／B 各自能按需回讀。
3. revise 只增加或移除真正受影響來源；未提及來源保留。
4. split 將來源分配到正確 replacement，不複製全部；merge 產生正確聯集子集。
5. 模型以倒序 keys 提交時，Runtime 仍保存 canonical 順序；未知／重複／跨文件／錯 purpose 拒絕。
6. checkpoint resume 後 key→reference 不漂移；分頁與 B2 回查不改來源順序，模型無法控制 offset。
7. 無 timestamp、offset、tool／system／thinking 進模型可見 evidence。
8. finish 不再因模型填錯 `changed/no_op` 失敗；Runtime 仍攔截未完成必讀集合或不一致 stage。
9. 現有 window admission、context pair、lineage、B1/B2 step limits 與 bundle validation 回歸保持通過。
10. 檢查 B1／B2 實際 provider request 是否真的啟用 strict schema；未證實不得只因 Pydantic schema 存在就標為 strict，Runtime 驗證在兩種情況都保留。

執行受影響 package tests、conversation/source tests、B1/B2 App adapter tests、compileall 與 `git diff --check`。不呼叫 provider、不讀正式 key、不啟動 production、不做 push。

實際結果：`consultant-memory` 全套 **247 passed**，App 的 `test_memory_sources.py`／`test_interview_window_source.py`／`test_extraction_app.py` **94 passed**；兩個範圍的 `compileall` 均通過。另以反例確認 B2 語意與 workflow 兩個工具工廠都在組裝時拒絕跨文件 source reader。鎖定版本的 provider wire tool definition 未啟用 `strict=true`，因此只記錄 Runtime Pydantic／ToolNode strict 驗證已通過，不把 schema 存在冒稱 provider strict。全程未呼叫 provider、未讀 key、未啟動 production、未 push。

## 4. 明確不做

- 不建立新的 `turn` citation token 或第二份 conversation table。
- 不把整份歷史預載給 B1／B2，不新增 embedding／RAG／向量搜尋。
- 不以時間戳、UUID、reference 字串或模型自行排序決定前後。
- 不接背景共同 publication、dispatcher、C repair、compaction、JD writer 或 UI。
- 不做 artifact GC、文件封存、歷史 UI 或舊資料 migration。

## 5. Gate

本片通過後，才回到 `BackgroundMemoryWorkflow`，串接 B1 staged → B2 staged → 最多一次 case rework → bundle → CAS publication。若實作時發現現有 source owner 無法在不改 canonical conversation authority 的前提下證明歷史 source order，停止並提出具體反例，不自行改成時間戳、模型輪次、文字 offset 或全歷史複製。
