# JD 完整業務操作、範圍與持續修訂：文件複核

- 日期：2026-09-12；Topic：JD-R002；僅研究與設計文件。
- 結論：**JR-R01／04／05、CS-R01／02 DESIGN CLOSED**；不是功能實測 PASS，整體 G4 仍 Needs revision，ADR0075 Proposed／production0060 不變。
- 責任稿：[業務操作與範圍](../2026-09-12-jd-business-operations-and-scope-design.md)、[工具](../2026-09-12-jd-relational-agent-tool-contract.md)、[schema](../2026-09-12-jd-relational-schema-and-write-contract.md)、[整體設計](../2026-09-12-jd-relational-editor-design.md)。
- 既有 finding：[初審](2026-09-12-jd-relational-editor-needs-and-design-review.md)；R02／03 及 AS-R01 的既有閉合另見[保存複核](2026-09-12-jd-relational-save-contract-review.md)，本輪沒有重跑其實測。

## 1. 授權與研究基準

Owner 授權研究者自行研究裁決任務必要範圍位置，並要求回讀完整 JD／完整工作分析；另明確提醒 LLM 可反覆修改 JD 與 Memory。沒有要求重寫 Memory 引擎或每輪雙寫。

主代理核官方工具與交易／選取契約、全文責任設計；內容獨立審查核對完整工作分析、欄位寫作、深度校準、完整樣稿及樣稿審查。來源、查閱日、版本與授權限制集中在業務稿 §1，不把本案工具名稱、64 個變更上限或條件位置冒稱大廠規格。

## 2. 首次修稿失敗與修正

| Finding | 可重現的文件反例 | 修正及結果 |
|---|---|---|
| CS-R01／P2 | 初稿稱 task 尚無 requirement 時，可把職責內安全／交付條件塞到 description。這違反成果／要求分列與既有定義 | 移動／刪職責可同次新增正確的 outcome／requirement；安全隔離、功能確認放要求，維修紀錄交付放成果。**DESIGN CLOSED** |
| CS-R02／P2 | 初稿有界修正僅能更新既有欄位，無法同次更正技術診斷正文、增刪要求及 unlink 誤寫客服技能 | 改為有限 `jd_revise_work` typed variants，正文、成果／要求、K/S 關係及全職位條件能同候選更正。**DESIGN CLOSED** |

工具審查另提出：結構操作只准 add_requirement 仍可能放錯「交付診斷紀錄」；已採共用 add_task_detail(outcome／requirement) 子集。所有 refs 依同 base 解譯、互斥變更與被刪 anchor 拒絕；按最終候選驗證，避免清名稱再補正文的中間狀態誤拒絕。首敗不能因最終修正而省略。

## 3. 獨立窄複核

`jd_command_semantics_review` 唯讀複核工具 §2–5／10 及業務稿 §2–5；`jd_format_audit` 唯讀複核上述內容反例、業務稿 §3.4／6 與既有內容研究。两者沒有寫入責任稿，主代理處理修稿與跨文件同步。

| 原 finding | 最終文件證據 | 判定 |
|---|---|---|
| JR-R01 | 完整新增任務、有限內容修訂；人與 AI 同完整業務效果及原子邊界；同基準、衝突、最終候選、來源與上限有明確處理 | DESIGN CLOSED |
| JR-R04 | 整欄與選區不同型別；捕捉值／保存後核對、UTF-16／LF、合法邊界、提交重驗，過時不搜尋替代位置 | DESIGN CLOSED |
| JR-R05 | 必要範圍就近、原／目的職責與受影響任務完整呈現；同次補正文或正確子項；禁止自動繼承／轉掛；App 機械驗證與顧問語意判斷分開 | DESIGN CLOSED |
| CS-R01／02 | 兩個首敗及「另一有效月結工作保留」均有修稿與固定案例 | DESIGN CLOSED |

`jd_memory_revision_crosscheck` 額外唯讀核對現行 Memory 與來源路由：保留既有即時修補／背景整併，不恢復 PARKED 完成檢查；來源限原 port 實際發配的精確問答引用。新稿過廣的「Memory source owner」已收斂，明示尚無永久 Memory-version locator，`needs_recheck` 只核 JD target digest。新補充已進需求、業務責任與驗收，沒有宣稱 JD／Memory 跨系統共同交易。

`jd_storage_audit` 最後窄核 schema §6、tools §3／9 與業務稿 §6：最終候選與同列更新仍沿原鎖／savepoint／receipt 邊界，結構附帶新增與主操作共用交易，沒有重開 R02／03。非阻擋的兩處「外部 Memory 來源」舊措辭已統一為原始問答來源。

## 4. 實際執行與後续

本轮執行官方文件查閱、本地內容比對、獨立文件反例審查與 Markdown 靜態核對。沒有修改程式、建表、執行 DB／瀏覽器／provider schema 測試或產品模型呼叫。純字串研究不是 adapter／瀏覽器驗收。

靜態核對：12 份本輪責任文件（決策入口只核新增路由）、145 個本地連結、38 個章節 anchor、13 個 JSON 外形示例，均無錯誤；另核 fence 配對與尾端空白。首次執行被工具的使用者 cache 寫入權限阻擋，改用工作區內 cache 後完成；沒有因此安裝或下載套件。這些只證明文件結構／引用與 JSON 可解析，不證明 provider 接受或業務操作已執行。

施工前仍須 generated schema 的兩家 adapter 離線 fixtures、完整候選真 DB、UTF-16／IME 真瀏覽器及同頁完整操作證據；自然訪談另驗工具選擇、忠實度、持續更正及成本。工具數與上限是驗證候選，不是已實測最佳值。

下一產品單位：未歸任務的成果／要求草稿要如何保留，以及自動保存後的撤回、歷史分組與重開恢復。既有真正未決用途保留，不因技術 finding 閉合就宣稱完整 G4 通過或可直接建表。
