# 技術選型與機制驗證

- 狀態：**供後續施工採用的工程選型／相容性待驗**，2026-09-29。不是已安裝版本清單或產品驗收。
- 邊界：目前基線是 PostgreSQL、LangGraph＋OpenAI direct Responses，不無故重選。依[Owner 的研究後實現調整授權](../plans/2026-09-29-target-rebuild/README.md#1-交付什麼刻意不做什麼)，可提出證據改採更合適機制並同步契約與測試；不能因此改掉已定產品概念、來源或恢復保證。其他選型依本機單體需求選擇，不以底稿使用什麼作理由。

## 1. 首選工具鏈

| 範圍 | 本次首選 | 理由、替代與限制 |
|---|---|---|
| Python 與套件 | CPython 3.14 系列、uv＋單一 API lock | 採目前穩定系列；T01 核對全相依與 Windows wheels 再鎖 patch。只有具體相容反例才改用仍受支援的 3.13 並記理由；不因系統已有 3.12 venv 就沿用它。[官方支援表](https://devguide.python.org/versions/) |
| API | FastAPI＋Pydantic 2＋Uvicorn | typed HTTP 邊界、依賴注入及模組 router；不再加第二套 Django／Node 業務後端。[官方模組化](https://fastapi.tiangolo.com/tutorial/bigger-applications/) |
| DB | PostgreSQL 18 受支援穩定 patch；SQLAlchemy 2＋psycopg 3；Alembic | 關聯式 JD、約束、短交易；ORM／Core 均可在 feature persistence 內使用，不建通用 DB 引擎。每個 async task 自己的 session，不共享 mutable AsyncSession。[SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks)、[PG 隔離](https://www.postgresql.org/docs/current/transaction-iso.html) |
| Graph | LangGraph Graph API＋官方 PostgreSQL checkpointer | 持久節點、私有子圖、恢復機制；不使用 LangChain Agent／Message adapter。框架傳遞相依中的 langchain-core 不等於本產品使用它管理對話。[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs) |
| 原件補存退避 | Tenacity（既有 lock 9.1.4，列為直接相依） | 僅調度仍持有原 R／C／count 的有限保存重試，不用來重送模型或業務操作；故障分類、次數及接線見[執行 §5.6](agent-execution.md#56-原件補存的有限自動恢復t06-第十六切片)。不建重試平台，不取代持久外送預算 |
| 模型 | `gpt-6-luna`；OpenAI 官方 Python SDK，直接 Async Responses | 2026-10-01 Owner 因成本明確決定產品使用 Luna，不採用 Sol 或自動 fallback；維持既有 high。保留原生 items；`store=false`、`all_turns` 與顯式 compact。不擅換模型／provider；重開選型須再確認。[官方接續](https://developers.openai.com/api/docs/guides/deployment-checklist#use-reasoningencrypted_content) |
| 推理設定 | A／B1／B2 共用既有 `ModelSettings`，預設 `high` | 2026-10-01 有限校準：同 payload 的局部更正來源選擇有改善，四輪真 App 旅程保存與來源回讀成立；不改模型、Prompt 或 Context，不新增角色切換器。較高推理額度可能增加輸出量／延遲；未作嚴格同批延遲比較，也不是每個角色品質都已證明改善。比較、限制及可回退範圍見 [T14 證據](../plans/2026-09-29-target-rebuild/evidence/t14-job-analysis-quality.md#2026-10-01來源保留的-reasoning-effort-對照)。既有執行保留已保存請求，設定變更不改寫歷史。 |
| 已結束的隔離模型對照 | 程式化 `ModelSettings(model="gpt-6.1-sol")` 僅為既有新合成檔案比較接縫，不是產品選型入口 | `adapters/openai_models.py` 統一兩個 runner 的已核對配置，沒有 UI／環境模型切換或自動 fallback。Owner 已選 Luna；不推進 Sol 採用、跨模型歷史相容功能或追加 Sol 外送。歷史原件保留，不能換模型續跑其 opaque reasoning；原 execution 保護不變。官規、結果與限制見 [T14 核心 App 對照](../plans/2026-09-29-target-rebuild/evidence/t14-job-analysis-quality.md#2026-10-01較高能力模型的核心-app-旅程對照)。 |
| 模型費用估算 | 版本化官方費率配置＋Decimal，接既有 executions budget | 不為單一 provider 引入代理平台或線上價格服務；輸入／cache read／write／輸出分算，未知不當零。公開費率配置、compact 推估與未驗帳單界線見[執行 §5.7](agent-execution.md#57-固定費率與-usage-成本估算t06-第十七切片) |
| Web | React＋TypeScript strict＋Vite；React Router 僅管理路由；TanStack Query 管 server state | 本機 SPA 無 SEO／SSR 需求；相比 Next.js 不引入第二套 server action／業務層。React 官方列出這些成熟選項，**不是聲稱官方首選所有專案用 SPA**。[React](https://react.dev/learn/build-a-react-app-from-scratch)、[Vite](https://vite.dev/guide/) |
| UI 元件 | MUI Core；原生受控欄位 | 使用既有表單、Dialog、鍵盤可操作元件，不從底層重造 widget；不選付費 Data Grid 或全文富文字編輯器，JD 是分欄編輯。[MUI](https://mui.com/material-ui/getting-started/) |
| 跨語言契約 | JSON Schema SSOT；datamodel-code-generator 產 Python，json-schema-to-typescript 產 TS；FastAPI 再產 OpenAPI | 兩個鎖定生成器讀同一 schema，不是兩份規格。前者不產 TS；型別生成也不代替執行時驗證。[Python 生成器](https://datamodel-code-generator.koxudaxi.dev/)、[TS 生成器](https://github.com/bcherny/json-schema-to-typescript)、[契約策略](../contract-strategy.md) |
| PDF | Python Playwright＋Chromium；受控 HTML／print CSS 模板 | 後端從正式 JD 投影，固定字型、禁止遠端資源與腳本；可用瀏覽器版面測試驗證。代價是 Chromium 體積與字型安裝；不把瀏覽器列印對話框當匯出完成。[官方 page.pdf](https://playwright.dev/python/docs/api/class-page#page-pdf) |
| 測試 | pytest＋HTTPX；真 PostgreSQL；Vitest＋Testing Library；Playwright Test | 單元／契約、資料競爭、UI 與完整旅程分層；fake Responses 先跑，不預設每次測試付費 |
| 靜態品質 | Ruff format／lint、mypy；TypeScript strict、ESLint＋Prettier | 統一工具化風格；Google 命名原則不代表需整套照搬其 lint 工具。生成碼用再生檢查，不手修 |

Node 用受支援 24 LTS 系列及相容 pnpm 穩定版，依[官方 release 狀態](https://nodejs.org/en/about/previous-releases)選 LTS，不以 Current／prerelease 優先。**本頁不捏造當日最新版 patch**；T01 將 registry、官方支援矩陣、license 與相容性結果寫入 lock／證據。同一任務不用因新 patch 發布無限重開；之後升版是獨立受測變更。

模型對照的限制：原 execution 的固定模型／計價保護，**不等於跨 execution 的歷史已具備模型相容性保護**。目前改用不同程式化設定啟動既有檔案，仍可能將已完成的舊模型 items 帶入新請求；因此上述對照只用新 schema／新檔案，不開放既有檔案切換。若後續採用新產品模型，須先處理這個實際接縫，而非以修改預設字串當完成。

T01 已發現 TS 7 超出 [typescript-eslint 支援範圍](https://typescript-eslint.io/users/dependency-versions/)，目前鎖 TS 6.0.3＋typescript-eslint 8.70.1 並以 strict peer 檢查；不保留自動加出的 release-age 排除項。OpenAI SDK 3.20.0 的 transport 使用 httpx2，與 FastAPI 測試的 HTTPX 分開；不以同名概念假定型別互換。Windows saver 的 Selector／PDF Proactor 接縫見[交付設計](interface-and-delivery.md#4-pdf-與程序)；具體通過／未驗範圍在 [T01 證據](../plans/2026-09-29-target-rebuild/evidence/t01-foundation.md)。

## 2. 有具體風險的機制，先驗再擴大

T02 保存切片已核對並採用 SQLAlchemy 2.1.1＋Alembic 1.20.0（Python 3.14／Windows），不是沿用 2.0 legacy 作新安裝。當前官方 [2.1 transaction](https://docs.sqlalchemy.org/en/21/orm/session_transaction.html)、[Alembic 命名](https://alembic.sqlalchemy.org/en/latest/naming.html)與實際接線見[訪談保存](interview-storage.md)；真 PostgreSQL 證據及已發現接縫在 [T02 evidence](../plans/2026-09-29-target-rebuild/evidence/t02-job-files-and-interviews.md)。不因此推導 Memory／JD 整體交易已驗收。

| Spike／承接任務 | 檢查與產物 | 不通過時 |
|---|---|---|
| T01 相容組合 | SDK 的 typed reasoning／compact／stream；LangGraph saver serializer；生成器支援 schemas；Windows＋Node／Python＋PG 啟動。留下實際版本及可重現命令 | 在同一已選框架內選受支援相容版；涉及撤換產品選型才提出問題 |
| T05 V4A | 優先核對官方公開 parser／helper 的鎖定原碼、license 與既有研究探針；唯一近似定位、多 hunk 原子性、越界命令拒絕 | 只補本契約缺少的匹配／原子保護；不能以 helper 可套 patch 宣稱已安全；不得默選第一處／最高分 |
| T06 原生接續 | 用真 SDK mock transport＋PG saver 往返原生項目；output→input 按 SDK 官方契約轉型，不任意裁欄。另備全合成的少量 provider preflight：依[有效授權與分批 manifest](../plans/2026-09-29-target-rebuild/README.md#3-狀態與施工順序)提前驗 native items、strict、compact 與 input token count，不必等所有 UI 完成 | 無法保留 opaque payload／順序就停止擴展 Graph；不改用文字摘要。授權不涵蓋的外送範圍仍須提問，離線工作可繼續 |
| T08／T12 持久接縫 | COMMIT 成功確認遺失、取消競爭、階段回復、晚到 writer；新程序恢復 | 修真正 owner，不新增第二套 receipt／event replay |
| T16 provider wire | 當次授權內驗 strict variants、多 call、all_turns、compact、模型限制及 usage | capability 不符明說，不偷偷改 API、模型、角色或來源範圍 |

V4A 的載體仍是既定 Memory 業務工具，不引入 filesystem tool 或全 repo patch 權限。官方 apply_patch 說明執行方處理 diff，沒有替本案保證唯一匹配。[OpenAI](https://developers.openai.com/api/docs/guides/tools-apply-patch)。優先重用語法解析；新增的有限安全政策必須有測例，不能自製通用模糊編輯框架。

T05 已選官方 MIT section parser 的受限抽取＋RapidFuzz 3.14.6（MIT）作文字相似度；不安裝 Agents SDK runner。所有合格位置共同計數、完整解析及原文保留由有限 adapter 負責。來源鎖定、政策／容量、替代取捨與未接通範圍見[正文編輯接線](memory-body-editing.md)，不是原 helper 自帶的保證。

## 3. 運作參數不是無限值，也不是已核准費用

已確認 A 輪前 128,000、A／B1／B2 中途 272,000；時間點及回退依[執行契約 §6.3](../specs/2026-09-27-shared-agent-execution-and-state-design.md#63-輪前主動壓縮與-272k-中途保險目標已確認未實作)。以下只作 **T16 校準起始設定**，不升格 Owner 決策，不直接用於無授權外送：

| 待校準設定 | 測試初值與精確計算 |
|---|---|
| B1／B2 輪前壓縮 | 各 512,000 tokens；先證明模型與 compact 可容納；若模型限制更小，不盲送，先報此初值不可用 |
| 模型迭代上限 | A 每 Turn 128；B1、B2 各每批 256；每次新的 create 算一次，回交不重置 |
| 傳輸重試 | 同一請求最多 5 次外送，含首次；create／compact 都計；SDK 關閉隱含 retry，Runtime 單一責任退避 |
| 工具修正 | 同目標、同錯誤連續最多 5 次；語意修正是新模型迭代／新操作，仍受工作總預算約束 |
| 整體限制 | 每工作總外送數、時間、金額與單請求 timeout 必須明配；未配置不啟動付費。測試 manifest 額度可更低，取最嚴者 |

一次回應多個 call 依原順序執行，不把 call 數誤當模型迭代數。API 逾時不等於未計費；所有 attempts 與 compact 共用工作費用資格。校準輸出用品質、錯誤率、請求／工具次數、token、延遲及費用比較，不單憑「更高上限比較好」。此階段不選 retry platform／額度管理產品。

## 4. 明確不採用

首版不引入微服務、Redis／Kafka／Celery、向量搜尋、Git／event-sourcing 版本框架、通用 rule engine、第二套 LangChain／Agents SDK loop、全域前端 Redux 狀態、每層一個 package、LLM 直寫 SQL。沒有實際反例及效益證據，不為未來新增它們。

選型變更記錄「原需求、比較、採用理由、測試及退出影響」。若只是相容 patch 或內部組織調整，可由工程代理完成；若改成資料外送、雲端服務、來源權責或不同產品效果，按原決策流程裁決。
