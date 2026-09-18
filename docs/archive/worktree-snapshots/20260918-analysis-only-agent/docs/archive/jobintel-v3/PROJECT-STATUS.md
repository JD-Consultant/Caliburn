# jobintel-ai v3 — 跨 session 狀態快照

> **這是什麼**：給「在 `s:\jobintel-ai` 開的新 session」快速接上脈絡。**本地、untracked、不 commit。**
> **最後更新：2026-06-23**（D29 表頭 metadata 全鏈完成＋真資料 live 驗證；待瀏覽器驗收）。
> **D29（indexer profile 端點 + 表頭自動填）已完成**：I1 indexer `GET /profile/{ocs_code}`（commits `9bf52ac`+修正 `cb17573`）、V1 v3 `/job-profiles/{id}/header-meta` 聚合（`df99247`+修正 `2210e4e`）、V2 前端 `HeaderMetaPanel`（〔表頭分類〕多選所屬類別+主基準切換，`1d6d629`）。**重大修正**：`category.job_categories` 是多值 {code,name}（非單值），normalizer 原本丟了 name → 已補；**已完整 re-ingest**（908 檔/9502 點）並重啟 indexer，`/profile` 真資料回正確多值 job_categories。decision-log「D29」。後端 indexer 50 / v3 141 passed。
> **D27 已完成**：文件即工作台（後端 REST + 前端工作台 + 選職類/選任務 curate + @dnd-kit + 官方表頭 + JSON 匯出 + e2e 驗收 + bug log）。commits 到 `cc95bb7`/`1ae0149`；docs 見 `specs/2026-06-21-*`、decision-log D27。
> **D28（LLM agent）已實作 T0–T12**（commits `5101960`→`630e538`；decision-log「D28 實作完成」）：後端 catalog UUID 串接 + `/ai/*` 5 端點（recommend-ks/draft-op/extract-tasks/structure-task/clarify，**薄 adapter+純函式 §I 可重用**）+ `_notes` 工作筆記欄/export 剝除；前端 api+型別、✨「AI 填寫」面板（核心入口，5W2H→draft-op+recommend-ks→暫存→套用 PATCH）、次要任務「帶 catalog」一鍵、〔選任務〕AI 預勾+CIT 補漏自訂、intake 小訪談頁。**後端 134 passed（FakeLlm、免 key）；前端 tsc+eslint 乾淨。** MVP＝甲（結構化直接 fetch、不碰 CopilotKit；聊天 Phase 2）。
> **T13 eval-gate ✅（2026-06-23，真模型 DeepSeek V3）**：`OPENROUTER_API_KEY` 設於 gitignored `backend/.env`；模型＝`deepseek/deepseek-chat`（cheap 三層共用，使用者選）。smoke `docs/superpowers/_t13_smoke.py`（untracked）建真情境(profile→職類→任務含 provenance UUID)打 5 端點 **12/12 綠**：catalog 優先 + AI 個人化(source=ai) + grounding(catalog 項有 code) + source 標記皆如設計。
> **下一步 = T13 瀏覽器驗收（人工）**：4 服務全開（DB / `run_live.py`:8001 / indexer:8000 / `npm run dev`:3000）走完整員工流程（小訪談→盤點→✨深填→次要一鍵→A→80 分→顧問精修）。§I 預留未來「AI 自主深度訪談」（獨立編排層疊在現有純函式上）。
> **已知**：indexer profile 搜尋相關性偏弱（「人力資源管理」→「農業人力資源管理師」），別 repo 範疇。
> **權威來源**（衝突以這些為準）：`specs/2026-06-16-refactor-decision-log.md`（D1–D26 全決策）、`specs/2026-06-16-jobintel-ai-v3-architecture.md`（架構，部分段落已被 D24/D25 取代見其內註記）、最新兩份 design：`specs/2026-06-18-ksa-flow-redesign-design.md`(D24)、`specs/2026-06-18-db-document-centric-design.md`(D25)。

---

## 專案

`s:\jobintel-ai`。把「從對話推論」的 JD 顧問重構為「**catalog 取出 + 人 curate + 每任務深問 → 產出 OCS 職務說明書**」的 agent，消費 **jd-ocs-indexer**（另一 repo `S:\jd-ocs-indexer`）的 query API。**v3 已合併進 `master`**（feat/v3 == master == `c816f86`，本機；尚未 push origin）。

## 棧（現況）

LangGraph（控制流 + `interrupt()`/`Command` HITL + **AsyncPostgresSaver** checkpointer）+ **ag-ui-langgraph / AG-UI**（取代舊 copilotkit remote-endpoint，D22）+ **CopilotKit v2**（`@copilotkit/react-core/v2`，headless：`useAgent` + `useInterrupt(renderInChat:false)`）+ Postgres（**Alembic** 管 schema，無 pgvector）+ OpenRouter（per-node 分層，沒金鑰則 `llm=None` 優雅降級）。Next.js 16 + React 19。

## 現在的使用者流程（D24 後）

```
dashboard 新增職務 → /v3/[id] 開始
① pick_profile     : search() → 複選 OCS（順序=優先度）
② build_task_pool  : task_pool() → 可編輯任務審閱面（勾/改/增/刪）
③ 逐任務深問迴圈   : star → five_w2h → indicator（每問 interrupt；單層 node loop）
④ curate_ks        : 全部訪談完後，逐任務 K/S 審閱面（候選來自 pairs() 職類池，預設不勾）
⑤ curate_attitudes : 全域 A 審閱面
⑥ build_doc        : REVIEW 唯讀預覽 → 存 document_versions（整份 OCS 文件 JSONB）
```
所有 HITL = `interrupt()`；前端 v2 `useInterrupt` 各 kind 渲染自製審閱面（`InterruptHandlers.tsx`）。

## 資料模型（D25 文件導向）

- **業務表只剩 3 張**：`users` / `job_profiles`(含 `selected_ocs_codes TEXT[]`) / `document_versions`(content JSONB, status)。
- **of-record = `document_versions.content` JSONB**（整份文件）；任務/KSA/深問細節**全在 LangGraph checkpointer**（`checkpoints*` 表，AsyncPostgresSaver 自管）。
- persistence 只剩 `ProfileRepo.set_selected_ocs(codes)` + `DocRepo.save_document`（D25 砍掉 TaskRepo/KsaRepo/flush_*；翻轉 D6/D9 的 write-through）。
- schema 由 **Alembic** 管（`backend/alembic/`，baseline `0001`）；舊 raw SQL migrations + `company_tasks`/`ksa_items`/`icap_*`/`interview_sessions` 表與 models 已刪。

## 進度（全完成）

Phase ①資料層 → ②圖骨幹 → ②-FE CopilotKit → ③深問 → ④assemble/build → ⑤OTel+eval → **Live-wire A**（接真 indexer/DbPersist/PostgresSaver）→ **Concern B**（刪舊 graph/orchestrator/icap_*）→ **前端 Slice 1-3**（AG-UI 遷移 D22 + v2 + 全 interrupt 接齊）→ **v3 dashboard 重建** → **D24 KSA 流程重設計** → **D25 DB 文件導向重作** → **docs 清理** → **合併 master**。後端 suite 61 passed；前端 tsc+eslint 乾淨。

關鍵中途決策：**D22** copilotkit 0.1.94 ↔ JS 不相容 → 改 AG-UI；**D24** KSA 逐任務 K/S + 全域 A + REVIEW（對齊 OCS 職能基準）；**D25** DB 文件導向（業務表精簡 3 張、Alembic）；**D26** MVP 範圍。

## 環境 / 怎麼跑

- venv：`s:\jobintel-ai\backend\.venv`（Python 3.13）。測試：`cd /s/jobintel-ai/backend && .venv/Scripts/python -m pytest -q`（**別用 uv run**）。DB 測試需 `TEST_DATABASE_URL` 否則 skip。
- **後端啟動**：`.venv\Scripts\python run_live.py`（:8001；Windows 要 SelectorEventLoop，run_live 已設）。**別用 `uvicorn app.copilotkit_live_app`** 直接跑（會撞 ProactorEventLoop）。
- **DB**：`docker compose up -d db`（Postgres `jobintel_db`）→ schema 套用 `cd backend && .venv/Scripts/python -m alembic upgrade head`。重建 dev DB（破壞性、需明確授權）：`DROP SCHEMA public CASCADE; CREATE SCHEMA public` + alembic upgrade + 重啟（checkpointer 表自動重建）。
- **indexer**：`cd /s/jd-ocs-indexer && uv run jd-ocs-indexer serve --port 8000`（載 BGE-M3 + 連 Qdrant；冷啟首搜 ~3s、暖機後 ~0.2s）。
- **前端**：`cd frontend && npm run dev`（:3000）。Next runtime route 連後端用 **127.0.0.1**（非 localhost，避 IPv6 ::1）。

## 已知 / 待辦（都已記錄，可新 session 接）

- **resume**（重開 profile 接續 thread）：後端機制已清楚（thread 釘 profile id 後 `runAgent()` 不 setState 即從 checkpoint 重現 interrupt）；卡點＝CopilotKit **v2 headless** 怎麼釘 threadId（`useAgent` 不收、mutate 被 lint 擋；正規入口可能是 `CopilotChatConfigurationProvider`/`setThreadId`/`useThreads`，未驗）。需獨立 focused session + 瀏覽器迭代。見 decision log「Resume 調查」。
- **完成後編輯 JD**（D26 延後）、**匯出 docx/pdf**、**多租戶**。
- **indexer 端（別 repo）**：`/tasks/by-id` 502（深問 outputs 預填降級中）、profile 搜尋相關性弱。修好後 KS 來源可從 `pairs()` 職類池升級成 per-task `tasks_by_id`（D24-c）。
- tech debt：AsyncPostgresSaver 單連線非 pool；live app 啟動 fail-hard；FE `as never` interrupt payload 型別。

## 規矩（使用者定）

每決策先找**權威資料**→列選項優劣→使用者選→記 decision log→再 TDD（subagent-driven：RED→GREEN→commit + task reviewer + 終審）。**舊碼可丟**（只 `docs/superpowers/` 是新架構權威）。提交**不要** Co-Authored-By trailer。破壞性 DB 動作需明確授權。
