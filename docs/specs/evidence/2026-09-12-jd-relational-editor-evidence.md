# JD 關聯式管理編輯器：官方證據與本地現況

- 日期：2026-09-12
- Topic：JD-R002/C01、C03；階段：G2 evidence refresh，供 G4 設計使用
- 範圍：結構化 JD、關聯式保存、App／LLM 工具邊界、變更與錯誤回饋、編輯器角色
- 效力：本稿保存來源與推論，不是 production authority，也不表示資料表或 UI 已完成

## 1. 可以由公開資料支持的共同原則

### 1.1 模型提出結構化意圖，App 執行並回傳真實結果

**Official fact：**OpenAI 將 function calling 定義成五步工具迴圈：App 提供工具、模型回工具呼叫、App 執行、App 回傳工具輸出、模型再繼續。`strict: true` 用於約束參數符合支援的 JSON Schema；工具輸出仍由 App 產生及回送。OpenAI 的 Apply Patch 同樣要求 harness 解析操作、實際套用、記錄成功／錯誤，再回 `apply_patch_call_output`。這些資料沒有表示模型會自行修改 App 或資料庫。[OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)、[OpenAI Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)

**Official fact：**Anthropic 將 tool use 稱為 App 與模型間的契約：模型產生符合 `input_schema` 的 `tool_use`，client 執行後以相同 tool-use ID 回 `tool_result`；執行失敗以 `is_error: true` 回傳，並建議錯誤內容要說清楚發生什麼及可採取的下一步。Anthropic 也建議以 strict tool use 降低缺欄或型別錯誤，並以「何時使用」區分容易混淆的工具。[Anthropic How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)、[Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)、[Troubleshooting tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use)

**Cross-source principle：**模型輸出是待執行的意圖，不是已保存事實。文件 ID、目前版本、排序值、資料庫外鍵、交易狀態、operation identity 與成功宣告應由 App 配發、核對或回報。Strict schema 能約束形狀，不能取代業務規則、版本檢查或資料庫交易。

**Caliburn mapping：**JD 工具接收有限、具名的業務操作；App 將它映成同一 application service 的 command。LLM 不接觸 SQL、表名、行號、Slate path 或 client 自行計算的版本號。錯誤結果帶 code、真實 effect、可讀訊息與下一步，不只回 `failed`。

### 1.2 關聯身分、關係表與刪除政策是資料模型責任

**Official fact：**PostgreSQL 16 以 primary key、foreign key、unique constraint 維持列身分與引用完整性；官方文件直接以 junction table 示範多對多。`RESTRICT`、`CASCADE`、`SET NULL` 等刪除行為都有正式機制，但官方明確指出應依相關物件是否能獨立存在來選，不存在所有關係共用的單一刪除政策。[PostgreSQL 16 Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html)

**Official fact：**Microsoft Dataverse 的官方關係文件把 1:N 與 N:N 列為基本表關係，並將「刪除一列時相關列如何處理」列為關係設計必須回答的問題。Notion 的官方 relation 文件顯示，使用者可以從一個項目選擇關聯項目，反向檢視由同一關係呈現；這是產品行為證據，不是其內部 SQL schema 公開說明。[Microsoft Dataverse table relationships](https://learn.microsoft.com/en-gb/power-apps/maker/data-platform/create-edit-entity-relationships)、[Notion Relations & rollups](https://www.notion.com/en-gb/help/relations-and-rollups)

**Cross-source principle：**一對多從屬內容與多對多共享內容應有不同的生命週期。關係的反向畫面應從同一關係推導，不要求人或模型維護兩份清單。刪除政策不能靠前端按鈕臨時決定。

**Caliburn mapping：**任務的成果／要求是任務擁有的一對多項目；K/S 是同份 JD 的共享定義，經 junction relation 供多個任務引用。任務移到另一職責只改關聯，不改任務身分及其從屬內容。D01 現依 Owner 授權採刪職責、保留任務為未分組，詳 §7；DB 保留 `RESTRICT` 作防護，由 App 在同交易明確解除分組再刪職責。職責共通條件的保留仍屬 JR-R05，不以關係完整取代內容驗收。

### 1.3 多列修改必須在同一交易完成

**Official fact：**PostgreSQL 交易把多步驟組成全成或全敗的操作，未提交中間狀態不對其他交易可見；需要保護同一份文件目前狀態時，可使用 row-level locking，而不必鎖住所有文件。[PostgreSQL 16 Transactions](https://www.postgresql.org/docs/16/tutorial-transactions.html)、[Data Consistency Checks at the Application Level](https://www.postgresql.org/docs/16/applevel-consistency.html)

**Caliburn mapping：**一次人工保存或 AI 工具操作中的 current rows、歷史修訂、head 與 operation receipt 同交易提交。文件 A 的 head row lock 不應阻塞文件 B；既有隔離核心曾出現全域 Python lock，已確認需在後續新設計中移除。

### 1.4 編輯器 runtime 不是業務資料庫

**Official fact：**Plate 官方 API 將 `children`、`selection` 與 `operations` 列為 editor runtime 的主要表面；editor instance ID、runtime metadata 與 DOM state 也屬編輯器運行狀態。Plate 並未提供 JD 關聯資料庫、外鍵、交易或任務／K/S 生命週期。[Plate Editor API](https://platejs.org/docs/api/core/plate-editor)

**Local verified fact：**隔離核心固定 Plate 53.3.11；已保存套件清單與授權，Plate 核心多數為 MIT，`@platejs/diff` 另含 Apache-2.0／雙授權材料。既有固定操作證明它可處理其文件樹、selection、history 與部分 diff，不證明整份 Plate JSON 適合作為新的 JD relational authority。[既有 Plate 證據](2026-09-09-jd-oss-plate.md)

**Caliburn mapping：**結構化表單、CRUD、關係與保存由 App／DB 承擔。Plate 只在需要富文字或原生 selection/history 的單一文字欄位內作候選 leaf editor；若普通文字欄位已滿足內容語意，第一版不為保留框架而強制使用 Plate。

### 1.5 JD 欄位語意有官方參照，畫面與資料表仍是本案選擇

**Official fact：**iCAP 現行職能基準把職責／任務建議為主要兩層，並分別定義工作產出、行為指標、知識與技能。行為指標描述任務情境中成功完成的行為或產出；工作產出是關鍵過程或最終成果。[iCAP 職能基準項目說明](https://icap.wda.gov.tw/ap/knowledge_introduction.php)

**Caliburn mapping：**沿 Owner 已確認格式，成果與「工作執行要求」是任務下兩組並列清單，不配對、不合併。`requirement` 作穩定 domain kind；畫面中文名稱仍可改，不牽動資料關係或歷史格式。

## 2. 來源版本、狀態與限制

查閱日期均為 2026-09-12。

| 來源 | 適用版本／狀態 | 授權或使用界線 | 可直接支持 | 不能支持 |
|---|---|---|---|---|
| OpenAI Function calling／Apply Patch | 官方現行 API 文件；範例含 GPT-6 Astra | 服務 API，非本地 OSS 依賴 | typed tool loop、strict input、App 執行及回結果 | OpenAI 內部 JD schema、SQL 表或本案 UI |
| Anthropic tool use／errors | 官方現行 Claude Platform 文件；tool reference 為版本化工具契約 | 服務 API，非本地 OSS 依賴 | call/result correlation、strict、`is_error`、可採取的錯誤訊息 | Anthropic 內部 JD schema、固定重試次數或本案刪除政策 |
| PostgreSQL | repo 指定 16；穩定官方文件 | PostgreSQL License | PK/FK、junction、delete actions、transaction、row lock | 自動替本案選表數、snapshot 或 UX |
| Plate | 隔離 lock 53.3.11；官方 current API 與固定版本本地證據 | 逐套件 OSS 授權已保存；付費 Plus 不列入 | 編輯器 value、selection、operations、history／diff 候選 | relational authority、跨欄 CRUD、DB rollback |
| iCAP | 官方現行頁面，頁面未列版號／更新日 | 作方法參照；不主張版型內容可任意重製 | 職責／任務、產出、行為指標、K/S 語意 | Caliburn 的欄名、個人化 JD 表數或 UI |
| Microsoft Dataverse／Notion | 官方現行產品文件 | 產品參照，不採用其付費平台 | 1:N／N:N 管理、關聯選擇與反向閱讀、刪除需設計 | 內部 SQL 實作或 Caliburn 必須照抄畫面 |

## 3. 本地現況與舊編輯器可學部分

### 3.1 現在隔離 JD 核心

- `q019_document` 是多文件 catalog。
- `jd_head` 指目前版；`jd_revision.value` 是整份 JSONB；`jd_operation` 保存操作結果。
- 職責、任務、成果、要求及 K/S 目前不是獨立 relational rows。
- Plate 畫面把完整 JD 當文件樹，因而能閱讀但不符合 Owner 要求的項目管理體驗。

本地直接來源：[catalog](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/catalog.py)、[JD store](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/jd_store.py)、[隔離 editor README](../../../.worktrees/analysis-only-agent/experiments/jd-editor/README.md)。

這是已驗現況，不是新方向的正確性證明。既有測試與故障證據保留，之後可重用 operation receipt、版本核對及恢復情境。

### 3.2 舊管理畫面

舊 `ApprovedDocumentEditor` 已提供新增／刪除職責、任務、任務選擇職責、O/P/K/S CRUD 及 K/S 多任務勾選；這證明 Owner 所說的「管理 JD」具體包含哪些操作。舊後端仍把整份 `ApprovedJobDocument` 放入 LangGraph／整體物件寫入，沒有 duty/task relational tables，所以不能直接移植為新 authority。

本地直接來源：[舊管理畫面](../../../apps/web/src/features/consultant/ApprovedDocumentEditor.tsx)、[舊 domain models](../../../apps/api/app/consultant/state.py)、[舊 Postgres／LangGraph adapter](../../../apps/api/app/adapters/langgraph/postgres.py)、[舊 export mapper](../../../apps/api/app/export/approved.py)、[iCAP XLSX 測試](../../../apps/api/tests/test_job_analysis_export_xlsx.py)。

可作需求參考的行為：

- 未分組任務可存在，移動任務只改 duty reference。
- 刪任務時，任務專屬 O/P 隨任務處理，共享 K/S 定義保留並解除 relation。
- 共用 K/S 可從一處編輯並看到多個任務引用。
- 舊系統另有 iCAP XLSX 投影，證明結構化資料可確定性輸出；它的舊欄位與舊 authority 不自動成為新格式。

不可沿用：整份 PUT 覆蓋、舊 package／route／checkpoint owner、舊批准稿生命週期、舊刪除政策的默認效力。

## 4. 尚未由外部資料證明的事項

1. OpenAI 與 Anthropic 都沒有公開「AI 與人共編 JD 應使用哪些 SQL tables」；本案 schema 是由已確認的產品關係映射，不稱為兩家共同內部實作。
2. 沒有已核實的共同規範要求所有分類都保留或連帶刪除成員；D01 已依 Owner 授權由研究者按物件獨立性裁決，官方依據與本案映射見 §7，不能冒稱 AWS 的一種產品行為就是普世規定。
3. 目前沒有證據要求每個文字欄位使用富文字；Plate leaf role 需在畫面原型或內容需求出現 marks／list 等必要性後才固定。
4. 歷史採 relational row version、event sourcing 或 derived snapshot 都可成立；應按單機、多文件、精確前後比較與施工風險選擇，不能將其中一種冒稱唯一主流。
5. Owner 已選 JD 第一版先提供 Excel；iCAP 或其他具體版型仍未選定。資料設計須可投影，但不能據此宣稱下載成品已完成。

## 5. 證據結論

「relational current rows＋同交易 derived immutable snapshot＋operation receipt」有上述官方機制作為候選基礎；但[最新審查](2026-09-12-jd-relational-editor-needs-and-design-review.md)已找到讀取一致性、失敗回執等未閉合項目，不能僅憑模式合理就宣稱滿足完整 CRUD 與恢復需求。這是 Caliburn 的候選映射，不是供應商公開的相同表名或完整組合，亦未通過本輪設計驗收。

下一層閱讀：

- [Owner 方向與需求](../2026-09-12-jd-relational-editing-requirements.md)
- [整體設計](../2026-09-12-jd-relational-editor-design.md)
- [資料庫與保存契約](../2026-09-12-jd-relational-schema-and-write-contract.md)
- [AI／App 工具契約](../2026-09-12-jd-relational-agent-tool-contract.md)

## 6. Owner 提供的外部研究參照（2026-09-12）

來源：[ChatGPT 分享：研究 LLM 與 APP 通訊操作](https://chatgpt.com/s/t_6aa53c079e2081919a9cfa54551e3bb4)。已以瀏覽器讀取分享頁正文的十三節；頁中提及的另份完整報告及全部 33 份來源不列為已逐一核驗。分享是二手研究，不能取代原始官方契約或本案需求。

| 分享主張 | 本案評估與採用界線 |
|---|---|
| 人工 UI 與 AI 共用正式 App 操作，不必共用相同 endpoint | 與 Owner 明確要求及本案責任方向一致。功能與規則仍先由實際 JD 操作情境定義，不因分享取名 `DocumentCommandService` 就凍結程式結構。 |
| 按業務操作設計工具；相關修改可原子批次完成 | 支持重審七個過細工具與 JR-R01。分享的 `changes[]` 是可比較候選，不是兩家共同規定的 payload；仍需核對完整新增、更正、拆分等實際需求與模型負擔。 |
| 讀取多表要有一致快照；跨表寫入用短交易；回覆遺失查實際結果 | 與先前已核 PG 依據及 JR-R02／R03 的方向相符；分享不能替本案閉合 failure receipt／recovery 接線。 |
| 已知參數交 App，說清工具用途、參數及結果 | 本輪再次核 OpenAI Best practices、Claude Define tools；两者均有直接依據，後者也明列整合相關操作。 |
| 原生 tool calling 與 MCP 是不同接入選項 | 暫以現有自家顧問與 App 的使用需求討論；外部 host、OAuth、MCP、核准提案等段落不自動變成本版功能。若有接入需要，再核 host／SDK／協定相容性，不能把最新規範當所有實作均已支援。 |

本輪定點核對：[OpenAI Function calling — Best practices](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)、[Claude Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)。查閱 2026-09-12；現行官方 API 指引、非新增本地 OSS 依賴；只支持工具設計與分工原則，不證明本案 schema／操作數已定。

下一步仍是[功能目的釐清](../2026-09-12-jd-relational-editing-requirements.md#7-功能目的與使用方式釐清2026-09-12持續討論)。本次新增研究參照與需求回答，沒有依分享施工、切換框架或採用其完整示例。

## 7. AWS 業務邏輯與 D01 裁決依據（2026-09-12）

Owner 要求業務邏輯多參考 AWS，並授權研究者決定含任務職責的刪除政策。本節定點核對官方現行文件；只採可直接支持的原則，AWS 服務本身不列入本機 App 依賴。

| 來源 | 版本／穩定狀態／授權界線 | 官方事實與本案適用界線 |
|---|---|---|
| [AWS Resource Groups：Deleting resource groups](https://docs.aws.amazon.com/ARG/latest/userguide/deleting-resource-groups.html) | 查閱 2026-09-12；`latest` 現行服務文件，該頁未標 preview 或列單頁版號；服務文件參照，非免費開源套件採用 | 刪群組保留成員資源及成員 tags，移除群組結構及群組自身 tags。支持分類與成員生命週期可以分開；不證明 AWS 其他服務同樣處理，也不證明 JD 職責說明可無條件丟棄。 |
| [AWS Prescriptive Guidance：Hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html) | 查閱同上；现行架構指引，非版本化 SDK／API 契約，無 preview 標記；只引用方法，不複製範例或加入雲端依賴 | 多種 client 可使用同一 domain logic；ports／adapters 分開業務、UI 與資料存取。也指出額外抽象的維護成本；不要求為每一層建立框架。 |
| [AWS Prescriptive Guidance：Adapting to change](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html) | 查閱同上；現行方法指引，非 runtime 版本或免費服務承諾 | commands 與 handlers 可由不同 client 呼叫；採完整 CQRS 前須衡量代價，也可先只採命令處理方式。本案不因此加入消息佇列、微服務、event sourcing 或第二個讀取資料庫。 |
| [PostgreSQL 16：Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html#DDL-CONSTRAINTS-FK) | 查閱同上；本案指定且仍受支援的穩定主版本；PostgreSQL License | 從屬物件可考慮 CASCADE，獨立物件可採 RESTRICT／NO ACTION，可選關係可採 SET NULL。資料模型決定策略，不是依樹狀畫面一律連帶刪除。 |

**共同原則與個別事實分開：**AWS 群組是具體產品例子；PostgreSQL 是關係完整性契約。兩者可支持先分清分類、獨立物件與從屬內容，再明定刪除影響；不能合稱「大廠一律刪父留子」。AWS 的業務與接入分離，與本輪已核 Microsoft 領域分層及 OpenAI／Anthropic 的 App 執行工具責任相容，但這些來源沒有規定本案表數、工具數或程式類別名稱。

**本案裁決：**沿已有「任務可未分組、可移至另一職責」的內容語意，採刪職責時保留任務及其從屬內容／共享引用。[D01 產品政策與效力](../2026-09-12-jd-relational-editing-requirements.md#8-d01刪除職責時保留任務2026-09-12)保存目的、替代方案與重開條件。職責名稱／說明及自身來源仍是真實內容，不能把刪職責說成所有內容原樣保留；JR-R05 負責補齊仍有效條件在目前稿的保留流程。

**人與 AI 共用業務操作的落點：**畫面與模型工具各解讀自己的輸入，交給相同的應用操作處理；移除分組、保存歷史及結果屬一次完整業務效果，由 App 掌管。不同入口須通過相同刪除影響、資料完整性、版本與保存規則；不得人工一次完成、AI 卻需要逐筆改外鍵。DB `RESTRICT` 保護直接刪除，App 先解除分組再刪職責；它是防止漏做命令步驟，不是仍待 Owner 選政策。具體交易失敗回執及工具粒度仍待 JR-R01／R03 修正，不因本節方法有依據便視為完成。

停止本題廣搜：政策判斷已有官方依据與本案語意支持，剩餘未知是 scope／來源、交易與實際操作反例，交責任設計與有限驗證閉合；不再為選出表數或固定工具名稱尋找不存在的廠商標準。

**本次核對結果：**獨立唯讀審查已核對九份責任文件的 D01 同步，結論 PASS（僅限授權、政策、來源生命週期、App／DB 分工及狀態一致性）。主代理核對相對檔案連結、三個新增章節錨點及空白檢查通過；修改前九檔保留於 `.research-tmp/d01-policy-20260912-before/`。未執行 runtime／DB／自然模型；JR-R01–05、G4 Needs revision 與 ADR0075 Proposed 仍保持，不能以本次窄複核替代整體設計審查。
