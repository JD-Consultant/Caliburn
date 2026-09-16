# B1／B2 訪談證據引用與 canonical 順序施工計畫

- 日期：2026-09-17
- Topic：`JD-R002 / MEM-L001`
- Stage：G7 前置正確性切片
- 依據：[MEM-L001](../specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md)、[背景 Workflow 設計](../specs/2026-09-17-layered-memory-background-workflow-design.md)

## 1. 目標

修正目前 B1 將整批 `window` 自動附到每個改動案例的過粗行為，讓 B1 能從已實際閱讀的完整訪談交換中選擇證據，並由 Runtime 保存為 canonical 順序的既有 `purpose="source"` references。B2 沿案例引用按需回查時，看到相同的正式輪次、前後關係、role 與原文。

本片完成後只證明引用與讀取接點正確；B1／B2 結果仍是 staged，不接共同 publication、dispatcher、C、compaction、provider 或正式 App authority。

## 2. 已確認契約

- `window`：本次背景工作範圍及 `processed_source` 游標，不是案例證據。
- `source`：現有已簽名、固定 checkpoint 的完整訪談交換；包含該輪使用者回答與其前一則公開顧問問題／上下文。
- `context`：window 閱讀時的暫時消歧資料，不是案例證據。
- 同一 `source` 可支持多個案例；同一案例可保存多個 `source`。
- 多筆來源必須按 source owner 的一基準正整數 `turn_sequence` 保存及展示：第一個安全完成使用者輪次為 1，settled failed／cancelled 仍占序號，第一個 unsettled gap 後不列出；不得依 reference、UUID、字典序或時間戳排序。
- 模型不產生 reference、offset、sequence、document 或版本。Runtime 先提供可選的 `turn_sequence`；模型只選擇已提供／已讀序號，Runtime 解析及驗證真正 reference。
- 一筆交換不足以說明案例時，B1 選入較早的相關問答、補充及更正。效果要求是只看引用也能理解案例，不能只通過結構驗證就宣稱語意充分。

## 3. 範圍與步驟

### Task 1：來源 owner 提供歷史安全交換與 canonical 順序

修改：

- `experiments/jd-relational-app/src/jd_relational/conversation_sources.py`
- `experiments/jd-relational-app/tests/test_conversation_sources.py`
- 視既有測試責任補 `test_interview_window_source.py`

先寫反例，再新增最小 owner API：

1. 沿用 `AiRunHistory.find()` 與每輪自己的 terminal observation，為已安全完成的歷史使用者輪次簽發既有 `_SourcePosition`；不建立新 token purpose、第二份對話或文字 offset。
2. 對同一 fixed／canonical lineage 回傳一基準遞增 `turn_sequence`、`source_reference` 及 source 中的 message metadata。
3. 能列出某個已簽 `window` 內的 source exchanges，也能以有界分頁按需瀏覽同文件安全歷史；遇第一個 unsettled turn 停止，沿用現有 fail-closed 規則。
4. 驗證外文件、兄弟 branch、缺 checkpoint、超過 ancestry bound、倒序與範圍外 reference 明示失敗，不 fallback latest。
5. source 內容仍是「最近公開 AI 問題＋本輪 Human」，不把 tool／system／thinking／provider metadata 或時間戳投影給模型。

必要反例：反 UUID／反字典序仍按對話先後、同內容兄弟 lineage、較早歷史輪、failed／cancelled 但已安全保存的員工原話、unsettled gap、跨頁順序、單一 source 被兩個 consumer 重用。

### Task 2：package source port 與 App adapter

修改：

- `packages/consultant-memory/src/caliburn_memory/sources.py`
- `experiments/jd-relational-app/src/jd_relational/extraction_app.py`
- 對應 package／App adapter tests

新增最小 typed／validated port，讓 package 只看見：

- 固定 window 內按順序的 evidence exchanges；
- 同文件歷史安全 exchanges 的有界按需讀取；
- exact `source` 的有界分頁讀取。

App adapter 只轉譯 source owner 的既有錯誤與資料，不自行重排、重簽或保存另一份索引。現有 window／context pair 驗證與 admission cursor 不變。

### Task 3：B1 stage 保存「已提供／已讀」證據，不保存原話副本

修改：

- `packages/consultant-memory/src/caliburn_memory/case_maintenance.py`
- `packages/consultant-memory/tests/test_case_maintenance.py`
- `packages/consultant-memory/tests/test_case_maintenance_agent.py`

1. 升級 B1 checkpoint stage 格式，保存 Runtime 已交付／已讀的 `(turn_sequence, source_reference)` 對照與必要 read evidence；不複製原始訪談文字。
2. `_load_window` 在提供 `NEW_SOURCE` 時一併提供 owner 已驗證的 exchange sequence，並把它們登記為模型可選證據。
3. 新增 B1 受控工具，讓模型按需讀既有案例引用及有界歷史交換；工具回傳 sequence、role、全文與分頁資訊，不能把 window／context 當 evidence。
4. `read_case` 回傳每筆既有 source 對應的 canonical sequence；如果 owner 無法證明，明示失敗，不照 tuple／字串原順序猜測。
5. stage serialize／resume 後保留同一映射；同 attempt 不因 latest conversation 前進而偷偷改序或擴大已提供集合。

### Task 4：B1 語意工具改為選擇證據

工具只接受已提供的 `turn_sequence`，由 Runtime 解析成 references：

- `create_case`：必填完整的 `source_turns`。
- `revise_case`：使用 `add_source_turns`／`remove_source_turns` 做增量調整；未列出的既有證據保留，避免每次重填整組。
- `split_case`：每個 replacement 各自提供完整 `source_turns`，不能把舊案例的全部來源複製給每個新案例。
- `merge_cases`：提供合併後完整 `source_turns`；Runtime 可接受既有 cases 與本 attempt 已讀證據的聯集子集，但仍驗證至少一筆及 canonical order。
- `retire_case`／`set_case_route`：不新增來源選擇。

Runtime 拒絕未提供序號、重複序號、空證據、跨文件、非 `source` purpose、模型直接提交 token，以及新增／移除後無法支持資料結構的請求。工具回應回傳實際保存的 ordered sequences，讓模型可修正錯誤。

Prompt 只補來源選擇與分配規則，不重寫案例分析方法、B1/B2 分層或主顧問 Prompt。

### Task 5：Memory bundle 與 B2 讀取保持相同順序

修改：

- `packages/consultant-memory/src/caliburn_memory/memory.py`
- `packages/consultant-memory/src/caliburn_memory/understanding_workflow.py`
- `experiments/jd-relational-app/src/jd_relational/memory_sources.py` 或既有正確 adapter 接點
- 對應 package／App tests

1. `save_bundle()` 不再只相信 caller tuple 順序；經 source port 驗證 references 都屬同文件及 canonical sequence，再以該順序保存。
2. B2 `read_case` 顯示 ordered source sequences；`read_case_source` 沿 exact reference 分頁後仍帶相同 `turn_sequence`。
3. B2 的 read evidence 仍以 `(case_id, source_reference)` 隔離；排序欄位不改變授權，不能把 case A 已讀冒充 case B 已讀。
4. 工作理解只引用案例身分／精確 case digest；不把 raw source references 複製成另一套 B2 citation authority。

### Task 6：驗證與文件收尾

至少覆蓋：

1. 顧問完整問題＋員工簡答形成一筆 source；跨回合補充／更正形成有序多筆來源。
2. 同一 source 支持 A、B 兩案例；A／B 各自能按需回讀。
3. revise 只增加或移除真正受影響來源；未提及來源保留。
4. split 將來源分配到正確 replacement，不複製全部；merge 產生正確聯集子集。
5. 工具以倒序 sequences 提交時，Runtime 保存 canonical 順序；未知／重複／跨文件／錯 purpose 拒絕。
6. checkpoint resume、分頁與 B2 回查不改 sequence。
7. 無 timestamp、offset、tool／system／thinking 進模型可見 evidence。
8. 現有 window admission、context pair、lineage、B1/B2 step limits 與 bundle validation 回歸保持通過。

執行受影響 package tests、conversation/source tests、B1/B2 App adapter tests、compileall 與 `git diff --check`。不呼叫 provider、不讀正式 key、不啟動 production、不做 push。

## 4. 明確不做

- 不建立新的 `turn` citation token 或第二份 conversation table。
- 不把整份歷史預載給 B1／B2，不新增 embedding／RAG／向量搜尋。
- 不以時間戳、UUID、reference 字串或模型自行排序決定前後。
- 不接背景共同 publication、dispatcher、C repair、compaction、JD writer 或 UI。
- 不做 artifact GC、文件封存、歷史 UI 或舊資料 migration。

## 5. Gate

本片通過後，才回到 `BackgroundMemoryWorkflow`，串接 B1 staged → B2 staged → 最多一次 case rework → bundle → CAS publication。若實作時發現現有 source owner 無法在不改 canonical conversation authority 的前提下證明歷史 source／sequence，停止並提出具體反例，不自行改成時間戳、文字 offset 或全歷史複製。
