# D28 LLM Agent — 實作 Plan（subagent-driven）

> 依據 design：`2026-06-22-llm-agent-design.md`（D28 定案）。執行：**subagent-driven TDD**（RED→GREEN→commit + task reviewer + opus 終審），分支 `feat/v3`，ledger `.git/sdd/progress.md`。
> **MVP＝甲**：核心結構化、`/ai/*` 直接 fetch、**不上 CopilotKit**（聊天＝Phase 2）。
> **測試＝FakeLlm**（不需 API key）；真模型人工驗收才需 `OPENROUTER_API_KEY`。

## 北極星
員工逐格用 AI 把職務說明書填到 **80 分**：`/ai/*` 專職**純函式**（catalog 優先、AI 補、結構化輸出、不寫 DB、可測、可換模型），✨ 面板/表單直接呼，HITL 暫存→套用→現有 PATCH。函式寫成**未來自主訪談 agent 也能直接重用**（§I 約束）。

## 共用契約 / 規則
- **AI 只提議**：`/ai/*` 回結構化提議、**不寫 DB**；使用者套用才 PATCH。
- **catalog 優先**：標準任務的 O/P/K/S 來自 `tasks_by_id`（UUID）；LLM 只做個人化/篩選/自訂；**無 LLM（key 缺）→ 退化成「只回 catalog 內容」**（draft-op/recommend-ks 仍可用）。
- **來源標記**：每個建議項標 `source: "catalog" | "ai"`（+ K/S 帶 `reason` 一句）。
- **LLM**：reuse `LlmPort`（`complete_json`，`role` 分層）；模型 env 設定、可 per-endpoint。
- **grounding**：K/S 代碼盡量落在 catalog；自訂/AI 生成標 `source:"ai"`、無 code。

---

## Tasks（順序＝依賴）

### T0（前置）catalog UUID 串接
`tasks_by_id` 需任務 UUID（`PoolTask.id`），但目前 `task-candidates`/`build-tasks`/provenance 只有 `task_id`("T1.1")。
- `task-candidates` 回傳每任務加 `id`(UUID)。
- `build-tasks` picked 帶 `id`；`ocs_doc` provenance 存 `{ocs_code, task_id, id}`（id＝catalog UUID，可空＝自訂任務）。
- 測試：seed/build 後 provenance 有 UUID；既有測試更新。

### T1 AI 基礎設施
- `get_llm` FastAPI dep（`OpenRouterLlm()` if key else `None`）；新 `app/api/routes/ai.py`（router prefix `/ai`，掛 main + **copilotkit_live_app**）。
- `app/services/ai/`：`prompts.py`（各函式 prompt 模板）+ 共用解析/來源標記 util。
- 測試替身：`FakeLlm`（給定輸出的 LlmPort，放 tests/conftest 或 app；複用既有 stub knowledge）。
- 測試：router 掛載、無 key 時 `llm=None` 注入 OK。

### T2 `POST /ai/recommend-ks`
- 輸入 `{profile_id, task_key, note?}`；用 provenance UUID → `tasks_by_id` 取該任務官方 K/S 當候選。
- 有 `note`+LLM → LLM 依描述**篩選/排序+理由**；無 note 或無 LLM → 回**catalog 全部 K/S**（source=catalog）。
- 輸出 `{knowledge:[{code,name,source,reason?}], skills:[...]}`。
- 測試（FakeLlm + stub indexer）：有 note 篩選、無 note 回全 catalog、無 LLM 退化、indexer 掛→空+不爆。

### T3 `POST /ai/draft-op`
- 輸入 `{profile_id, task_key, note?}`；`tasks_by_id` 取官方 outputs/activity_examples 當底。
- 有 note+LLM → 依描述**個人化改寫** O/P；否則回 catalog 官方 O/P（source=catalog）。
- 輸出 `{outputs:[{name,source}], indicators:[{text,source}]}`。
- 測試：個人化、catalog 退化、無 LLM、太薄回空。

### T4 `POST /ai/extract-tasks`
- 輸入 `{intake 自述, ocs_codes}`；`task_pool` 取候選；LLM → `{suggested_task_ids:[], custom_candidates:[{name}]}`。
- 無 LLM → 回空建議（不爆）。測試（FakeLlm）。

### T5 `POST /ai/structure-task`
- 輸入 `{description, ocs_codes}`；LLM → `{task_name, unit_suggestion}`。無 LLM → 用描述當 task_name、unit 空。測試。

### T6 `POST /ai/clarify`
- 輸入 `{task, note}`；若太薄 → LLM 回**一個**追問字串；否則 `null`。無 LLM → `null`。測試。

### T7 `_notes` 工作筆記 + export 剝除
- `ocs_doc`：任務可帶 `_notes`（5W2H/CIT 原文）；`assemble_final` 把 `_notes`（連同 `_uid/_tid/_pool`）一併剝除。lib/ocsDoc 對應 setter。測試：finalize/export 無 `_notes`。

### T8 前端 api + 型別
- `lib/api.ts`：recommendKS/draftOP/extractTasks/structureTask/clarify；型別（含 source/reason、_notes、provenance.id）。

### T9 ✨ 面板（核心 AI 入口）
- 每任務一顆 **✨**；面板：5W2H 卡（必填1格「做什麼/產出」＋選填 CIT＋收合細節）→「產生」→ 呼 `draft-op`+`recommend-ks` → **暫存**（O/P 可改、K/S 勾選+來源/理由）→「套用」（現有 setOp/setKS + PATCH）。
- 「全部採用/捨棄」（單任務）；警語；太薄→顯示 `clarify` 追問一輪。
- `_notes` 隨套用一起存。manual 逐格面板（D27）保留。

### T10 intake 小訪談（Phase 0）
- 進工作台前一頁 3 格表單（職稱/職務、主要工作、特別工作，可跳過）→ 存 `job_summary`+ → 呼既有 search 推職類（員工確認）+ `extract-tasks` 預勾任務、列候選自訂。

### T11 任務盤點/補漏/自訂
- catalog 勾選清單預勾（extract-tasks）；CIT 補漏問→`structure-task`→新增任務（**建立時要求一句描述**）。

### T12 次要任務「一鍵取 catalog」
- 任務上「一鍵帶 catalog」→ 呼 `draft-op`+`recommend-ks`（無 note＝回 catalog 官方）→ 直接暫存→採用/略過。

### T13 e2e + eval
- e2e（需 key、人工）：員工小訪談→盤點→核心 ✨ 深填→次要一鍵→A→80 分→顧問精修。
- eval gate：grounding（K/S code ∈ catalog、有 source 標記）、結構（輸出 schema）。FakeLlm smoke 進 pytest，真模型不進。

## 收尾
- 後端 suite 綠（FakeLlm，無需 key）；前端 tsc/eslint 乾淨。
- 真模型人工驗收（給 key 後）。更新 PROJECT-STATUS + decision log「D28 實作完成」。

## 不做（Phase 2 / 延後）
CopilotKit 自由聊天副駕、一鍵自動草擬整份（→未來自主訪談 agent，§I 已預留函式介面）、多帳號權限、PDF/docx、語音、本地模型 adapter（隱私需求出現再加）。

## 開新 session 接續
spec＝`2026-06-22-llm-agent-design.md`、plan＝本檔。新 session：讀這兩份 → subagent-driven 從 **T0 → T7（後端，FakeLlm 可測、免 key）** 先做，再 T8→T12 前端，最後 T13。後端啟動/測試指令見 PROJECT-STATUS。
