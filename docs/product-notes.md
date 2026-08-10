# 產品 / UX 決策與延後項

> 不夠「架構」到要開 ADR、但需要被記住的產品 / UX 決策與**刻意延後**的項目。
> 每項標清楚:**現況是不是刻意的**、**為什麼延後**、**未定的取捨**。

> **Current-only 狀態（2026-08-10）**：owner 已授權只保留新的 Job Analysis API、Web `/workspace`、`job-analysis-contract` 與 PostgreSQL。舊 OCS editor、知識索引、PDF ETL、embedder、舊訪談與 `job_authoring` 已移除；本檔後續舊 OCS 段落只作歷史 UX 討論，不能作為新實作入口。

---

## 現行產品範圍鎖定：本機 Web AI 職務分析應用程式

**狀態：已決定（2026-07-23）；只有 owner 明確指示才可改變。**

目前要交付的不是雲端網站或 SaaS，而是一個在員工電腦本機運行、以 Web UI 操作的應用程式。員工的實際體驗必須是：

- 啟動本機 Web app 後，直接與 AI 專業顧問訪談並同步編輯自己的職務說明書；
- 不會收到或登入遠端產品網址；本機啟動流程可以自動開啟 browser／localhost UI，員工不必手動設定 host、port 或部署；
- 不需要註冊、登入、帳號、密碼、公司代碼、workspace invitation 或 tenant 選擇；
- 第一版只處理一名本機操作者，一次開啟並訪談一份職務說明書；同一台電腦可以建立、保存、關閉與重新開啟多份
  彼此隔離的職務說明書。這是本機文件庫，不是帳號 workspace、公司管理或多人共同作業。

「本機 Web app」是產品交付邊界：Web UI、API、資料庫與必要服務皆在本機組合運行，不要求 Electron、Tauri 或原生桌面殼。
可以沿用或重構現有 Web 技術，但不得把 port、服務啟停、資料庫或基礎設施設定暴露成員工的日常操作流程。

本決策也**不等於完全離線**。LLM 可以由本機 Web app 呼叫 OpenRouter；模型 API key 由開發者／owner 在本機設定管理，不由員工建立
模型供應商帳號或輸入 key。若未來需要真正離線模型，必須另案研究品質、硬體與封裝成本，不能默認降低職務分析品質。

### 工程資源優先順序

1. 訪談問題是否專業、自然、有效率，能否處理短答、更正、不知道與上下文；
2. LLM 是否能正確分析工作任務、工作產出、行為指標、K／S，並保留 Evidence linkage；
3. Context Engine、episode 工作分析、文件提案與員工接受／修改／拒絕的完整 loop；
4. 職務說明書內容完整度、一致性、客製化程度與可匯出品質；
5. 能讓員工實際操作、可一鍵啟動的最小本機 Web workspace。

本機 Web workspace 的新文件權威是 greenfield `app/job_analysis`：Current JD 保存員工確認或直接編輯的文件內容，
Current Work Model 保存 AI 可修正的分析。第一版不整合、不雙寫，也不搬遷舊 `job_authoring`／vNext 資料；舊
`DocumentVersion`／OCS deep JSON／`_pending` 不得恢復為新產品真相。詳細裁決見
[`ADR 0043`](adr/0043-job-analysis-local-current-state-persistence-and-authoring-authority.md)與
[`本機 JD 分層編輯與 PostgreSQL 持久化研究`](specs/2026-07-29-local-jd-authoring-and-postgresql-persistence-research.md)。

第一個成品不做 JD 版本歷史、還原或 revision diff。員工 direct edit 直接更新 Current JD；下次 AI 互動前才
reconcile，UI 不必顯示內部待對齊狀態。完成的回合、編輯與提案決策可恢復，未完成的模型回答可丟棄。

### 內部 Job Model 不等於政府公版

**狀態：已決定（2026-07-29）。**政府公版是 export profile，不是內部資料上限。UI 必須容納公版必要欄位，
也可以用分層編輯器增加工作分析資訊。Task 第一版只增加 `purpose/context/frequency/responsibility role/enablers`：
公版與 Task statement 常駐，分析詳情可展開編輯，來源按需唯讀，系統 ID／lineage／generation 隱藏。

第一版不加入 O*NET 群體 `core/supporting`、importance、typicality 或 time share，也不預建尚無 production contract 的
O/P/K/S/A tables。未來匯出才要求與公版格式一模一樣；內部 UI 不必被公版版面限制。

除非 owner 明確提出，**不得投入** organization、tenant product behavior、member／role／ACL、登入、密碼重設、計費、quota、
admin console、雲端部署、多租戶測試矩陣、多人即時協作或其他 SaaS infrastructure。既有資料表的 `tenant_id` 是歷史／FK 相容
細節，不是新增上述功能的授權。也不得因追求全面 hash、audit 或測試覆蓋而延後可操作成品；只保留直接保護文件正確性、
Evidence provenance、員工決策與關鍵 transaction 的安全網。

---

## 選取即自動填(autofill on selection)— 延後

> **本節描述的是 legacy OCS editor,不是現行 `job_analysis`。**
> `OccupationPicker`／`TaskCuratePanel`／`CellFillerPanel`／`services/knowledge/` 的 header-meta
> 服務都屬舊編輯器。**不得拿來接新的 `job_analysis` header**——後者走 `JdHeader` 的 authority
> seam(Journal＋generation＋CAS),見 ADR [0053](adr/0053-jd-header-authority-boundary-and-readiness-scope.md)
> 決定 2／3／5。下面的 UX 期望仍可當未來討論素材,但**實作路徑不適用**。

**使用者期望的 UX**(2026-06-26 提出,當下決定先不動、晚點討論):

- **選職類後**自動填表頭:所屬類別、職能基準名稱、工作描述、基準級別、態度 A、應備資格、補充說明。
- **選任務後**自動填每個任務的 O / P / K / S。

**現況是刻意的「catalog 取出 + 人工 curate」,不是 bug:**

- 選職類(web `OccupationPicker` → `setOccupations`)只寫 `ocs_code` + 職類名 / 工作描述(且取 **profile** 的 job_title/job_summary,非 catalog 官方值)。類別 / 級別 / 態度 / 資格 / 補充要另開〔表頭分類〕面板(預設全勾)按「套用」才寫。
- 選任務(web `TaskCuratePanel`)只建**空** K/S/O/P 格;每格走 `CellFillerPanel` 手動挑 / 打。
- api 的 header-meta 服務 docstring 明講**刻意永不自動寫**,以免重選職類洗掉使用者的編輯。

**實作可行性**:`apps/api/app/services/knowledge/task_detail.py` 的 `task_competencies(pool, task_code)` 正好能取「該任務官方 K/S/O/P」拿來自動填任務格;表頭可重用「全勾套用」邏輯改成 `setOccupations` 後自動套。

**未定的取捨(晚點討論)**:

1. **覆寫策略** = 只填空(保護使用者編輯)vs 每次都從 catalog 覆寫。
2. **任務填什麼** = 「該任務官方 K/S/O/P」vs「整職類池」。

> 注意:上面的檔名 / 函式為 2026-06 觀察,動手前請對照現行 `apps/api` / `apps/web` 確認(api 已做過六邊形重構,服務位置可能調整過)。
