# JD 成品基線與平行設計審查紀錄

2026-09-10；JD-R002。P0完成，P1 Task 1施工中。以下為獨立唯讀審查原始結論；有限設計通過不代表runtime、自然模型或員工試用通過。Task 4／5增補已納回六切片；ADR0074仍Proposed，production authority不變。

# JD 成品有限設計獨立審查

最新結論：2026-09-10 定點複核 PDR-01–04 全部 CLOSED；spec／quality verdict PASS（有限設計）。下方初審 OPEN 與 CHANGES REQUESTED 保留為沿革，最終效力見文末複核。

2026-09-10；review 範圍：主 checkout 的 R2/R3、R5 與 Proposed ADR0074；唯讀核對既有 plan、current-decisions、decision-process、ADR0073，以及隔離 analysis-agent 的 service/catalog/api/sources/memory/publication/scheduling。未執行測試、未修改候選文件／程式、未提交。

## Preflight

- Topic ID：JD-R002/C03、R5、LLM-Q019。
- Current stage：Owner 已授權完整成品計畫；核心隔離 G7 可繼續；本三份候選為 G4 review，production G6 尚未通過。
- Binding decisions：App 內本機多文件、持續工作稿、封存／恢復保留全部資料、永久刪除 PARKED、保留已驗 Memory 策略、正式 authority 另做 successor。
- 唯一問題：這些有限設計能否安全交給各自對應施工切片消費？
- 已讀證據：核心 Task2.4、Task4–5、ADR0073，以及上述實際 runtime；無廣泛再研究。
- Out of scope：施工、測試、付費／自然模型驗收、真人驗收、production mutation。

## Findings

### PDR-01 — P2 — 封存對背景 Memory 的規則互斥，且會影響既有 scheduler 列表來源

- 位置：`docs/specs/2026-09-10-jd-production-adoption-design.md` §2（第35行）、§3.3；對照 R2 §7、§6.1 列表預設。
- 違反：核准總計畫保留既有 Memory；R2 明定背景繼續處理已收到工作且不延長封存等待，但 R5 要求不啟動新背景及等待正在執行工作結束。
- 具體影響：實作者無法一致決定封存是否等待 B/C；若按 R5 停止背景，再將 `list_documents()` 預設改為僅 active，實際 `scheduling.py:99` 的 tick 枚舉就會漏掉 archived 的既存 queued/partial/recovery 工作。恢復前 Memory 可能永久停在半批，並改變已驗調度政策。
- 最小修正：R5 明確與 R2 對齊：封存拒絕新前景／人編，等待前景與必要 JD 結果閉合；已收到來源所衍生的 B/C 仍按原策略（包含尚未首次排程、部分批次及受控恢復）處理，不因 archived 額外啟動工作或等待背景歸零。明列內部 scheduler 使用包含 archived 的完整 catalog 枚舉，UI filtered list 不共用此預設。將此列入固定 archive/background 回歸。
- 狀態：OPEN；影響封存 seam 及 R5 採用前閉合，不阻擋 Task1。

### PDR-02 — P2 — ADR0074 的 G6 順序形成施工循環

- 位置：`docs/adr/0074-tested-consultant-runtime-source-and-memory-adoption.md` Gate（第34行）；對照 R5 §5 A1–A7。
- 違反：decision-process G6 正式化後進 G7 小型施工；總計畫 P4 不跳過 authority gate。
- 具體影響：目前 Gate 寫 A1–A7 審查及必要實證 → G6 → 正式施工，但 A2 本身含 G6、A3–A6 是正式 migration/runtime/Web/restore 實作驗證，A7 要求 code/design/ADR/register 完成同步。照字面執行，要先完成需 G6 授權的正式施工才可進 G6。
- 最小修正：分開「G6 輸入」與「G7/G8 完成條件」：核心／P3 已有授權證據、固定採用 manifest、候選設計 review、0073/0074 的取代範圍先完成 G6；A3–A6 的正式施工／驗證與 A7 closure 隨後執行。A2 中契約實作測試也明列為 G6 後，而不是 acceptance 前必要成品。可沿用已完成隔離證據，不新增無界 spike。
- 狀態：OPEN；須在 production 採用前閉合。

### PDR-03 — P2 — Create 描述會取消已核准的首建空稿原子性

- 位置：`docs/specs/2026-09-10-jd-employee-journey-design.md` §6.1 POST documents（第93行）。
- 違反：核心 Task2.4 明定同一短交易建立 catalog／空稿 revision／head。
- 具體影響：候選寫「row 與 identity 同一短交易，不新增 JD revision」；若按此實作，建立成功可得到沒有初始 head 的文件，後續 current read／人工保存缺合法基底。Create 去重交易亦未明列必須包住原 Task2 的初始 JD 建立。
- 最小修正：明言首次新 key 成功在同一短交易建立 catalog（含 create identity/digest）、唯一初始空稿 revision 與 head；同 key 重試僅回原文件，不額外造 revision；rename/archive 不造 revision。不啟動模型保持不變。J02 應同驗恰一 catalog、初始 revision/head 與 rollback 無半文件。
- 狀態：OPEN；Task4 create 增補前閉合，不推翻 Task2。

### PDR-04 — P2 — 正式 fresh setup 漏列既有背景 admission 持久表及初始化副作用

- 位置：`docs/specs/2026-09-10-jd-production-adoption-design.md` §1 初始化、§2 owner 表、§3.2 正式 ORM 表名／migration、§4 還原驗收。
- 違反：總計畫採用受測 Memory，不重建其調度／恢復政策；日常 startup 不執行 create_all。
- 具體影響：實際 `scheduling.py:23–30` 有 `q019_background_admission`（target/source reference、status、recovery_count 等），且 `BackgroundDispatcher.__init__` 第54行會再次 `catalog.setup()`。候選正式表清單只有 document/run/memory_head/memory_receipt/JD，未列此表或其改名；依清單做 fresh migration 並刪 startup create_all 後，背景會查缺表；若漏刪 dispatcher 的 setup，日常啟動仍偷偷建 schema。它亦是待恢復批次及 recovery limit 的資料，不能憑 Saver 或 publication head 取代。
- 最小修正：把該既有 admission/error metadata 納入採用表名映射／root migration／責任圖（可歸最小 catalog，非第二 workflow owner）；列 dispatcher constructor 的 setup 一併移到明示維護 setup。還原驗證加入 queued/partial/blocked 的 target/source/status/recovery_count 保持；不改其既有語意。
- 狀態：OPEN；R5 fresh-storage/adoption 前閉合。

## Verdict / closure

- Spec verdict：CHANGES REQUESTED。四項都是有限可修正接點，未发现需要重開產品選擇或廣泛研究；修正後再做定點 review 即可交接。Task1 不受這四項阻擋。
- Quality verdict：CHANGES REQUESTED（文件一致性／可施工性）。已核對 stale metadata 的 GET 現況語意、same-key create/run digest（含 selection）、普通 dirty 與 submission recovery、舊 writers/API 退出要求、Saver 精確來源與官方 setup 分工；除此四項未見新的 actionable finding。此為設計 review，不是 DOM／DB／自然模型／真人品質通過。
- Status：候選尚待上述修正；ADR0074 保持 Proposed，production 仍依現行 authority。
- Reopen trigger：修正後設計仍與 runtime／gate 相衝，或對應實作驗收出現具體反證。
- Next gate：主線修候選、同步責任 plan/register 路由後定點複核；不以本報告批准 production 切換。


## 2026-09-10 定點複核：PDR-01–04 closure

本輪僅重新讀取 S:/caliburn 主 checkout 的三份候選，核對上述四項修正及相鄰敘述是否引入矛盾；未重開研究、未執行測試、未改 production 或候選文件。

| Finding | 結論 | 修正證據 |
|---|---|---|
| PDR-01 | CLOSED | R5 §2／§3.3、ADR0074 Decision 5、R2 §7／§9／J08 一致：封存等前景與必要結果閉合，不等背景歸零；既存來源的未首次排程／部分批次／受控恢復沿原策略；內部 scheduler catalog 包含 archived，UI active-only 僅作用 HTTP 列表。 |
| PDR-02 | CLOSED | R5 §5 A2 與表後順序、ADR0074 Gate 將核心／P3證據、A1 manifest、A2設計審查列為 G6 輸入；A2契約實作及 A3–A7 正式施工／驗證／closure 明列 G6 後，不再有先完成正式施工才能正式化的循環。 |
| PDR-03 | CLOSED | R2 §6.1、§9 Task4增補與 J02 均明列首次 catalog/key/digest/空稿revision/head 同交易；失敗無半文件、同鍵 replay 不多造初版，與原 Task2.4 一致。 |
| PDR-04 | CLOSED | R5 §1／§2／§3.2 補 consultant_background_admission、既有欄位及責任；包括 dispatcher constructor 的所有 setup 明列移至維護階段；§4 還原核對 queued/partial/blocked target/source/status/error/recovery_count 且不得重置恢復計數。 |

Spec verdict：PASS（本次有限 G4 設計及指定四項 closure）。

Quality verdict：PASS（文件一致性與可施工性）；未發現修正引入新的 actionable contradiction。可由主線完成計畫／register 的交接同步後，供各對應切片消費；這不批准跳過原施工依賴、production G6、P3付費授權或P6驗收。

Decision / finding：四項已閉合；初審 findings 保留以供追溯。
Status：有限設計 review 完成；ADR0074 仍 Proposed，DOM／DB／恢復／自然模型／真人效果尚待其正式驗收。
Sources：主 checkout R2/R3 §6.1／§7／§9／J02／J08；R5 §1–5；ADR0074 Decision 5／Gate；原初審已讀 runtime 證據。
Affected artifacts：只更新本 scratch report；責任設計與 register 的 durable closure 由主線完成。
Reopen trigger：對應施工產生具體失敗或新的 authority／契約衝突。
Next gate：沿既有隔離核心切片；正式採用依修正後 G6→G7/G8 順序。


# JD 成品品質材料獨立審查

日期：2026-09-10。範圍：`docs/specs/2026-09-10-jd-product-quality-acceptance.md` 對照成品總計畫、current decision register／decision process、完整工作分析／欄位寫作／深度校準／來源手改研究及核心 Task 6。唯讀審查，僅寫本報告；未改 runtime、未跑測試、未呼叫付費模型、未提交。

**Spec verdict：PASS，無可行動阻擋。Quality verdict：材料可交主線整合與 Task 6 精煉；不代表 P3／P6 自然流程或真人驗收已通過。**

- §3–4 將足夠才寫、未知不補、案例與常責分清、有效工作不遺漏、有界更正、K／S 關聯依據、最新已保存訪談及人工現況轉成正反判準。Q01–15 有來源／JD／trace 的核對方式及未觀測狀態；沒有以模型自評或固定 golden 字串取代語意判斷。Task 6 仍是一個按需 Skill／兩份 references，固定接線測試與自然效果分列。
- 純手改不自動成訪談事實或 Memory、舊 source refs 不替新人工敘述背書、最新明確更正不被舊 Memory 蓋回，與既有來源及手改規則一致；未知不阻保存已支持的內容。
- CT49–51、公開合成校準、未見案例、自然流程及真人操作證據清楚分開。§7 明說尚無 sealed held-out，規定事前凍結、接觸紀錄、oracle 隔離、同版兩次、六次前不調校、失敗包轉 regression；hash 不冒充未接觸證明。未揭露工作與已揭露遺漏分開判讀。compaction 未觸發不能冒稱通過。
- §8 的 30／120／180 秒是 P3 實測後、P6 前待固定的本案提案；沒有授權 runtime 強殺／重試或以 streaming 首字冒充保存完成。真人試用未發生、未授權代邀請、協助與失敗如實保留。
- §6 付費批次是待另行授權提案，不延用 CT49–51 授權、不含 P6 額度。既有測試 harness 確有金額／請求保留及離線拒絕檢查：`experiments/analysis-agent/.test-tmp/ct51_service.py` 的 `CT51Ledger.before`（35–55）與拒絕檢查（113–136）；CT49 沿用 Ledger。故「沿既有 limiter／budgethook」不必解讀成新增產品預算層；仍須按本文要求在執行前核實新批次費率／輸入上界與接點，不能把舊測試當新硬上限已驗。本輪不要求改已採 Memory／模型／runtime budget。
- 官方事實抽查：實際重讀 [OpenAI deprecations — Evals platform](https://developers.openai.com/api/docs/deprecations#2026-06-03-evals-platform)，官方列 2026-06-03 公告、2026-10-31 唯讀、2026-11-30 dashboard／API 預定關閉，與 §2 一致；方法論引用沒有被寫成新評量平台依賴。

本輪 actionable blockers：無。自然品質、成本 guard 新批次可用性、P6 私有材料及真人使用仍按原 gates 待驗，不影響零付費 Task 1 施工。


