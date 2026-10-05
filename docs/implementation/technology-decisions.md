# 技術選型與機制驗證

- 狀態：**現行技術選型與驗證依據** 。實際安裝版本由 lockfile 管理；本頁保留選型理由、相容性與後續調整條件，歷次驗證見[結案證據](../history.md#source-8e6fa902e6e1928b1f59)。
- 邊界：基線為 PostgreSQL、LangGraph＋OpenAI direct Responses。機制調整須有具體證據並同步契約與測試；涉及產品效果、來源權責或恢復保證的變更依[決策流程](../decision-process.md)處理，不由歷史施工授權推定。

## 1. 首選工具鏈

| 範圍 | 現行選型 | 理由、替代與限制 |
|---|---|---|
| Python 與套件 | CPython 3.14 系列、uv＋單一 API lock | 版本限制與鎖定值由 `apps/api/pyproject.toml`、`uv.lock` 維護；升級須核對相依及 Windows wheels。[官方支援表](https://devguide.python.org/versions/) |
| API | FastAPI＋Pydantic 2＋Uvicorn | typed HTTP 邊界、依賴注入及模組 router；不再加第二套 Django／Node 業務後端。[官方模組化](https://fastapi.tiangolo.com/tutorial/bigger-applications/) |
| DB | PostgreSQL 18 受支援穩定 patch；SQLAlchemy 2＋psycopg 3；Alembic | 關聯式 JD、約束、短交易；ORM／Core 均可在 feature persistence 內使用，不建通用 DB 引擎。每個 async task 自己的 session，不共享 mutable AsyncSession。[SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks)、[PG 隔離](https://www.postgresql.org/docs/current/transaction-iso.html) |
| Graph | LangGraph Graph API＋官方 PostgreSQL checkpointer | 持久節點、私有子圖、恢復機制；不使用 LangChain Agent／Message adapter。框架傳遞相依中的 langchain-core 不等於本產品使用它管理對話。[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs) |
| 原件補存退避 | Tenacity（直接相依，鎖定 9.1.4） | 僅調度仍持有原 R／C／count 的有限保存重試，不用來重送模型或業務操作；故障分類、次數及接線見[執行 §5.6](agent-execution.md#56-原件補存的有限自動恢復)。不建重試平台，不取代持久外送預算 |
| 模型 | `gpt-6-luna`；OpenAI 官方 Python SDK，直接 Async Responses | 產品使用 Luna／high，不採用 Sol 或自動 fallback。保留原生 items；`store=false`、`all_turns` 與顯式 compact。不擅換模型／provider；重開選型須再確認。[官方接續](https://developers.openai.com/api/docs/guides/deployment-checklist#use-reasoningencrypted_content) |
| 推理設定 | A／B1／B2 共用 `ModelSettings`，預設 `high` | 較高推理額度可能增加輸出量／延遲；尚無嚴格同批延遲比較，也未證明各角色品質皆改善。既有執行使用已保存請求，設定變更不改寫歷史。驗證見[品質與設定對照](../history.md#source-d3293e9b28c75bbb6616)。 |

| 模型費用估算 | 版本化官方費率配置＋Decimal，接既有 executions budget | 不為單一 provider 引入代理平台或線上價格服務；輸入／cache read／write／輸出分算，未知不當零。公開費率配置、compact 推估與未驗帳單界線見[執行 §5.7](agent-execution.md#57-固定費率與-usage-成本估算) |
| Web | React＋TypeScript strict＋Vite；React Router 僅管理路由；TanStack Query 管 server state | 本機 SPA 無 SEO／SSR 需求；相比 Next.js 不引入第二套 server action／業務層。React 官方列出這些成熟選項，**不是聲稱官方首選所有專案用 SPA** 。[React](https://react.dev/learn/build-a-react-app-from-scratch)、[Vite](https://vite.dev/guide/) |
| UI 元件 | MUI Core；原生受控欄位 | 使用既有表單、Dialog、鍵盤可操作元件，不從底層重造 widget；不選付費 Data Grid 或全文富文字編輯器，JD 是分欄編輯。[MUI](https://mui.com/material-ui/getting-started/) |
| 跨語言契約 | JSON Schema SSOT；datamodel-code-generator 產 Python，json-schema-to-typescript 產 TS；FastAPI 再產 OpenAPI | 兩個鎖定生成器讀同一 schema，不是兩份規格。前者不產 TS；型別生成也不代替執行時驗證。[Python 生成器](https://datamodel-code-generator.koxudaxi.dev/)、[TS 生成器](https://github.com/bcherny/json-schema-to-typescript)、[契約策略](../contract-strategy.md) |
| PDF | Python Playwright＋Chromium；受控 HTML／print CSS 模板 | 後端從正式 JD 投影，固定字型、禁止遠端資源與腳本；可用瀏覽器版面測試驗證。代價是 Chromium 體積與字型安裝；不把瀏覽器列印對話框當匯出完成。[官方 page.pdf](https://playwright.dev/python/docs/api/class-page#page-pdf) |
| 測試 | pytest＋HTTPX；真 PostgreSQL；Vitest＋Testing Library；Playwright Test | 單元／契約、資料競爭、UI 與完整旅程分層；fake Responses 先跑，不預設每次測試付費 |
| 靜態品質 | Ruff format／lint、mypy；TypeScript strict、ESLint＋Prettier | 統一工具化風格；Google 命名原則不代表需整套照搬其 lint 工具。生成碼用再生檢查，不手修 |

Node 使用 24 LTS 系列及相容 pnpm；版本依 repo 配置與 lockfile，不以當日最新版或 prerelease 為產品要求。[官方 release 狀態](https://nodejs.org/en/about/previous-releases)提供支援週期依據，升版仍是獨立受測變更。

**模型相容限制：** 原 execution 的固定模型／計價保護，不等於跨 execution 的歷史已具備模型相容性保護。程式化改用不同設定啟動既有檔案，仍可能帶入舊模型 items；產品沒有 UI／環境模型切換或自動 fallback。`adapters/openai_models.py` 中的比較模型配置不是產品選型入口；若日後採用新模型，須先處理歷史相容性，不能只改預設字串。驗證見[隔離模型對照](../history.md#source-d3293e9b28c75bbb6616)。

工具鏈鎖定 TypeScript 6.0.3＋typescript-eslint 8.70.1，升級時須核對[相容範圍](https://typescript-eslint.io/users/dependency-versions/)並保留 strict peer 檢查。OpenAI SDK 3.20.0 的 transport 使用 httpx2，與 FastAPI 測試的 HTTPX 分開，不假定型別互換。Windows saver 的 Selector／PDF Proactor 執行邊界見[交付設計](interface-and-delivery.md#4-pdf-與程序)。驗證見[工具鏈](../history.md#source-9fa61edd21bd247e656d)。

## 2. 有具體風險的機制，先驗再擴大

資料保存使用 SQLAlchemy 2.1.1＋Alembic 1.20.0。交易與遷移命名依 [SQLAlchemy transaction](https://docs.sqlalchemy.org/en/21/orm/session_transaction.html)、[Alembic 命名](https://alembic.sqlalchemy.org/en/latest/naming.html)；接線見[訪談保存](interview-storage.md)，驗證見[保存驗證](../history.md#source-2a993efd60b1a85e23d6)。

| 變更風險 | 檢查與產物 | 不通過時 |
|---|---|---|
| 工具鏈相容 | SDK 的 typed reasoning／compact／stream；LangGraph saver serializer；生成器支援 schemas；Windows＋Node／Python＋PG 啟動。留下實際版本及可重現命令 | 在同一已選框架內選受支援相容版；涉及撤換產品選型才提出問題 |
| V4A 編輯 | 優先核對官方公開 parser／helper 的鎖定原碼、license 與既有研究探針；唯一近似定位、多 hunk 原子性、越界命令拒絕 | 只補本契約缺少的匹配／原子保護；不能以 helper 可套 patch 宣稱已安全；不得默選第一處／最高分 |
| 原生接續 | 真 SDK mock transport＋PG saver 往返原生項目；output→input 按契約轉型。必要時依當次有效授權以少量合成資料驗 provider 的 native items、strict、compact 與 token count | 無法保留 opaque payload／順序就停止擴展，不改用文字摘要；授權外的外送須確認，離線工作可繼續 |
| 持久接縫 | COMMIT 成功確認遺失、取消競爭、階段回復、晚到 writer；新程序恢復 | 修正實際負責保存或恢復的模組，不新增第二套 receipt／event replay |
| Provider wire | 當次授權內驗 strict variants、多 call、all_turns、compact、模型限制及 usage | capability 不符明說，不偷偷改 API、模型、角色或來源範圍 |

V4A 的載體仍是既定 Memory 業務工具，不引入 filesystem tool 或全 repo patch 權限。官方 apply_patch 說明執行方處理 diff，沒有替本案保證唯一匹配。[OpenAI](https://developers.openai.com/api/docs/guides/tools-apply-patch)。優先重用語法解析；新增的有限安全政策必須有測例，不能自製通用模糊編輯框架。

V4A 使用官方 MIT section parser 的受限抽取＋RapidFuzz 3.14.6（MIT）作文字相似度；不安裝 Agents SDK runner。所有合格位置共同計數、完整解析及原文保留由有限 adapter 負責。來源鎖定、政策／容量、替代取捨與驗證界線見[正文編輯接線](memory-body-editing.md)，不是原 helper 自帶的保證。

## 3. 運作參數不是無限值，也不是已核准費用

A／B1／B2 輪前門檻為 **128,000** tokens，中途完整 Step 交界為 **160,000** ；時點與回退依[執行契約 §6.3](../specs/2026-09-27-shared-agent-execution-and-state-design.md#63-輪前主動壓縮與中途保險)。這是產品留量政策，不是模型 context 上限或避免所有 429 的保證。下列為現行程式預設；在途工作沿已固定的 request／budget，不能由設定變更重置：

| 設定 | 現行預設與計算責任 |
|---|---|
| 模型迭代上限 | `ModelSettings.max_model_steps=64`；A 以 Turn、B1／B2 以共用 Memory execution 計量。各角色 loop 另受同值限制；交接不重置批次用量。一次新 logical create 算一個模型步數，多個工具 call 不另算模型步數 |
| 傳輸重試 | 每請求非限流 attempts 最多 8 次，含首次；限流等待另分類，仍受總外送數與 deadline 約束。SDK 隱含 retry 關閉，Runtime 單一責任退避 |
| 工具與壓縮 | 每 Step 最多 32 個工具 call；每工作最多 4 次 logical compaction。模型修正參數是新模型迭代／新操作，沿原工作總限制 |
| 整體限制 | 每工作總外送 512 次、時限 1,800 秒、單請求 timeout 120 秒、輸出上限 16,384 tokens。產品 `max_cost_usd=None`；付費評測可明確啟用較低金額上限，不能當成產品限制 |

數值來源為 [ModelSettings](../../apps/api/src/caliburn/settings.py)、[共用 runtime](../../apps/api/src/caliburn/workflows/model_runtime.py)、[重試政策](../../apps/api/src/caliburn/agent_execution/response_retries.py)與角色 runner。API 逾時不等於未計費；create／count／compact 的 attempts 共用工作外送紀錄。品質、錯誤率、token、延遲及費用分別觀察，不把更高上限當作更佳效果。驗證見[執行接線](agent-execution.md)與[容量驗證](../history.md#source-6d2d7ab4abfedbf8416e)。

## 4. 明確不採用

首版不引入微服務、Redis／Kafka／Celery、向量搜尋、Git／event-sourcing 版本框架、通用 rule engine、第二套 LangChain／Agents SDK loop、全域前端 Redux 狀態、每層一個 package、LLM 直寫 SQL。沒有實際反例及效益證據，不為未來新增它們。

選型變更記錄「原需求、比較、採用理由、測試及退出影響」。若只是相容 patch 或內部組織調整，可由工程代理完成；若改成資料外送、雲端服務、來源權責或不同產品效果，按原決策流程裁決。
