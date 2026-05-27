# 系統架構總覽

## 技術棧

| 層 | 技術 |
|----|------|
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI (Python 3.11+), asyncio |
| AI / Graph | LangGraph (StateGraph), LangChain, OpenAI GPT-4o |
| Embeddings | OpenAI `text-embedding-3-small` (1536 維) |
| Database | PostgreSQL + pgvector 擴充套件 |
| ORM | SQLAlchemy 2.x async (asyncpg driver) |
| 同步 DB | psycopg2（僅供 ingest script 使用） |
| iCAP Chunk | llama-index `TextNode`（僅作資料容器，未使用 LlamaIndex pipeline） |

## 目錄結構

```
jobintel-ai/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app、CORS、lifespan
│   │   ├── config.py             # Settings（.env）含 icap_high/medium_threshold
│   │   ├── database.py           # async engine / session
│   │   ├── logging_config.py     # setup_logging()：structlog 格式、第三方套件降噪
│   │   ├── models/               # SQLAlchemy ORM models
│   │   │   └── job_profile.py    # User / JobProfile / InterviewSession / KsaItem / DocumentVersion
│   │   ├── schemas/              # Pydantic I/O schemas
│   │   │   ├── job_profile.py    # UserOut / JobProfileOut / InterviewMessageIn ...
│   │   │   └── ocs.py            # OcsDocument 完整 Pydantic 模型（含 EvidenceRef / EnrichedExportJson）
│   │   ├── api/routes/           # FastAPI routers
│   │   │   ├── users.py          # POST/GET /users
│   │   │   ├── job_profiles.py   # CRUD /job-profiles + GET /{id}/state
│   │   │   ├── interviews.py     # POST /interviews/{id}/chat (SSE 串流)
│   │   │   ├── tasks.py          # GET/PATCH /tasks
│   │   │   └── documents.py      # GET /preview、POST /freeze、POST /export
│   │   ├── graph/
│   │   │   ├── state.py          # InterviewState TypedDict
│   │   │   ├── graph.py          # build_interview_graph() + 條件邊路由函式
│   │   │   ├── llm.py            # get_chat_llm() factory（支援 openai/google/anthropic）/ get_embeddings()
│   │   │   ├── llm_gateway.py    # LLMGateway：invoke_text / invoke_json（含 retry）
│   │   │   ├── phase.py          # Phase dataclass：star/five_w2h/general，to_str/from_str
│   │   │   ├── task_loop.py      # TaskLoopManager：current_task / advance / skip_completed
│   │   │   ├── constants.py      # FIVE_W2H_REQUIRED / INDICATOR_REQUIRED_FIELDS / LIST_FIELDS
│   │   │   ├── interview_readiness.py  # compute_readiness()，6 信號加權評分
│   │   │   ├── prompts/          # 節點 Prompt 模板（集中管理，避免散落各 node）
│   │   │   │   ├── interview.py  # SYSTEM / TARGETED / READY
│   │   │   │   ├── star.py       # SLOT_EXTRACT / SLOT_SYNTHESIZE
│   │   │   │   └── indicator.py  # PER_OUTPUT / SINGLE
│   │   │   └── nodes/            # 8 個 LangGraph 節點
│   │   │       ├── icap_rag.py         # iCAP 職能基準 RAG（候選職種信心判斷）
│   │   │       ├── interview.py        # 自然訪談（含兩段式 readiness 確認）
│   │   │       ├── task_extraction.py  # 任務萃取 + task_id 分配 + task RAG 注入
│   │   │       ├── responsibility_grouping.py # 主要職責分組 + 使用者確認
│   │   │       ├── star.py             # STAR slot filling（4 槽 + synthesis fallback）
│   │   │       ├── five_w2h.py         # 5W2H 補洞（9 欄 + iCAP 參考提示泡泡）
│   │   │       ├── indicator.py        # per-output 行為指標生成 + 品質評分
│   │   │       └── ocs_builder.py      # OCS 文件生成 + K/S/A RAG 對應 + display_labels
│   │   ├── services/
│   │   │   ├── state_service.py      # StateService：build_initial_state / extract_persistent / persist
│   │   │   ├── interview_orchestrator.py  # InterviewOrchestrator：stream()，SSE + 圖執行 + 持久化
│   │   │   ├── document_service.py   # generate_docx / generate_pdf / generate_xlsx
│   │   │   │                         # get_enriched_export_json（含 evidence_refs / icap_reference_pack）
│   │   │   ├── icap_matcher.py        # iCAP 候選職種信心判斷與推薦文字
│   │   │   └── icap_retriever.py       # 6 種 RAG 函式：search_knowledge/skills/attitudes/tasks/indicators/outputs
│   │   └── utils.py                  # safe_parse_json
│   └── scripts/
│       ├── icap_parser.py        # iCAP JSON → TextNode chunks（9 種 chunk_type）
│       ├── icap_ingest.py        # 批次 embed + upsert to DB（含 --resume / --dry-run）
│       ├── test_full_interview.py
│       ├── test_ocs_api.py
│       └── test_ocs_export.py
└── frontend/
    └── src/
        ├── app/
        │   ├── dashboard/page.tsx              # 職務列表（草稿/訪談中/已預覽/已匯出）
        │   ├── profiles/new/page.tsx           # 新增職務表單
        │   ├── profiles/[id]/page.tsx          # 訪談頁（聊天介面 + TaskPanel）
        │   └── profiles/[id]/preview/page.tsx  # 預覽 + 凍結 + 匯出
        ├── components/
        │   ├── interview/
        │   │   ├── ChatBubble.tsx
        │   │   ├── IcapBadges.tsx
        │   │   ├── ProgressTracker.tsx
        │   │   └── TaskPanel.tsx       # StagePill（STAR/5W2H/指標三階段完整度顯示）
        │   ├── preview/
        │   │   ├── SourceBadge.tsx     # [訪談確認]/[AI整理]/[iCAP參考]/[待確認]
        │   │   ├── BehaviorIndicatorCard.tsx
        │   │   ├── EvidenceRefs.tsx
        │   │   ├── QualityBadge.tsx
        │   │   └── KsaSection.tsx
        │   └── ui/                     # shadcn/ui 元件
        ├── lib/
        │   └── api.ts              # getProfileState / getDocumentPreview / freezeDocument
        └── hooks/
            ├── useInterview.ts     # SSE 串流 hook
            └── useProfiles.ts      # SWR profile 查詢
```

## 系統資料流

```
使用者瀏覽器
    │
    │ POST /api/v1/interviews/{id}/chat  (body: { content, phase })
    │ ← text/event-stream (SSE)
    ▼
FastAPI  interviews.py  ← 只負責 HTTP 層（驗證、存 user 訊息、回 StreamingResponse）
    │
    ▼
InterviewOrchestrator.stream()  ← 載入歷史、組裝 InterviewState、驅動 graph、持久化
    │  StateService.build_initial_state()  ← 從 profile.graph_state 恢復 18 個持久欄位
    ▼
LangGraph get_interview_graph()  ← lru_cache，compile 一次共用
    │  entry_router 依 current_stage 跳入對應節點
    │  節點輸出 ai_response 或 ai_messages，逐則 yield 給前端
    │  多節點可在同一 API call 內串接（star→five_w2h→indicator→star 逐任務迴圈）
    ▼
各 Graph Node（8 節點）
    │  呼叫 LLMGateway.invoke_text / invoke_json（含 retry）
    │  Phase.star/five_w2h(task_id).to_str() 生成 phase key
    │  TaskLoopManager 管理任務推進與 skip_completed 邏輯
    │  icap_matcher：多粒度候選排序；icap_retriever：6 種 pgvector 查詢函式
    │  完成後 accumulated state 存回 DB
    ▼
PostgreSQL  jobintel DB
    icap_embeddings      ← pgvector 向量表（9 種 chunk_type）
    job_profiles         ← stage + graph_state JSONB（跨 call 持久化 18 個 key）
    interview_sessions   ← 完整對話歷史（含 phase 欄位）
    document_versions    ← 凍結版本（freeze 後建立）
```

## 環境變數（.env）

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `DATABASE_URL` | asyncpg 連線字串 | `postgresql+asyncpg://postgres:password@localhost:5432/jobintel` |
| `DATABASE_URL_SYNC` | psycopg2 連線字串（ingest script） | 同上但不含 `+asyncpg` |
| `LLM_PROVIDER` | Chat LLM provider 選擇：`openai` / `google` / `anthropic` | `openai` |
| `OPENAI_API_KEY` | OpenAI API 金鑰 | — |
| `OPENAI_MODEL` | OpenAI Chat 模型 | `gpt-4o` |
| `OPENAI_EMBEDDING_MODEL` | Embedding 模型（固定 OpenAI，不隨 provider 切換） | `text-embedding-3-small` |
| `GOOGLE_API_KEY` | Google Gemini API 金鑰（`LLM_PROVIDER=google` 時必填） | — |
| `GOOGLE_MODEL` | Gemini Chat 模型 | `gemini-2.5-flash` |
| `ANTHROPIC_API_KEY` | Anthropic API 金鑰（`LLM_PROVIDER=anthropic` 時必填） | — |
| `ANTHROPIC_MODEL` | Claude Chat 模型 | `claude-sonnet-4-6` |
| `ICAP_HIGH_THRESHOLD` | iCAP 高信心門檻（≥ → reference mode） | `0.70` |
| `ICAP_MEDIUM_THRESHOLD` | iCAP 中信心門檻（≥ → hybrid mode；< → company_defined） | `0.55` |
| `ICAP_TOP_K` | iCAP RAG 返回候選數 | `5` |
| `DOCUMENT_OUTPUT_DIR` | 匯出檔案目錄 | `./output/documents` |
| `FONT_PATH` | PDF 中文字型路徑（跨平台） | `assets/fonts/NotoSansTC-Regular.ttf` |

> `ICAP_HIGH_THRESHOLD` / `ICAP_MEDIUM_THRESHOLD` 取代舊版單一 `ICAP_SIMILARITY_THRESHOLD`，支援三段式信心判斷。
> Embedding 固定使用 OpenAI `text-embedding-3-small`，不隨 `LLM_PROVIDER` 切換；向量資料庫已有資料時切換 provider 無需重新 ingest。

## 持久化狀態（`StateService.PERSISTENT_KEYS`）

以下 18 個欄位由 `StateService` 統一管理，在每次 API call 結束後存回 `job_profiles.graph_state` JSONB：

```
extracted_tasks, responsibility_groups, responsibility_grouping_round,
current_task_index, task_extraction_round, missing_fields,
star_slots_by_task, star_completed_task_ids,
behavior_indicators, indicator_retry_counts,
ksa_items, ocs_document,
icap_candidates, icap_hit, icap_mode,
interview_readiness_detail, interview_ready, interview_ready_confirmed
```

| 方法 | 說明 |
|------|------|
| `StateService.build_initial_state(profile, phase, user_input, history)` | 從 `profile.graph_state` 恢復全部 18 個欄位，組裝完整 `InterviewState` |
| `StateService.extract_persistent(accumulated)` | 從 graph 執行後的 accumulated dict 取出 18 個持久欄位 |
| `StateService.persist(db, profile_id, stage, state)` | 更新 DB 中的 `stage` 與 `graph_state` |

> AI 訊息的 `phase` 欄位以 `accumulated.get("phase", message.phase)` 寫入 DB，確保節點輸出的 phase（`"star_task_001"` 等）正確持久化，供下次呼叫的訊息過濾使用。

---

## Docker Compose

`docker-compose.yml` 包含三個服務，可一鍵啟動開發環境的基礎設施（DB + Redis + Backend API）。

### 服務總覽

| 服務 | Image | 容器名稱 | Port |
|------|-------|----------|------|
| `db` | `pgvector/pgvector:pg16` | `jobintel_db` | 5432 |
| `redis` | `redis:7-alpine` | `jobintel_redis` | 6379 |
| `api` | Build from `backend/Dockerfile` | `jobintel_api` | 8000 |

> Frontend（Next.js）**不在** docker-compose 內，需另外以 `npm run dev` 啟動。

### 啟動方式

```bash
# 建立 backend/.env（複製範本後填入金鑰）
cp backend/.env.example backend/.env

# 啟動全部服務（DB → Redis → API，依 healthcheck 順序）
docker compose up -d

# 查看 API 日誌
docker compose logs -f api

# 關閉並保留資料
docker compose down

# 關閉並清除 DB volume（重置資料庫）
docker compose down -v
```

### 初始化細節

- **PostgreSQL**：啟動時自動執行 `backend/migrations/init.sql`（建表 + pgvector extension）
- **API**：等待 `db` 與 `redis` 通過 healthcheck 後才啟動，避免連線失敗
- **Hot reload**：API 容器掛載 `./backend:/app`，修改程式碼後自動重啟（`--reload`）
- **資料持久化**：DB 資料存於 Docker volume `pgdata`，`docker compose down` 不會刪除

### 環境變數注入

`api` 服務透過 `env_file: ./backend/.env` 載入設定，Docker Compose 內的 DB/Redis 連線位址需改為服務名稱：

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/jobintel
DATABASE_URL_SYNC=postgresql://postgres:password@db:5432/jobintel
REDIS_URL=redis://redis:6379/0
```

> 本機直跑（`uvicorn`）時則用 `localhost`；Docker 環境用服務名 `db` / `redis`。

---

## 已知問題與改善方向

> **P0 / 第一〜四階段已於 2026-05-20 全部完成。** 以下保留改善方向供規劃參考。

### graph_state 不應是唯一真相（第六階段規劃）

**現況**：跨 API call 的狀態全部儲存在 `job_profiles.graph_state` JSONB，不支援任務級分析、版本控制、稽核追溯。

**目標**：graph_state 作為 runtime cache，核心物件逐步拆成正規表：

| 資料物件 | 建議表 | 目的 |
|---------|--------|------|
| 原始對話 | `interview_sessions`（已有） | 保存 AI / 工作者原話 |
| 結構化任務 | `company_tasks`（已有） | 5W2H 欄位 |
| 證據關聯 | `task_evidence_refs` | 任務/指標對應到原始回答（現已存 OCS JSON） |
| 行為指標 | `task_indicators` | 5W2H / ABCD + quality_score（現已存 behavior_indicators） |
| iCAP 對應 | `task_icap_mappings` | task-level mapping + confidence |
| 文件版本 | `document_versions`（已有） | frozen content |
| Graph 執行 | `graph_runs` | 每次 AI 流程執行紀錄與錯誤（第五階段 #20） |
| iCAP 主資料 | `icap_standards` | 版本管理（第六階段 #23） |

### embedding model 版本記錄（第六階段 #24）

**現況**：`text-embedding-3-small` 版本未記錄於 DB，若 OpenAI 更新模型，舊向量與新向量不可比較。

**目標**：`icap_embeddings` 加入 `embedding_model` 欄位，re-ingest 時記錄模型版本。

### Graph execution lock（第五階段 #19）

**現況**：前端連點或 SSE 重連可能觸發同一 profile 兩次 AI 流程，造成狀態競爭。

**目標**：DB 或 Redis 層加入 per-profile 執行鎖，確保同時只有一個 graph 在跑。
