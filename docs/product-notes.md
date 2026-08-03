# 產品 / UX 決策與延後項

> 不夠「架構」到要開 ADR、但需要被記住的產品 / UX 決策與**刻意延後**的項目。
> 每項標清楚:**現況是不是刻意的**、**為什麼延後**、**未定的取捨**。

---

## 現行產品範圍鎖定：伺服器部署、瀏覽器存取

**狀態：已決定（2026-08-03；取代 2026-07-23 的員工電腦 localhost 假設）。**決策見
[ADR 0044](adr/0044-server-deployed-browser-product.md)。

Caliburn 是由企業或我們操作伺服器、員工以瀏覽器使用的 Web application：

- 企業可在自己的伺服器、內網或私有環境操作一套企業自管 deployment；
- 我們也可操作彼此獨立的代管 deployment，讓企業使用者經核准網址存取；
- Web、API、PostgreSQL、Qdrant、GPU embedder 與 OpenRouter key 都在 deployment 端，員工裝置只需瀏覽器；
- 員工不負責 host／port、服務啟停、資料庫、GPU、備份或 deployment secret；
- 第一個 production scope 是一個 deployment 服務一個企業，可保存多份彼此隔離的 JD；一次開啟一份文件的 UI 限制可保留，
  但不再稱為「本機文件庫」。

企業自管或我們代管不等於立即建立共享多租戶 SaaS。本階段不做 tenant control plane、跨企業共享資料庫、organization/member、
ACL、quota、billing 或 tenant admin。若 deployment 將由多名使用者或非受控網路存取，登入、企業 SSO、角色與 actor scope
必須在 R8 暴露前另案固定；「部署在內網」不能自動被當成安全身分。

本產品不要求 Electron、Tauri 或原生桌面殼。開發者仍可使用 localhost；那只是 development profile，不是員工交付方式。

### 工程資源優先順序

1. 訪談問題是否專業、自然、有效率，能否處理短答、更正、不知道與上下文；
2. LLM 是否能正確分析工作任務、工作產出、行為指標、K／S，並保留 Evidence linkage；
3. Context Engine、episode 工作分析、文件提案與員工接受／修改／拒絕的完整 loop；
4. 職務說明書內容完整度、一致性、客製化程度與可匯出品質；
5. 能在 server deployment 上由員工透過瀏覽器完成主要旅程的最小 `job_workspace`。

`job_workspace` 的文件權威是 `app/job_authoring` current canonical relational state；畫面可採政府公版欄位排列，但舊
`DocumentVersion`／OCS deep JSON／`_pending` 不得恢復為新產品真相。詳細裁決見
[`ADR 0039`](adr/0039-local-multi-document-canonical-public-form-workspace.md)。

**2026-07-24 owner correction：**第一個成品不做 JD 版本歷史、還原或 revision diff。員工儲存與接受 AI proposal
直接更新每份文件的 current rows；既有 0011 revision core 暫留但不再擴張。詳細 current-table 設計見
[`Job Authoring v2 本機單一現況儲存設計`](specs/2026-07-24-job-authoring-v2-relational-storage-research.md)。

**2026-08-02 切換裁決：**現行 v3／OCS editor 維持過渡 production 且只做 maintenance；新路徑在 R1–R5 gate
通過後，以整份 `document_id` 單寫者切換到 current rows。禁止同文件 dual-write；退役順序與資料處理見
[`ADR 0041`](adr/0041-document-boundary-single-writer-cutover.md)。

### 第一版文件地位：員工確認的 JD 草稿

**狀態：已決定（2026-08-03）。**第一版 Current JD 是員工直接編輯或接受／修改 AI proposal 後形成的
**員工確認 JD 草稿**，可匯出後交主管／HR 審閱，但不宣稱已代表企業正式核准、組織政策或 SME 共識。
這延伸 [ADR 0037](adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md) 的員工文件權威：
「current draft truth」只回答目前草稿內容由誰決定，不等於建立企業 approval authority。

現行單企業 deployment 不新增提交、退回、簽核、主管／HR reviewer role 或多人共編。未來可研究多人審閱與共享平台，但
未另案前不得據此新增 organization／tenant、ACL 或 SaaS control plane。企業自管與我們代管 deployment 已屬現行產品邊界，
不得再把 server deployment 本身列為禁止項。

### 第一版發布門檻：真實員工試用

**狀態：已決定（2026-08-03）。**完整 server-deployed Web、工程測試與模型 eval 通過後，只能稱為 **release candidate**。
第一版在稱為「可供員工使用的成品」前，必須由實際在職、也是預期操作者的員工，以本人目前工作完成端到端試用，並驗證
操作結果、互動理解、T–T–O–P／KSA 內容、安全／agency 與 provenance。高擬真 transcript、模擬 persona、產品團隊自測、
合成 eval、LLM grader 或僅由主管／HR／SME 離線審閱，都不能取代此 gate。

Pilot 開始前須另由 owner 核准 release scope、參與者 coverage、樣本數、rubric 數值、blocker severity、資料處理與最終
release authority；無預先門檻或可追溯證據時不能判定通過。通過 gate 仍只代表經真實員工驗證的「員工確認 JD 草稿」產品，
不代表企業正式核准或組織級效度。決策見 [ADR 0043](adr/0043-real-employee-pilot-release-gate.md)。

### 內部 Job Model 不等於政府公版

**狀態：已決定（2026-07-24）。**政府公版是 UI／export profile，不是內部資料上限。內部 Task 可以保存
`purpose/context/frequency/ownership/importance/typicality/optional time share`，用於專業訪談、核心任務判斷與
文件品質檢查。`time_scope` 與 `polarity` 只作 Evidence materialization gate，不進正式 JD。頻率不等於重要性，
低頻高風險任務仍可為 core；也不要求每項工時比重必填或全文件加總 100%。這些資料主要從自然工作敘事抽取，
只針對高價值缺口追問，不按公版欄位逐格盤問。

除非另案核准，**不得投入**共享多租戶、organization、tenant product behavior、member／role／ACL、密碼重設、計費、quota、
tenant admin、多租戶測試矩陣或多人即時協作。這不禁止企業自管／我們代管的 server deployment，也不禁止在 R8 前研究必要的
OIDC／SSO access seam。既有 `tenant_id` 是歷史／FK 相容細節，不是共享 SaaS 授權。

---

## 選取即自動填(autofill on selection)— 延後

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
