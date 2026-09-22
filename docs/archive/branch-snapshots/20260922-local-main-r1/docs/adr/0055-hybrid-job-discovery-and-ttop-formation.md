# 0055. 混合式職務發現與 T–T–O–P 形成順序

- 狀態：**Accepted**（owner 於 2026-08-03 確認）
- 編號說明：本 ADR 原以 `0042` 起草於離線分支，合併回 `main` 時該編號已由另一條線的[0042-r1-screening-stop-and-a6-first-version-default](0042-r1-screening-stop-and-a6-first-version-default.md) 佔用，故發布為 `0055`。決策內容未更動。
- 日期：2026-08-03
- 範圍：AI 對話如何從職務範圍與員工工作材料形成 Duty／Task／Output／Indicator／KSA
- 延伸：[0040](0040-professional-consultant-engine-and-r1-validation-contract.md)
- 研究：[AI 對話式職務分析路線研究](../specs/2026-08-03-ai-conversational-job-analysis-discovery-route-research.md)

## 脈絡

Caliburn 最終要呈現主要職責 `T1`、工作任務 `T1.1`、工作產出 `O1.1.1` 與行為指標 `P1.1.1.1`，但成品層級不等於
訪談順序。純上而下從既有 Duty／職能基準展開，容易讓分類先決並漏掉員工實際工作；純故事式由下而上能取得具體證據，
卻可能漏掉例行工作、耗費大量訪談，且仍需跨故事整併與結構化判斷。iCAP 的成熟範例採功能分析、在職者訪談與專家確認的
混合方法；OPM／O*NET 也結合多來源、開放新增、Task 整併與人員評定。

## 決定

1. 新專業顧問採**混合式職務發現**，不採純上而下填表或純故事自動生成。
2. 訪談開始時可依職位範圍、既有 JD 與職能基準建立暫定職務框架，但所有 Duty／Task 都只是可新增、修正或否定的假說；
   參考候選不得冒充員工工作證據。
3. 顧問先以開放式工作敘事取得實際工作材料，對高判斷、高風險或例外工作取得具體情境、行動與結果；之後再以日／週／月／年、
   交接、例外、低頻高影響責任及參考 taxonomy 定向補漏。
4. 工作故事不得直接成為 Task。系統要跨敘事比較、整併與修正，形成具有明確成果、可指派／檢核、穩定例行或正式低頻責任的
   Task，再把共享主要目的的 Task 歸納為 Duty。
5. Task 邊界穩定後，才共同定義 Output 與 Indicator。以預期結果反查可觀察行為與品質條件，但不得只憑 Output 自動產生正式
   Indicator。
6. 既有職能基準與 AI 只能提出 KSA 候選；候選必須能連結 Task／Indicator、保留來源與支持度，經員工或適任人員確認後才能納入
   正式 JD。
7. 訪談與分析可依上述順序迭代，畫面與匯出仍以 `Duty → Task → Output → Indicator` 由上而下呈現。`T1`／`T1.1`／`O`／`P`
   是公版顯示與匯出代碼，不取代內部 canonical term。
8. 本決策只固定分析語意與順序，不建立 API、資料表或 Web route。R1 仍只驗證 Task Discovery；R2–R5 依 ADR 0040 gate 逐步加入
   多輪、恢復、Duty／O／P／KSA 與 Current JD。

## 後果

### 正面

- 既有框架能提高覆蓋效率，又不會封閉員工實際工作與新興任務。
- 工作故事保留具體來源，但 Task／Duty 仍經專業邊界判斷，不會把事件、工具或步驟照抄成 JD。
- Output／Indicator 與 KSA 都有 Task linkage 與人工確認邊界，符合現行 Evidence／proposal authority。

### 負面與成本

- 顧問必須同時維持暫定框架、尚未整併的工作材料、Task 候選與覆蓋缺口，不能用單一路徑表單取代 Context Engine。
- 需要防止參考 taxonomy 過早錨定，也要防止故事訪談無限延伸；後續 gate 必須驗證提示順序、補漏與停止條件。
- 「先自由敘事、後顯示 taxonomy」目前是待驗證的產品假說，不得宣稱為官方已證明的唯一最佳順序。
