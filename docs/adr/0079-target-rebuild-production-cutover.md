# ADR 0079：新目標重建的正式切換與舊程式退役

- 狀態：**Proposed（2026-10-01）；只完成切換決策草案，尚未切換或退役。**
- 決策者：Product Owner；工程代理依既有 Goal 的條件式授權準備與驗證，不由草案自行放行。
- 擬取代：[ADR0077](0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md) 的正式實作、資料初始化及操作入口；Accepted 前 ADR0077 仍有效，原紀錄不改寫。
- 範圍：將已授權重建的新產品提升為唯一正式入口。不重新決定領域、工具、Context 或保存契約。

## 脈絡

Owner 已要求依新架構重建產品，舊程式與資料僅作參考，不要求整合或遷移。[實作計畫](../plans/2026-09-29-target-rebuild/README.md)已授權施工、本地提交，以及通過最後 gate 後的入口切換和精確舊碼退役；並未授權略過品質驗收或刪除本機資料。

目前新程式位於 `apps/api`／`apps/web`，但根命令、CI 與正式權責仍指向 ADR0077 的產品。若只更新 README、只切根命令，或只刪舊目錄，會留下互相矛盾的操作入口與驗收對象。需要一次可追溯的正式切換，不需要新舊相容層。

本 ADR 借鑑 [Microsoft ADR 指引](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record)的帶狀態、保留原決策及連結 successor 做法（2026-10-01 核對）；切換範圍與 gate 是 Caliburn 的既有決策，不宣稱是外部標準要求。

## 擬採決定

### 唯一正式產品與資料責任

通過下節條件並正式化後，採用 `apps/api` 的後端與 `apps/web` 的介面；不因沿用曾退役的目錄名稱而恢復舊實作。程式分層、工具與資料責任沿[目標架構](../target-architecture-map.md)及[實作入口](../implementation/README.md)，不在 ADR 複製 schema 或操作手冊。

採用已確認的 LangGraph＋OpenAI direct Responses 接線，產品模型固定依 [Luna／high 決策](../implementation/technology-decisions.md#1-首選工具鏈)，不採 Sol 或自動 fallback。正式訪談、JD 與 Memory 業務保存不由模型 Context 或 checkpoint 取代；各自的 owner 及交易邊界仍由相應責任文件定義。

只使用依新產品說明明確配置、初始化的新資料範圍，不搬移或雙寫舊資料，不自行沿用舊產品 DB／provider 設定。初始化、秘密注入、啟停與 PDF 依新 App README；根 runbook 於正式切換時同步更新。舊 DB、volume、秘密、ignored／未追蹤檔與獨立 RAG 均不在退役授權內。

### 入口、依賴及文件共同切換

根 pnpm scripts／workspace、由套件管理器生成的 lock、CI、App README 與全域文件須在同一交付中指向新產品。根命令轉交既有新產品入口，不另造部署平台或移植舊憑證／provider 接線。正式交付採既定的[單程序同源方案](../implementation/interface-and-delivery.md#41-同源靜態建置入口)；開發入口不冒充已部署的產品。

舊可執行程式僅依 [T18 固定 Git 樹盤點](../plans/2026-09-29-target-rebuild/evidence/t18-same-origin-web.md#切換範圍盤點與舊依賴防線2026-10-01)逐檔核對後退役。該清單是可重建的候選，不是遞迴刪除目錄的許可；執行前重新確認工作樹、使用中的程序及新增變更。歷史研究、ADR、實驗結果與沿革文件保留，舊操作說明標為歷史。

## 採用前條件與目前限制

是否可以正式化以[任務表 T18](../plans/2026-09-29-target-rebuild/tasks.md#t18-新產品入口切換與舊程式退役)、[計畫完成條件](../plans/2026-09-29-target-rebuild/README.md#5-整個-goal-的完成條件)及[驗證對照](../implementation/verification-plan.md)為準，不在本頁另建較寬鬆的驗收表。順序為：前置品質／容量／旅程 gate 成立 → 核定本次精確切換範圍 → 切換並驗證根入口與交付 → 同步正式權責與文件。

截至本草案建立時，T14、T16、T17、T18 尚未完成：

- Luna 仍有跨輪 JD 來源漏選的已知品質反例；維持 Luna 不等於接受該缺口或通過品質 gate。見 [T14 證據](../plans/2026-09-29-target-rebuild/evidence/t14-job-analysis-quality.md)。
- 大視窗壓縮仍受實測 token 限流影響；已完成的較小視窗不能代替原門檻驗收。見 [T16 證據](../plans/2026-09-29-target-rebuild/evidence/t16-compaction-continuity.md)。
- Memory 最終失敗後已接線：正式訪談再前進三輪才允許一次新批次（2026-10-01，政策待 Owner 核對）；尚未在真長旅程中實際觸發。見 [T11 證據](../plans/2026-09-29-target-rebuild/evidence/t11-memory-batch.md)。

這些是採用審查時必須查回的狀態，不由本 ADR 升格、豁免或增加新需求。後續變化只在各任務 evidence 與任務表維護，再於正式化時核對本節。

## 切換內容與預先驗證（候選分支 `target-cutover-candidate`）

切換已備成**一組可審提交**，不在原分支放行：根 `package.json`（`dev`／`start`／`build`／`lint`／`typecheck`／`test`／`check`／`app:migrate`／`app:status`，RAG 命令不變）、`pnpm-workspace.yaml` 與 pnpm 重新生成的 lock、CI（改跑同一個根 `check`）、README／ARCHITECTURE／CONTRIBUTING／AGENTS／runbook，以及下節的程式退役。`app:status` 是只讀診斷（`python -m caliburn.status`），不印出密碼或 key；`app:migrate` 是唯一改 schema 的命令。

在乾淨 worktree（只含 tracked 檔案）已驗：鎖定安裝；根 `check`（lint、mypy strict、1,113 單元／契約測試、162 前端測試、契約生成核對、production build）；新 schema 遷移；無設定與有設定的 `app:status`；以根 `start` 啟動的單程序同源 UI（首頁、深連結、資源、API 404）；硬停止後重啟資料仍在。實際輸出與限制見 [T18 證據](../plans/2026-09-29-target-rebuild/evidence/t18-same-origin-web.md#乾淨-worktree-的根命令切換候選2026-10-01)。這些不取代 T14／T16／T17 的品質、容量與旅程 gate。

## 退役範圍與取回

退役範圍是[固定 Git 樹盤點](../plans/2026-09-29-target-rebuild/evidence/t18-same-origin-web.md#切換範圍盤點與舊依賴防線2026-10-01)的 **379 個 tracked 檔**：`experiments/jd-relational-app` 的 336 個非 Markdown 檔、`packages/consultant-memory` 的 41 個非 Markdown 檔（不含 `adoption.json`），以及 `scripts/run-jd-app.mjs`、`scripts/run-jd-app.test.mjs`。保留 16 個 Markdown／`adoption.json` 沿革檔（兩個 README 於頂端加歷史標記）、`packages/job-analysis-contract` 的歷史 README、全部研究／ADR／證據文件與獨立 RAG。不刪 DB、volume、秘密、ignored 或未追蹤檔；不做舊資料遷移，舊 runtime 也不能讀新 schema。

清單可重建：`git ls-tree -r --name-only d08a3b09 -- experiments/jd-relational-app packages/consultant-memory`，排除 `.md` 與 `packages/consultant-memory/adoption.json`，再加上述兩個啟動器。基準提交 `d08a3b09` 是退役前的完整樹。取回單一檔案：`git show d08a3b09:<路徑>`；整批恢復：`git revert <退役提交>`（它只含上述刪除，與入口／文件切換分開提交）。

## 回退與後果

切換前記錄可回查的 Git 基準、精確變更與驗證結果。切換失敗時停止放行，保留新舊資料與證據，修復入口或依精確提交恢復程式；**Git 回退不會回退業務資料，也不能讓舊 runtime 讀取新 schema**。不自動殺程序、刪 DB、清 volume 或重新生成模型結果。

收益是正式入口、CI 驗收對象與責任文件一致，後續開發不必維護兩套產品。代價是沒有舊資料／API 相容承諾，新環境需按新說明設定；Luna 的實際分析品質仍必須獨立驗證，切換本身不會改善模型效果。

未採用的路徑：長期雙產品／相容 adapter 會增加資料與維護責任且非 Owner 需求；前置 gate 未過就切換則會把可跑 Demo 冒充完整交付。兩者均不作本次切換方案。
