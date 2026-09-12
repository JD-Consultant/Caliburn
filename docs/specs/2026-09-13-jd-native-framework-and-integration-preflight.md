# JD App：框架能力證據與選型前置

- 查閱日：2026-09-13；Topic：JD-R002／DA-04、DA-07。
- 目的：接欄位審核後，依產品需要與現行官方證據比較框架；已有程式僅提供現況及失敗案例，不以框架名稱、已安裝或沿用成本代替採用依據。
- 效力：G2/G4 本案映射；本文初稿為選型前置。後續局部實作依 §1.3 路由，不能把初稿未施工狀態當最新結果。整體 G4 尚未閉合。

## 1. Owner 修正後的選型前提

**2026-09-13 Owner 明確修正：不必優先沿用現有框架／原生元件，不需要整合舊代碼。**原先「沿現有React／Next、FastAPI／Pydantic、LangChain／LangGraph及生成器」的整組採用結論撤回；§2–3保留官方能力與已安裝現況，不再作新技術已選定的證明。

以完整JD、員工管理／訪談體驗、保存可靠性、免費開源限制、現行支援／棄用／安全狀態、可驗證性及維護負擔比較。原生瀏覽器控制項、成熟元件庫及完整框架皆可納入，不能先指定必須用最底層元件，也不因某方案較新便跳過適用性與穩定性。

保留既有JD／Memory研究釐清的能力、資訊保留及單一資料責任要求，不等於必須保留其runtime、檔案結構、adapter或generator。新方案可以直接新寫；舊實測可轉為驗收反例，不能直接算新實作通過。最終選到相同框架也須有獨立證據，沒有「因已安裝加分」或「同名就必須淘汰」規則。無需求的持久AI試稿分支、多人／雲端、舊資料搬移及匯出仍不加入。

### 1.1 選型研究的有限範圍

| 能力面 | 必須比較的內容 | 退出條件 |
|---|---|---|
| 管理與聊天介面 | 六章CRUD、重複項／關係選擇、長文字／IME／鍵盤、差異與歷史／來源呈現、狀態提示；成熟設計系統能承接多少互動 | 以同份JD／同旅程比較至多三個實質方向，列必要接合、授權與未覆蓋範圍，不先指定React或原生表單 |
| 業務與保存 | HTTP與模型入口共用規則、具名操作、關係約束、交易／版本／回執、恢復、schema生成與測試支持 | 採用框架及版本有官方依據；不用舊 service形狀限制API／domain；若變更Accepted權責仍走successor |
| Agent與模型接點 | 訪談／按需工具、可信context注入、流式結果、取消、續談／壓縮、Memory與來源、費用與實測能力 | 比較現行官方SDK／框架，分清本機與託管、資料保存責任及授權；符合既定產品能力，不以「另一套SDK」為由排除候選 |

所有採用項須記查閱日、實際選定版本、穩定／預覽／棄用狀態、授權與限制。版本與相容性未核，僅列候選。資料足以區分方案後停止廣搜；只驗會改變選擇的缺口，不先照舊框架生成契約再補選型理由。

### 1.2 本輪新查的官方候選入口

查閱2026-09-13，以下是能力研究起點，**未完成選型或精確套件版本／授權全量核對**：

- [AWS Cloudscape](https://cloudscape.design/)官方明示供AWS產品使用、React元件及Apache-2.0；[現行開發入口](https://cloudscape.design/get-started/for-developers/using-cloudscape-components/)列一般元件與chat-components。可比較完整設計系統是否降低管理＋聊天的自有UI負擔；不是自動採用AWS介面風格，也不要求使用AWS服務。
- [Adobe React Aria](https://react-aria.adobe.com/)官方列表單、選擇、鍵盤、focus及國際化互動；可比較可組合元件的覆蓋與必要樣式工作。採用前核所需元件版本、授權、繁中及實際輸入行為，不從首頁宣傳推定全部已滿足。
- [OpenAI Agents](https://developers.openai.com/api/docs/guides/agents)區分Agents API、Agents SDK、Responses及各自執行／狀態責任；[Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)提供另一官方runtime參考。要按本機App、Memory／原話責任及工具用途比較，不能把API／SDK／託管服務視為同一層，更不能假定全部免費開源。這是補齊選項，不代表重做整份已研究的Memory方法。

### 1.3 本輪比較後的收束

Owner 後續舉出 TypeScript／React／Next.js／Python，並再次澄清：**不是指定或偏好這些名稱，判準仍為現行主流、大廠公開實務與適用性。**研究者依[主流框架比較](2026-09-13-jd-app-stack-selection.md)選 Next.js App Router＋TypeScript／React、Python＋FastAPI 為 App 框架方向；MUI 免費核心為第一 UI 驗證候選，Cloudscape 備選，SQLAlchemy／Alembic 為資料接合候選。採用理由獨立於舊碼，具體版本組合與 Agent 接點尚未完成，不能把局部選型當整個 RS-F 或 G4 通過。

後續資料層與查詢 HTTP 已依[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)驗證。[人工 runtime 切片](2026-09-13-jd-manual-runtime-slice.md#2-官方依据與有限選型)比較 LangGraph、OpenAI Agents／Temporal、Claude Agent SDK 的具體持久責任後，採 LangGraph 1.2.11＋PG Saver 3.1.2 原生 root state；實際單程序 owner／真 PG 已驗，不 import 舊碼。AWS 支持共用 domain／明確操作身分，不指示本案框架與七欄格式。後續[Windows 宿主與重啟恢復切片](2026-09-13-jd-host-restart-recovery-slice.md)已驗人工操作跨程序恢復，補 Win32 官方接點與 pywin32 312，並記錄 default DACL／舊物件退休的實測修正。[人工 HTTP 接合](2026-09-13-jd-manual-http-slice.md)再驗同一保存 owner、原操作查回、ASGI 斷線界線及本機 Origin，未加框架或升級依賴。完整 AI middleware、文件入口／持久配置、日常啟停與 UI 尚未完成；只因新證據／實測缺口重開此層選型。

## 2. 已核官方能力與先前映射參考

下表的「沿原runtime／現有service／現裝adapter」是前次評估的現況映射，均受§1新準則取代為候選接點，不授權舊碼優先整合；官方能力事實及已決的資料安全效果仍可用。

| 官方來源／狀態 | 官方直接支持的能力 | 本案採用及限制 |
|---|---|---|
| [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)，現行 Responses guide，無固定頁版本 | 模型提出工具呼叫、App 執行並按 call_id 回結果；建議減少已知參數負擔、合併必然連續動作、啟用strict；strict所有property required，可空用null，各object禁額外欄 | 完整新增任務／有界整組更正，App注入scope/run/保存版本；顯式strict，不靠API預設正規化。文件、變更、來源refs由App發配，模型不算SQL欄位／行號。strict只約束形狀，不是已提交或語意正確證明 |
| [Anthropic strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)、[處理工具呼叫](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)，現行滾動文件 | 支援strict輸入schema；client tool由App執行，以tool_use_id回結果，可用is_error表達工具失敗 | 每個結果須帶實際保存狀態；參數錯誤與提交結果未知不同。不能將兩家JSON Schema支援範圍或例外格式假定完全相同，需用現裝adapter作離線fixture與後續核准的服務端驗證 |
| [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools)，OSS Python現行v1路線 | ToolRuntime隱藏於模型schema外，提供context/state/tool_call_id；ToolMessage／Command承接結果與狀態 | 沿原runtime/ports，不自寫第二個agent loop。document/run來自可信執行脈絡；thread_id與tool_call_id各有用途，不能混作業務operation或整輪撤回身分 |
| [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)，現行API | 原生依賴接點可共享邏輯及資源 | 現有api.py已組合JdService；HTTP與LLM adapter共用service／domain規則，不另加DI容器。Pydantic／Schema可驗輸入形狀、值及明示validators；DB交易、跨列關係與保存狀態仍由domain service／DB負責 |
| [React textarea](https://react.dev/reference/react-dom/components/textarea)，頁面目前v19.3 | 原生多行輸入、label、readOnly、選取事件；controlled value應同步更新，不可隨按鍵重建元件 | 保留DOM輸入，延遲的是保存，不是onChange。穩定item key、nullable呈現空字串、server晚回不覆蓋新輸入；中文組字與跨保存undo仍須真瀏覽器驗，不先聲稱全由React解決 |
| [PostgreSQL 16 constraints](https://www.postgresql.org/docs/16/ddl-constraints.html)，官方仍列受支援版本 | 複合PK/FK/UNIQUE、RESTRICT/CASCADE及NULL規則；跨列／跨表不能靠一般CHECK保證 | FK含document；junction去重；task／capability按owner分別刪除；線性parent UNIQUE。初始完整性、發布與receipt維持短交易，不增加通用event sourcing |
| [AWS hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)、[commands／handlers](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html)，現行Prescriptive Guidance | 輸入與基礎設施adapter可分離，業務邏輯可共用；額外adapter亦有維護成本 | 人工HTTP／AI工具可不同，D01／共享K/S／驗版本／交易效果共用。只採必要分層，不加雲端、微服務、訊息總線或動態CRUD引擎 |
| [MDN IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API/Using_IndexedDB)，現行標準非同步API | 本地object store／version upgrade／transaction，可處理錯誤與多分頁版本變動 | 承接既定單份恢復記錄，不能跨網路保持交易；容量、瀏覽器shutdown與記錄相容性須有限實驗。不是第二份正式JD或通用離線同步 |

OpenAI／Anthropic共有「模型意圖→App執行→配對結果」原則；AWS支持入口與業務邏輯分離。它們沒有共同規定本案十三表、命令數、autosave毫秒數或JD欄位。這些是依產品需要作的映射；不聲稱大廠內部亦如此保存。

## 3. 本地版本與免費開源界線

唯讀核對指定隔離checkout的[Web manifest](../../.worktrees/analysis-only-agent/experiments/jd-editor/web/package.json)、[Web授權清單](../../.worktrees/analysis-only-agent/experiments/jd-editor/web/license-inventory.json)、[Python manifest](../../.worktrees/analysis-only-agent/experiments/analysis-agent/pyproject.toml)、[Python lock](../../.worktrees/analysis-only-agent/experiments/analysis-agent/uv.lock)及其已安裝METADATA。下列僅是舊實證使用的版本，**不是新方案的版本鎖定清單或選型優先序**。

| 既有元件 | 精確版本／授權與限制 |
|---|---|
| Next／宣告React／DOM | 16.3.3／19.2.4／19.2.4；MIT。Next打包runtime另記19.3.0-canary-cbb046ab-20260731，不將其冒稱穩定19.2.4；採用時仍檢查實際執行層 |
| FastAPI／Pydantic | 0.141.1／2.13.5；MIT |
| LangChain／core | 1.4.0／1.6.2；MIT |
| LangGraph／checkpoint／checkpoint-postgres | 1.2.11／4.2.0／3.1.2；MIT |
| psycopg／binary | 3.3.5；LGPL-3.0-only，不能統称全部MIT |
| DeepAgents | 0.7.13；本輪確認已存在及既有用途，未選新增JD工作區；既有授權清單沿原Memory採用包核對 |

第三方文件是能力依據；OpenAI／Anthropic provider不是免費開源模型服務，真測仍有獨立費用範圍。新方案獨立選定並固定版本，查安全公告、棄用／migration及實際相容性；舊lock不限制選擇，現有正式產品則不在研究期間被隱式升級。

## 4. 必要自有程式與有限驗證

待方案選定後確認自有程式範圍：完整JD命令及驗證、relational repository／mapper、同文件refs與選區核對、current＋revision＋receipt交易、人工變更與可信run接線、自動保存／未知結果／差異呈現。先查框架現成能力，只有未被覆蓋且為本案必要的部分才實作；不能預先將整段都認定須自製。

| 首要驗證 | 通過／停止條件 |
|---|---|
| generated schema＋兩家離線adapter | required／nullable／nested variants／hidden runtime／call結果配對一致；不支持則調整schema表示或有界adapter，保留完整業務效果及原子性。無法保留時記反例並重開該設計，不默默縮減能力或改成任意JSON／SQL |
| 所選文字元件／繁中／emoji／重複文字選區 | 即時輸入、有效選區、A回覆不清B、組字與重開保留；單元測不能替代目標瀏覽器 |
| 真PG關係／原子發布 | 跨文件FK／重複link／分叉parent拒絕，第二步錯誤無部分發布，結果遺失查原receipt；不以新key補救未知 |
| runtime＋JD-only還原 | 同一顧問可持續改JD／Memory，各自結果可查；撤回只JD，原話與Memory不倒退，下一輪得知人工事件 |

DA-03恢復格式／容量／資料集身分與DA-04精確schema仍須完成；下一單位先按§1完成需求導向的有限選型，再進[新版施工計畫RS-1](../plans/2026-09-13-jd-relational-app-implementation.md)。不把舊方案可用或新候選首頁能力當採用結論。

## 5. 研究核對

前次研究：root核OpenAI Functions、React、MDN及AWS／PG；`jd_command_semantics_review`唯讀核現裝manifest／lock／METADATA、api.py／jd_tools.py／runtime.py，以及Anthropic／LangChain／FastAPI官方正文。當時未找到增加第二套agent框架或富文字核心的必要證據；這不構成排除替代框架的選型結果。Owner 修正後依 §1 比較新方案，前次版本及文件複核不能當新框架已採用。本輪未修改這些來源程式或套件。

獨立文件審查首輪指出：FI-R01／P2「不支持就縮限variant」可能默默削減完整業務效果；FI-R02／P3「Pydantic只驗型別」描述過窄。已分別改為先調整表示／adapter、保留原子業務並在不能保留時重開，以及明確涵蓋值／validators能力。`jd_command_semantics_review`窄複核兩項均**DESIGN CLOSED**；其餘版本／授權、G4/G6、未實測界線及RS-2／RS-5依賴無finding。此為本稿與施工計畫的文件審查，不是RS-1或新產品已執行。

同日 Owner 修正後，`jd_command_semantics_review` 對九份受影響文件再次唯讀窄複核 **PASS，無新增 finding**：AGENTS、入口、需求、整體／旅程設計、Proposed ADR、剩餘工作及施工順序一致，不要求沿用框架或整合舊碼；RS-F 先於 RS-1。靜態核對九檔、134 個本地連結及 19 個 anchors 通過。此結果只證明本次前提同步，不代表 RS-F 完成、框架已採用、產品實測或 G4／G6 閉合。
