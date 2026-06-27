# jobintel-ai v3 — 文件即工作台 實作 Plan（D27 → subagent-driven）

> 日期：2026-06-21。依據 design：`2026-06-21-frontend-canvas-ux-design.md`、決策 `2026-06-16-refactor-decision-log.md` D27 定稿。
> 執行：**subagent-driven TDD**（RED→GREEN→commit + task reviewer + opus 終審），分支 `feat/v3`。ledger `.git/sdd/progress.md`。
> **MVP = β REST-first，完全不碰 LangGraph/AG-UI**（CopilotKit 冰起來=A：套件留著、工作台不引用、舊 interrupt 頁當 legacy）。

## 北極星
職務說明書 = 一份**合法 OCS JSON**（`jd-pdf-to-json` 契約）。前端是「文件即工作台」：先 seed 骨架 → 自由點空格填（O/P 手打、K/S/A catalog 候選）→ 每格 PATCH 連續存 draft → finalize 產 final。

---

## 契約（先定，task 共用）

### OCS document JSONB（draft 與 final 同形；每任務一個 competency_block）
見 design §B5。要點：5 區塊 `version_info/ocs_profile/ocs_content/ocs_attitude/notes`；`ocu_units[].tasks[].task_codes[]`（陣列）+ `competency_blocks[0]`（每任務恰一個）= `{competency_level:int|null, indicators[], outputs[], knowledge[], skills[]}`；item 皆 `{code, name}`（P 用 `{code, text}`）；A 全域；codes 與 names 並存（catalog 帶的留 code，自訂可無 code）。

### REST 端點（掛 `job_profiles` router，`/api/v1`）
- `GET  /job-profiles/{id}/document` → 回 latest（draft 優先）；無則回**骨架**（見 Task 2）或 404（plan 時二選一，傾向回骨架空殼）。
- `PATCH /job-profiles/{id}/document` → body = **整份 OCS JSON**（MVP 用整份 merge/覆寫，粒度先粗）；存成/更新 draft；回新 content。
- `POST /job-profiles/{id}/document/finalize` → 由 draft 組裝+驗 schema → 寫 `status='final'`、版號遞增；回 final。
- `GET  /job-profiles/{id}/ksa-pool` → catalog `pairs(ocs_codes)` 攤平後的候選 `{knowledge[], skills[], attitudes[]}`（含 code）。快取。
- `GET  /job-profiles?user_id=` 既有 list → 補 `doc_status`(none|draft|final) + `completion`(0..1)。
- seed：`POST /job-profiles/{id}/seed`（或沿用既有 search/task_pool REST）→ 產骨架 OCS 文件存 draft。**plan §C3 待定：seed 是否仍借用既有 LangGraph 一次性跑，還是純 REST**；傾向純 REST（call indexer search + 人選 → task_pool）。

---

## Tasks（順序 = 依賴）

### T1 — persistence：draft PATCH + doc_status/completion
- `DocRepo`：加 `upsert_draft(job_profile_id, content)`（有 draft 就 UPDATE、無則 INSERT v1 draft；finalize 才升版+status）；`finalize(job_profile_id)`（draft→新 final 版）；`status_of(job_profile_id)`→(none|draft|final, completion)。
- `completion` 算法：已填格/總格（每任務 O·P·K·S 非空 4 格 + 全域 A；表頭固定算已填）。
- 測試：upsert 不增版、finalize 升版+status=final、status_of 三態 + completion 邊界。

### T2 — OCS 契約組裝/驗證 util（取代/擴充 `_assemble`）
- 新 `app/services/ocs_doc.py`：`skeleton(profile, units_tasks) -> dict`（產空殼 5 區塊、每任務一空 block）；`assemble_final(draft) -> dict`（補 version_info、確保契約完整）；`validate(doc) -> list[err]`（對齊 jd-pdf-to-json §7 checklist；可選直接呼叫該 repo 的 validator 若可 import，否則自實作精簡版）。
- 沿用既有 `_assemble` 的 T/P/O/K/S 編碼邏輯，但**改成 competency_blocks 巢狀** + task_codes 陣列。
- 測試：skeleton 結構鍵齊全、每任務恰一 block；assemble_final 通過 validate；validate 抓缺鍵/型別。

### T3 — REST 端點
- `routers/job_profiles.py`（或新 `documents.py` 掛同 router）：實作上述 5 端點 + list 補欄。Pydantic schema 寬鬆（OCS JSON 巢狀深，用 dict/JSON 直通 + 關鍵欄驗證）。
- `ksa-pool`：呼叫 `deps.knowledge.pairs()`，攤平成含 code 候選；best-effort try/except（indexer 掛則回空池）。
- 測試（httpx/ASGI）：GET 無 doc 回骨架、PATCH 寫 draft 可再讀、finalize 轉 final、ksa-pool 形狀、list doc_status。

### T4 — seed（產骨架）
- `POST /seed`：input = 已選 ocs_codes（或先 search 互選）；call indexer 取 units/tasks → `ocs_doc.skeleton` → `upsert_draft`。同時 `ProfileRepo.set_selected_ocs`。
- 決 §C3：MVP 用純 REST seed（search 互選可先簡化成「給 codes 直接 seed」，UI 的職類複選後送 codes）。
- 測試：seed 後 GET document 有 units/tasks、O/P/K/S 空。

### T5 — 前端 API client + 型別
- `lib/api.ts`：加 document GET/PATCH/finalize、ksa-pool、seed、list 帶 doc_status。
- `types/`：OCS document 型別（profile/units/task/block/attitudes/notes）。

### T6 — 前端 `JobDocTable`（工作台主表）
- render OCS 契約：表頭 + unit 分區 → task（級別欄唯讀）→ O/P/K/S 四格，每格 ✅(有內容)/⬜(空，點此填)。**不出現 block 字眼**。
- 點格 → 開 filler 面板（T7）。狀態由 document 推算。

### T7 — 各格 filler 面板（重用既有 UI、改成 PATCH）
- O/P：**手打兩清單**（產出 + 績效/行為指標，加/改/刪）。
- K/S：重用 `CurateKsPanel` 外觀，候選來自 `ksa-pool`，勾/加/改，**每任務一次**。
- A：重用 `CurateAttitudesPanel` 外觀，全域。
- 完成 → 合進 document → PATCH → 更新表格。**不引用 CopilotKit**。

### T8 — 工作台 shell + 自動儲存 + 續做 + 錯誤
- `InterviewConsole`（兩欄：進度 rail | JobDocTable）；頂部「✓ 已自動儲存」+「產生正式版本」(finalize)。
- 續做：進頁 `GET document` 載入（無則先 seed 流程）。
- 錯誤：PATCH/GET 失敗 → banner + 重試。`/v3/[id]/page.tsx` 換成工作台（舊 interrupt 版留作 legacy 或刪）。

### T9 — dashboard 狀態
- 卡片顯示 doc_status（未開始/進行中%/完成），用 list 新欄。

### T10 — 進度 rail + 完成度
- 由 document 算 completion + 哪些格空；rail 顯示。

---

## 收尾
- 後端 suite 綠 + 前端 tsc/eslint 乾淨。
- 瀏覽器 e2e：新建 → seed → 點格填 O/P/K/S/A → 自動存 → 重開續做 → finalize → dashboard 顯示完成。
- 更新 PROJECT-STATUS + decision log「D27 實作完成」。
- CopilotKit 維持安裝、工作台不引用（A）。

## 不做（延後，見 design §B10）
LLM 全域 CoAgent（核心、之後另開 spec）、匯出、拖拉、同任務多 block、indexer `tasks_by_id` 502 修復後把 O/P/K/S 升級 per-task、進行中 interrupt 跨 session 精準續答。
