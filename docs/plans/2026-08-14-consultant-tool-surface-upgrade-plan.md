# Consultant Tool Surface Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以最新主流 Tool Calling 做法收斂職務顧問的四個唯讀 Tool，並保持 Structured Output、員工審核與 durable authority 的清楚邊界。

**Architecture:** 保留 LangChain `create_agent`、ToolRuntime 與 Deep Agents `SkillsMiddleware`/`FilesystemMiddleware` 作為通用 agent/tool harness。模型只能透過四個受限唯讀 Tool 取得本輪未帶入的 Skill 方法與員工原話；文件變更是 provider-native Structured Output，員工 accept/edit/reject 才是 authority command。Tool 實際使用按需，不以固定「先 Skill、後 Source」排程。

**Tech Stack:** Python 3.13、Pydantic 2、LangChain 1.x、LangGraph 1.0 LTS、Deep Agents 0.7.x、pytest、PostgreSQL。

**Spec:** `docs/specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md` §9.16.3、`docs/adr/0061-compact-consultant-wire-progressive-skills-and-tools.md` 與 `docs/adr/0062-bounded-consultant-read-tools-and-structured-authority.md`。

## Global Constraints

- 產品只呈現一位專業職務分析顧問，Tool 與 Skill 不得變成多 Agent 或員工要操作的流程。
- 本輪不接 RAG；員工來源搜尋仍為同文件的本地查找，但 model-facing 名稱不綁死底層演算法。
- LLM 不得透過 Tool 直接寫 Current JD；文件候選必須先進入員工審核。
- `document_id`、來源 namespace、搜尋結果上限與權限由 application 注入，不要求模型提供已知參數。
- 保留最多 3 次 model calls、2 個 lookup waves 與總 Tool call/token/time/cost budget；獲取彼此獨立時可同波平行。
- 總 Tool 數只有 4，不引入 Tool Search、另一個 LLM router、provider beta 或 MCP catalog。
- 保留 employee source ID、exact text、speaker、validity 與 correction lineage，以支援 quote anchor 與 deterministic verifier。
- 不 push、不建 PR；每個可獨立審核的 Task 驗證後單獨 commit。

---

### Task 1: 凍結 Tool 架構決策與權威來源

**Files:**
- Create: `docs/adr/0062-bounded-consultant-read-tools-and-structured-authority.md`
- Modify: `docs/adr/README.md`
- Modify: `docs/specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`
- Modify: `docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`

**Interfaces:**
- Consumes: ADR 0060 runtime boundary；ADR 0061 compact provider contract。
- Produces: 四個 Tool 的權威名稱、Tool/Structured Output/authority 邊界、lookup 排程規則。

- [x] **Step 1: 建立 ADR 0062**

  決策必須明列 `read_file`、`employee_source_get`、`employee_source_lineage`、`employee_source_search`，並明定 ADD/REVISE/WITHDRAW/MERGE/SPLIT 只是 structured review draft，accept/edit/reject 只是 employee authority command。

- [x] **Step 2: 更正研究稿的 Tool Search 適用範圍**

  移除「Anthropic 約 10 個就建議 Tool Search」的過度推論；記錄目前官方定位為數十至數千個 Tool 的 catalog scaling，目前 4 個不適用。

- [x] **Step 3: 記錄官方來源與 owner 核准**

  來源包含 OpenAI Function Calling/Structured Outputs/Model Guidance、Anthropic Tool Search/Writing Tools for Agents、Google Function Calling/Structured Outputs、LangChain Tools/Structured Output。ADR 記錄 owner 於 2026-08-14 核准直接施工。

- [x] **Step 4: 文件自審**

  Run: `git diff --check -- docs/adr docs/specs`

  Expected: exit 0；ADR 0061 維持 schema-only，Tool 決策只在新 ADR 0062。

- [x] **Step 5: Commit**

  ```powershell
  git add docs/adr/0062-bounded-consultant-read-tools-and-structured-authority.md docs/adr/README.md docs/specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md docs/plans/2026-08-14-consultant-tool-surface-upgrade-plan.md
  git commit -m "docs: decide bounded consultant tool surface"
  ```

### Task 2: 收斂員工原話 Tool 契約

**Files:**
- Modify: `apps/api/tests/test_consultant_context.py`
- Modify: `apps/api/tests/test_consultant_run_service.py`
- Modify: `apps/api/app/consultant/context.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/consultant/agent.py`（同步 lookup budget allowlist，避免新名稱繞過上限）

**Interfaces:**
- Consumes: `DocumentSourceLookup.by_id/lineage/search`、server-bound `document_id`。
- Produces: `build_employee_source_tools(lookup, *, document_id) -> tuple[BaseTool, ...]`，Tool IDs 為 `employee_source_get`、`employee_source_lineage`、`employee_source_search`。

- [x] **Step 1: 先寫會失敗的 Tool 契約測試**

  測試要求：Tool 名稱為新的 domain names；`employee_source_search` 只暴露 `query`；結果包含 `source_id`、`kind`、`speaker`、`text`、`created_at`、`validity`與 correction pointers；他文件 ID 無法讀取。

- [x] **Step 2: 執行紅燈**

  Run: `cd apps/api; uv run pytest -p no:cacheprovider tests/test_consultant_context.py::test_langchain_source_tools_are_document_scoped_and_expose_exact_evidence tests/test_consultant_run_service.py::test_configured_execution_has_all_methods_and_only_non_rag_source_tools -q`

  Expected: FAIL，原因是 production 仍暴露 `source_by_id/source_lineage/source_lexical_search` 與 model-controlled `limit`。

- [x] **Step 3: 實作最小 Tool 契約**

  ```python
  EMPLOYEE_SOURCE_TOOL_IDS = (
      "employee_source_get",
      "employee_source_lineage",
      "employee_source_search",
  )

  @tool("employee_source_search", description=EMPLOYEE_SOURCE_SEARCH_DESCRIPTION)
  async def employee_source_search(query: str) -> list[dict[str, Any]]:
      sources = await lookup.search(
          document_id,
          query=query,
          mode=SourceLookupMode.LEXICAL,
          limit=5,
      )
      return [_source_tool_payload(source) for source in sources]
  ```

  `document_id` 與 `limit=5` 都留在 closure/application，不進 model schema。

- [x] **Step 4: 執行綠燈與 context regression**

  Run: `cd apps/api; uv run pytest -p no:cacheprovider tests/test_consultant_context.py tests/test_consultant_run_service.py -q`

  Expected: PASS。

- [x] **Step 5: Commit**

  ```powershell
  git add apps/api/app/consultant/context.py apps/api/app/consultant/run_service.py apps/api/tests/test_consultant_context.py apps/api/tests/test_consultant_run_service.py
  git commit -m "refactor: clarify employee source tools"
  ```

### Task 3: 精簡 Skill Tool 並改為依賴驅動 lookup

**Files:**
- Modify: `apps/api/tests/test_consultant_agent_and_skills.py`
- Modify: `apps/api/tests/test_consultant_model_runtime.py`（同步正式 Tool IDs）
- Modify: `apps/api/app/consultant/agent.py`

**Interfaces:**
- Consumes: Deep Agents `FilesystemMiddleware(custom_tool_descriptions=...)`、`LookupWaveLimitMiddleware`。
- Produces: 保留標準 `read_file` 名稱的精簡 Skill reader；同一 wave 可平行讀 Skill 與 employee source；第二 wave 只在前一結果產生新依賴時使用。

- [x] **Step 1: 先寫會失敗的 model-facing Tool 測試**

  擴充 `RecordingToolModel` 記錄實際 bind 的 Tool description。斷言 `read_file` 說明只提及 eligible `/skills/<id>/SKILL.md` 完整讀取，不宣稱編輯、PDF、圖片或分頁能力。

- [x] **Step 2: 執行紅燈**

  Run: `cd apps/api; uv run pytest -p no:cacheprovider tests/test_consultant_agent_and_skills.py::test_agent_composes_selected_skills_without_leaking_ineligible_content -q`

  Expected: FAIL，原因是 framework 通用 `read_file` description 仍含 filesystem/PDF/edit/paging 說明。

- [x] **Step 3: 使用 framework 公開 override 實作精簡說明**

  ```python
  SKILL_READ_TOOL_DESCRIPTION = (
      "Read one eligible Caliburn analysis Skill in full. "
      "Use only the exact /skills/<skill-id>/SKILL.md path listed for this run. "
      "Omit offset and limit; the server scopes access and records the loaded Skill."
  )

  FilesystemMiddleware(
      backend=backend,
      tools=["read_file"],
      custom_tool_descriptions={"read_file": SKILL_READ_TOOL_DESCRIPTION},
      system_prompt=None,
      tool_token_limit_before_evict=None,
      human_message_token_limit_before_evict=None,
  )
  ```

- [x] **Step 4: 移除固定 Tool 順序**

  `SKILLS_SYSTEM_PROMPT` 只規定：context 足夠就不呼叫；獨立讀取可平行；只有前一波結果改變下一步需求才用第二波。`LookupWaveLimitMiddleware` 的 Tool IDs 同步改成 employee-source 新名稱。

- [x] **Step 5: 執行綠燈與 agent regression**

  Run: `cd apps/api; uv run pytest -p no:cacheprovider tests/test_consultant_agent_and_skills.py tests/test_consultant_model_runtime.py -q`

  Expected: PASS；同一 AI message 的 `read_file` 與 `employee_source_get` 只計一個 lookup wave。

- [x] **Step 6: Commit**

  ```powershell
  git add apps/api/app/consultant/agent.py apps/api/tests/test_consultant_agent_and_skills.py
  git commit -m "refactor: make consultant lookups dependency driven"
  ```

### Task 4: 同步 runtime 設計與北極星審核

**Files:**
- Modify: `docs/design/consultant-runtime.md`
- Modify: `docs/specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`（同步關卡狀態）
- Modify: `docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`
- Modify: `docs/plans/2026-08-13-langgraph-consultant-runtime-big-bang-plan.md`

**Interfaces:**
- Consumes: Tasks 1–3 的 Tool 名稱、排程與 authority 邊界。
- Produces: 實作者可依循的 current runtime 設計，並記錄本輪沒有偏離產品北極星。

- [x] **Step 1: 更新 runtime 設計**

  寫明四個 Tool 都唯讀，structured result 不是 business Tool，employee review command 不得由模型呼叫。

- [x] **Step 2: 回查七個產品不變量**

  逐項對照：單一顧問、前景焦點/背景吸收、動態 Task/Duty/OPKS、記得員工原話、LLM 內容先審後入、必要澄清/一般 Gap 分流、自然離開後續談。

- [x] **Step 3: 確認本輪沒有偷渡延後範圍**

  文件明記：沒有 RAG、沒有能力級別/A、沒有正式 eval、沒有 Tool Search/MCP、沒有多 Agent。

- [x] **Step 4: Commit**

  ```powershell
  git add docs/design/consultant-runtime.md docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md docs/plans/2026-08-13-langgraph-consultant-runtime-big-bang-plan.md
  git commit -m "docs: align consultant runtime tool boundary"
  ```

### Task 5: 完整驗證與收尾證據

**Files:**
- Modify only if verification exposes a regression in a file already owned by Tasks 2–4.

**Interfaces:**
- Consumes: 四個唯讀 Tool、compact structured output、LangGraph authority flow。
- Produces: 可重跑的 API/Web/monorepo 驗證證據。

- [x] **Step 1: 執行 Tool/context/agent targeted suite**

  Run: `cd apps/api; uv run pytest -p no:cacheprovider tests/test_consultant_context.py tests/test_consultant_agent_and_skills.py tests/test_consultant_model_runtime.py tests/test_consultant_run_service.py -q`

  Expected: PASS, 0 unexpected failures。

- [x] **Step 2: 執行 API 完整 suite**

  Run: 設定本機 `TEST_DATABASE_URL` 後執行 `cd apps/api; uv run pytest -p no:cacheprovider -q`

  Expected: PASS；任何新失敗都必須先診斷。

- [x] **Step 3: 執行 Web/contract/monorepo gates**

  Run: `npm run test -w apps/web`

  Run: `npx tsc --noEmit -p apps/web/tsconfig.json`

  Run: `npm run lint -w apps/web`

  Run: `npm run check-codegen -w @caliburn/job-analysis-contract`

  Run: `npx turbo test`

- [x] **Step 4: 執行差異與決策審核**

  Run: `git diff --check`

  Run: `git status --short`

  重讀 ADR 0062 與本計畫，逐項確認沒有 business write Tool、固定 lookup 順序、Tool Search/RAG 或員工審核繞過。

- [x] **Step 5: 建立最後本地 commit**

  若本 Task 因 gate 診斷產生修正，只 stage 該修正與對應 regression test：

  ```powershell
  git commit -m "fix: close consultant tool gate findings"
  ```
