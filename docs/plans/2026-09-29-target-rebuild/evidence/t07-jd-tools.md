# T07：JD 按需工具與來源的施工證據

## 1. 第一切片：導覽與同範圍物件定位（2026-09-30）

承接 `79b773ee`；T03／T04／T05 前置已具備，T06 共用恢復接縫仍依原任務續做。此切片完成精簡 map 與精確下鑽的定位基礎，不宣稱完整 `read_jd` 或八入口已交付。

責任來源：[A context](../../../specs/2026-09-26-consultant-context-and-state-design.md) §3.2–3.3、[JD 工具契約](../../../specs/2026-09-29-jd-model-tool-contract-review.md)、[JD 欄位指南](../../../specs/2026-09-09-jd-field-and-writing-guide.md)、[共同工具規範](../../../specs/2026-09-27-agent-tool-contract-design-research.md)及程式／契約規範。欄位的唯一 wire 來源是 `apps/api/contracts/tools/jd-map.schema.json`；接線說明由 [JD 保存接線 §3.2](../../../implementation/jd-storage.md#32-模型導覽與既有物件定位)維護，不在此複製 schema。

### 實際效果與取捨

- 使用既有候選一次捕捉的 profile／work 修訂，投影完整 map；不保存另一份 map、不重新用模型摘要、不另設短 ID registry。
- 既有物件 identity 產生 `read_ref`，只在本次 App 提供的可見 revision 內解析；同名異物件不混淆，改名仍為原物件，刪後同名新建不能承接舊定位。
- 導覽保留未歸屬任務、成果／要求數量、全部可用集合及合法未填妥名稱。明定 preview 才取文字前綴加省略號，其餘無靜默裁切／假摘要。120 字元是可調初值，沒有宣稱已驗最佳品質。
- 查 [Azure CQRS 官方模式](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)，借查詢投影與修改分責、共用既有儲存的基礎形式；未引入 broker、event sourcing 或獨立讀取 DB。參考資料與實際選擇不混稱廠商保證。

### 驗證

1. Typed 骨架的行為 Red：導覽與 resolver 尚未實作，**10 failed**；實作後同檔 **10 passed**。不是把缺 import／工具未裝當成行為失敗。
2. 加 schema／真 PG 後，專項 **14 passed in 1.87s**：10 unit、1 contract、3 PG。PG 覆蓋候選導航與正式隔離、刪職責後任務完整保留、跨檔案定位拒絕，以及已取消 execution 不再提供候選基底。
3. 受影響回歸：`pytest tests/unit tests/contracts tests/integration/test_jd_candidate_navigation.py tests/integration/test_jd_candidates.py -q -p no:cacheprovider --tb=short`，**731 passed in 15.70s**。使用明確 loopback PostgreSQL `127.0.0.1:55439/caliburn_t01_test`；不是本增量完整後端、瀏覽器或真模型驗收。
4. Ruff check／format **236 files**、mypy **160 source files** 通過。生成、前端型別、文件及獨立審查結果於本節接續記錄。

測試先遇到 unit／integration 同 basename 的 pytest collection 衝突；更名為 `test_jd_candidate_navigation.py` 後再跑，沒有修改產品規則或刪掉斷言。首次契約生成因 sandbox 子程序存取臨時檔的 `PermissionError` 失敗；核對既有生成器後，獲准以同一命令執行完成，沒有改生成器、手改 DTO 或下載套件。

當次未讀 `.env`、無付費外送、無 migration／依賴變動、無 production 切換。原有較廣測試證據可重用，不宣稱前次全套涵蓋此次改動。

主代理最後以既有生成器 `--check` 完成全部契約比對；前端 `tsc --noEmit` 通過。獨立 reviewer 未發現本切片可重現的實質缺陷，專項 **14 passed（3 項真 PG）**、分層 **15 passed**，另驗 200 筆集合完整性、119／120／121 字元界線、null 名稱、改名／重建及投影不污染來源。Reviewer 的整套生成因暫存權限未完成，僅同工具逐項比對本次 Python／TS／封裝 schema；不拿它替代主代理已完成的全生成比對。數量不與主回歸相加，仍未宣稱完整工具／模型品質驗收。

## 2. 未完範圍與下一步

依 Owner 的先跑通優先序，沿既有 owner 接上 JD 精確／區域／全稿讀取、來源與編輯 handler，再接 A 的完整保存閉環；不先做額外觀測平台或完整效能調校。不得用假的空來源陣列把未完成來源能力包裝為正式工具。

- T07 仍欠來源保存與核對、current_input 接線、兩類 diff、完整 read 與八工具 handler 的組合及相應必要反例。
- T06 尚欠已保存但結果未明的原 attempt 核對後受控恢復，範圍見[原任務 §18](t06-agent-execution.md#18-下一個可執行切片)。不是用導航切片掩蓋恢復缺口。
- T08／T09 才提供 A 正式 Turn、控制及候選預覽；T12／T15 的廣故障矩陣／效能、T16／T17 的真 provider／長訪談留各 gate。不為本次純 mapper 重跑整套 UI 或付費品質評測。
- `read_ref` 不是寫入許可或讀過全文的憑證；map 正文預覽也不等於已閱讀完整修改目標。後續 handler 使用原契約與既有候選資格，不自行推導授權。
