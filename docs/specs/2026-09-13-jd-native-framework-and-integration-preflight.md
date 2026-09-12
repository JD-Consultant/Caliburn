# JD App：原生框架能力與接線前置

- 查閱日：2026-09-13；Topic：JD-R002／DA-04、DA-07。
- 目的：接欄位審核後，選出能承接新 App 的現有能力與真正需要本案實作的部分；不再廣搜全套 Agent／編輯器，不以框架名稱替代可驗契約。
- 效力：G2/G4 本案映射；未升級依賴、建表、修改 runtime 或呼叫產品模型。整體 G4 尚未閉合。

## 1. 核對結果與採用方向

**沿現有 React／Next、FastAPI／Pydantic、PostgreSQL／psycopg、LangChain／LangGraph及契約生成器。**新版是具名欄位與關係 CRUD，先採瀏覽器原生文字與選擇元件；Plate 不再是目前正文權威，本版也不以啟用 leaf Plate 為前置。只有真瀏覽器測得普通欄位無法滿足已定需求，才依反例比較有界替代，不因想像 IME 風險先加富文字引擎。

DeepAgents 已存在於 Memory/backend/skills 接合，不是本轮新增依賴；不將它擴成 JD 持久試稿工作區。現有 service 是可沿用接點，但其舊三工具／Node／Plate／JSONB 行為須替換，不能把已驗框架當新 relational 功能已驗。

## 2. 現行官方能力與本案映射

| 官方來源／狀態 | 官方直接支持的能力 | 本案採用及限制 |
|---|---|---|
| [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)，現行 Responses guide，無固定頁版本 | 模型提出工具呼叫、App 執行並按 call_id 回結果；建議減少已知參數負擔、合併必然連續動作、啟用strict；strict所有property required，可空用null，各object禁額外欄 | 完整新增任務／有界整組更正，App注入scope/run/保存版本；顯式strict，不靠API預設正規化。文件、變更、來源refs由App發配，模型不算SQL欄位／行號。strict只約束形狀，不是已提交或語意正確證明 |
| [Anthropic strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)、[處理工具呼叫](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)，現行滾動文件 | 支援strict輸入schema；client tool由App執行，以tool_use_id回結果，可用is_error表達工具失敗 | 每個結果須帶實際保存狀態；參數錯誤與提交結果未知不同。不能將兩家JSON Schema支援範圍或例外格式假定完全相同，需用現裝adapter作離線fixture與後續核准的服務端驗證 |
| [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools)，OSS Python現行v1路線 | ToolRuntime隱藏於模型schema外，提供context/state/tool_call_id；ToolMessage／Command承接結果與狀態 | 沿原runtime/ports，不自寫第二個agent loop。document/run來自可信執行脈絡；thread_id與tool_call_id各有用途，不能混作業務operation或整輪撤回身分 |
| [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)，现行API | 原生依賴接點可共享邏輯及資源 | 現有api.py已組合JdService；HTTP與LLM adapter共用service／domain規則，不另加DI容器。Pydantic／Schema可驗輸入形狀、值及明示validators；DB交易、跨列關係與保存狀態仍由domain service／DB負責 |
| [React textarea](https://react.dev/reference/react-dom/components/textarea)，頁面目前v19.3 | 原生多行輸入、label、readOnly、選取事件；controlled value應同步更新，不可隨按鍵重建元件 | 保留DOM輸入，延遲的是保存，不是onChange。穩定item key、nullable呈現空字串、server晚回不覆蓋新輸入；中文組字與跨保存undo仍須真瀏覽器驗，不先聲稱全由React解決 |
| [PostgreSQL 16 constraints](https://www.postgresql.org/docs/16/ddl-constraints.html)，官方仍列受支援版本 | 複合PK/FK/UNIQUE、RESTRICT/CASCADE及NULL規則；跨列／跨表不能靠一般CHECK保證 | FK含document；junction去重；task／capability按owner分別刪除；線性parent UNIQUE。初始完整性、發布與receipt維持短交易，不增加通用event sourcing |
| [AWS hexagonal architecture](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)、[commands／handlers](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html)，現行Prescriptive Guidance | 輸入與基礎設施adapter可分離，業務邏輯可共用；額外adapter亦有維護成本 | 人工HTTP／AI工具可不同，D01／共享K/S／驗版本／交易效果共用。只採必要分層，不加雲端、微服務、訊息總線或動態CRUD引擎 |
| [MDN IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API/Using_IndexedDB)，現行標準非同步API | 本地object store／version upgrade／transaction，可處理錯誤與多分頁版本變動 | 承接既定單份恢復記錄，不能跨網路保持交易；容量、瀏覽器shutdown與記錄相容性須有限實驗。不是第二份正式JD或通用離線同步 |

OpenAI／Anthropic共有「模型意圖→App執行→配對結果」原則；AWS支持入口與業務邏輯分離。它們沒有共同規定本案十三表、命令數、autosave毫秒數或JD欄位。這些是依產品需要作的映射；不聲稱大廠內部亦如此保存。

## 3. 本地版本與免費開源界線

唯讀核對指定隔離checkout的[Web manifest](../../.worktrees/analysis-only-agent/experiments/jd-editor/web/package.json)、[Web授權清單](../../.worktrees/analysis-only-agent/experiments/jd-editor/web/license-inventory.json)、[Python manifest](../../.worktrees/analysis-only-agent/experiments/analysis-agent/pyproject.toml)、[Python lock](../../.worktrees/analysis-only-agent/experiments/analysis-agent/uv.lock)及其已安裝METADATA。下列是已有版本，不宣稱每個都是最新release，也不因此更換目前受測組合。

| 既有元件 | 精確版本／授權與限制 |
|---|---|
| Next／宣告React／DOM | 16.3.3／19.2.4／19.2.4；MIT。Next打包runtime另記19.3.0-canary-cbb046ab-20260731，不將其冒稱穩定19.2.4；採用時仍檢查實際執行層 |
| FastAPI／Pydantic | 0.141.1／2.13.5；MIT |
| LangChain／core | 1.4.0／1.6.2；MIT |
| LangGraph／checkpoint／checkpoint-postgres | 1.2.11／4.2.0／3.1.2；MIT |
| psycopg／binary | 3.3.5；LGPL-3.0-only，不能統称全部MIT |
| DeepAgents | 0.7.13；本輪確認已存在及既有用途，未選新增JD工作區；既有授權清單沿原Memory採用包核對 |

第三方文件是能力依據；OpenAI／Anthropic provider不是免費開源模型服務，真測仍有獨立費用範圍。現有套件可用不代表可無條件升級；正式固定版本仍查安全公告、棄用／migration及實際相容性，僅有具體原因才改版。

## 4. 必要自有程式與有限驗證

只補六類本案責任：完整JD命令及驗證、relational repository／mapper、同文件refs與選區核對、current＋revision＋receipt交易、人工變更與可信run接線、自動保存／未知結果／差異呈現。這些是業務程式，不是再製一個通用框架。

| 首要驗證 | 通過／停止條件 |
|---|---|
| generated schema＋兩家離線adapter | required／nullable／nested variants／hidden runtime／call結果配對一致；不支持則調整schema表示或有界adapter，保留完整業務效果及原子性。無法保留時記反例並重開該設計，不默默縮減能力或改成任意JSON／SQL |
| 原生文字／繁中／emoji／重複文字選區 | 同步DOM值、有效選區、A回覆不清B、組字與重開保留；單元測不能替代目標瀏覽器 |
| 真PG關係／原子發布 | 跨文件FK／重複link／分叉parent拒絕，第二步錯誤無部分發布，結果遺失查原receipt；不以新key補救未知 |
| runtime＋JD-only還原 | 同一顧問可持續改JD／Memory，各自結果可查；撤回只JD，原話與Memory不倒退，下一輪得知人工事件 |

DA-03恢復格式／容量／資料集身分與DA-04精確schema仍須完成；本稿不以選好框架代稱已接好LLM。下一工程單位沿[新版施工計畫RS-1](../plans/2026-09-13-jd-relational-app-implementation.md)，停止無差異廣搜。

## 5. 研究核對

root核OpenAI Functions、React、MDN及AWS／PG；`jd_command_semantics_review`唯讀核現裝manifest／lock／METADATA、api.py／jd_tools.py／runtime.py，以及Anthropic／LangChain／FastAPI官方正文。框架可承接既有邊界，未找到需要增加第二套agent框架或富文字核心的證據。本輪未修改這些來源程式或套件。

獨立文件審查首輪指出：FI-R01／P2「不支持就縮限variant」可能默默削減完整業務效果；FI-R02／P3「Pydantic只驗型別」描述過窄。已分別改為先調整表示／adapter、保留原子業務並在不能保留時重開，以及明確涵蓋值／validators能力。`jd_command_semantics_review`窄複核兩項均**DESIGN CLOSED**；其餘版本／授權、G4/G6、未實測界線及RS-2／RS-5依賴無finding。此為本稿與施工計畫的文件審查，不是RS-1或新產品已執行。
