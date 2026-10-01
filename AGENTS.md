# Caliburn：工程代理工作指引

本檔只放跨任務的工作方式與文件路由，不作為產品架構、施工授權或歷史決策的副本。以繁體中文溝通，先說效果與證據，再給必要細節。

## 產品與狀態

Caliburn 是本機 Web AI 職務分析與職務說明書（JD）應用程式。員工透過訪談讓 AI 理解實際工作；人與 AI 可編輯同一份 JD。單一操作者可管理多份資料隔離的職務檔案。具體功能、非目標及目前進度以有效決策與責任文件為準，不從本檔推導新需求。

- **現行正式產品**：[`experiments/jd-relational-app`](experiments/jd-relational-app/README.md)（含 `web`）與 `packages/consultant-memory`；正式權責見 [ADR0077](docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)。目錄名中的 `experiments` 不表示它仍是實驗產品。
- **目標架構不等於正式產品**：ADR0077 的現行產品仍有 A／B1／B2／C 等接線；新目標已在 `apps/api`／`apps/web` 實作與驗收中，完成範圍查[任務表](docs/plans/2026-09-29-target-rebuild/tasks.md)，不能概稱全部未實作，也不等於 T18 已切換。討論或圖稿須分清「現行正式」「目標及其實作／驗收狀態」「候選」或「歷史」，不能把其中一種冒充另一種。
- **舊架構與獨立範圍**：原 `apps/api`、`apps/web`、`packages/job-analysis-contract` 已退役，不接回舊接線；2026-09-29 Owner 允許以 `apps/api`、`apps/web` 作新目標重建位置，規劃見[實作入口](docs/implementation/README.md)，不是現行 production 已切換。RAG 是獨立範圍，不是目前 JD App 的依賴。

## 自主工作與提問界線

- 先依請求區分研究／討論／審查、診斷或實作。研究與架構討論先產出有證據的建議，不因看見缺口就擅改 production；已授權的實作則推進到相應驗收，不停在第一版或反覆要求「是否繼續」。插入問題處理後回到未完成的主線。
- 工程代理自行查資料、比較方案、讀相關程式與文件；不把蒐證或技術選型功課交給使用者。可逆、已授權且效果等價的工程細節自行完成。只有答案會實質改變產品效果、資料權責、明顯費用、不可逆結果或跨層契約時，帶具體證據與選項提問；先完成不依賴答案的部分。
- 使用者明確指示優先於本檔及 Skill 的工作慣例，仍遵守系統與工具安全界線。若 Skill 確實讓工作暫停或改向，指出其來源及實際影響，不把它當成額外產品審批。

## 按任務讀取與研究

- 重大研究、架構或跨層變更：先在 [目前決策](docs/current-decisions.md) 定位**本題**的最新狀態與文件路由，再讀相關的 Accepted ADR、設計、程式及測試；依 [決策流程](docs/decision-process.md) 分清討論、核准與正式切換。局部小修只讀受影響範圍，不重讀整份歷史。現行程式／實測說明現況，Accepted ADR 說明正式權責；Proposed ADR、研究及隔離測試不自行切換 production。
- 跨層架構討論依 [架構討論規範](docs/architecture-discussion-standard.md) 的有效狀態進行，並由 [文件導覽](docs/README.md) 找到各層責任文件。工程代理先研究業界成熟做法，再以 Caliburn 的效果與反例比較，不強迫新架構沿用舊元件或框架切法。該規範仍是討論稿，不因本檔連結而升格為正式產品決策。
- 會改變設計的主張，查相關大廠、框架或平台的**當前官方契約**，必要時追鎖定版本原碼、測試與遷移說明。重要 Agent／LLM 設計可比較 OpenAI／Codex、Anthropic／Claude 等公開做法；資料保存、編輯及程序管理查其相應領域來源。分開「官方保證」「公開共通原則」「Caliburn 取捨」「尚未驗證」，不猜廠商未公開的內部實作，也不把單一廠商做法稱作共識。與本題無關的簡單修改不做固定多廠商巡查。
- 研究已足以比較方案且剩餘疑點可有限驗證時停止廣搜。新目標的權責、生命週期與跨層契約寫入相應設計文件；重大正式取捨循 ADR／G6，歷史 Accepted ADR 不直接改寫。文件保留演進順序，入口只維護狀態與路由，避免第二份 authority。

## 實作與驗證

- 新目標的計畫／施工依[SDD／TDD 開發規範](docs/implementation/development-standard.md)及[任務計畫](docs/plans/2026-09-29-target-rebuild/README.md)：直接追溯責任文件，先研究既有成熟機制，再以行為反例 Red–Green–Refactor、小切片交付。命名、模組與依賴沿[程式設計文件](docs/implementation/code-organization.md)；函式／實例／Service、錯誤與非同步寫法沿[程式撰寫規範](docs/implementation/coding-standard.md)。不把計畫完成當實作授權／驗收。
- 先核現有框架、Domain 與資料權威是否已提供所需能力；有具體反例才增補元件，避免第二套 validator、receipt、persistence 或通用引擎。模型不生成 App 已知的 ID、scope、版本及保存結果。新 API／共用格式依 [契約策略](docs/contract-strategy.md) 從正式來源生成，不手改生成檔。
- 正確性或保存問題先找可重現反例與真正 owner，再做有界修正；失敗先診斷，不無限重試。依改動風險跑受影響測試，必要時升到真 PostgreSQL、provider、瀏覽器或使用者旅程；不把離線通過說成真模型或完整產品通過，也不因文件修字重跑全套。純文件改動檢查差異、連結、狀態及相互一致性。
- 動手前確認工作目錄、分支與未提交變更；保留使用者及其他代理的工作。子目錄有局部指引時讀取適用規則。啟停、初始化、資料處置與檢查命令從 [runbook](docs/runbook.md) 及相關 App README 查找；不自動清資料或重建 volume，只停止已確認身分的自有程序。
- 不輸出或提交金鑰。真模型與其他有成本的外送依本次有效授權、資料範圍及費用界線執行；歷史切片的「零付費」限制不自動變成所有後續工作的禁令。未經明確要求不 merge、push、發布或對外傳送。
- 完成已授權的工作後，回報實際效果、驗證層級與未完事項。提交只依本次任務或既有授權精確進行；不預設研究／討論必須 commit，也不一律建立本地 tag。

`CLAUDE.md` 只引用本檔，不維護第二份手抄指引。
