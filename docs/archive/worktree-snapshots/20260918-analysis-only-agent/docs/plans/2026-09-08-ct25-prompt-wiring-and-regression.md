# CT25 Prompt Wiring and Regression Implementation Plan

> **For agentic workers:** 依單一、緊密耦合的局部切片執行；主代理完成接線與測試，另做只讀review。不另開架構討論。核准範圍不含新的付費測試。

**Goal:** 接入Owner已同意的CT25 M1＋T1提示，保留為歷史BUG新增的防錯條件。

**Architecture:** 原LangChain middleware與DeepAgents工具不換；使用公開`custom_tool_descriptions`校正共用文字讀取工具。修改模型可見指引，不修改編輯器、Memory發布、排程或模型。

**Tech Stack:** 現有LangChain 1.4.0、LangGraph 1.2.11、DeepAgents 0.7.13、OpenAI SDK接線；版本不動。

**Spec:** [CT25完整候選](../specs/2026-09-08-ct25-gpt-prompt-stack-and-live-repair-candidate.md)與其[已審核JSON](../specs/evidence/2026-09-08-ct25-memory-prompt-candidate.json)。JSON為獨立審核fixture，runtime不讀docs。

## Global Constraints／preflight

- Topic：Q019-MEM-CADENCE-01／CT15-R07；本輪G7 isolated wiring，G8仍OPEN。
- Owner核准CT25，補充「舊prompt可能為歷史BUG新增，需保留有效保護」及「相似錯誤可整理成更好的prompt」；保留防錯意圖，不要求逐字保留每個舊句；本輪唯一問題是接線與舊保護是否一致。
- 6工具、schema、來源路由、patch與錯誤回饋、Store／Saver、reasoning／compaction、Skills、B1/B2提示、顧問角色均不變。
- 不接JD／production、不加Agent／強制工具／timer、不使用舊已封存的付費額度。
- 已讀：主register／decision-process、CT25／CT21全文、CT04細節省略歷史、CT13來源／案例保真修復；官方GPT指南再次核對「精簡時保留限制」節。官方接點及引用沿CT25§6。
- 已有worktree：`S:/caliburn/.worktrees/analysis-only-agent`，分支`codex/analysis-only-agent`，起點`044ec71e`。既有dirty內容不屬本輪。
- 基線：`tests/test_memory_prompt_contract.py` 2 passed（4.55秒）。

## Task 1：完整提示接線與舊錯誤安全網

**Files:** 修改`experiments/analysis-agent/src/analysis_agent/live_memory.py`、`memory_tools.py`、`tests/test_memory_prompt_contract.py`；同切片更新app README、CT25狀態／保護對照與register。候選JSON保持不變。

**Interfaces:** `MemorySession.wrap_model_call`產生Memory指引；`MEMORY_REPAIR_DESCRIPTION`供原`@tool(description=...)`；`readonly_file_tools(backend)`仍回官方BaseTool instances。外部模型請求需逐字／逐結構等於獨立核准fixture（僅既有3項動態占位正規化）。

- [x] **1. RED：**現有SDK-boundary測試改為讀CT25候選，而非CT21；先跑兩項，應因system／工具描述仍舊而FAIL，不是fixture自己從程式生成。

```python
fixture = Path(__file__).resolve().parents[3] / 'docs/specs/evidence/2026-09-08-ct25-memory-prompt-candidate.json'
```

- [x] **2. 接入M1：**用候選JSON的system Memory block中`## Memory read view`之前文字替換`MEMORY_ACTION_GUIDANCE`；只改C工具no_memory說明。`PATCH_GUIDANCE`、`MEMORY_EDIT_GUIDANCE`及其餘read-view文字原樣保留。
- [x] **3. 接入T1：**把核准的三個description作為既有module的固定字串，經官方constructor提供；不在runtime載入候選文件、不修改原套件或註冊其他hooks。

```python
filesystem = FilesystemMiddleware(
    backend=backend, tools=["ls", "grep", "read_file"],
    custom_tool_descriptions=READONLY_TOOL_DESCRIPTIONS,
    human_message_token_limit_before_evict=None,
    tool_token_limit_before_evict=4000,
)
```

- [x] **4. GREEN：**同兩項接線測試通過；主A及空Memory服務入口的正常tool-followup請求都符合候選。這不證明自然模型會選repair。
- [x] **5. 舊錯誤回歸：**跑全部本機、非PostgreSQL測試，模型I/O均為離線fixture。既有測試實際驗patch定位／批次原子性／stale重讀／重試上限、逐層原文回查／長中文分頁、Skills讀取、opaque continuity、背景通知回執與context budget；不增加source-text字串存在測試冒充語意效果。
- [x] **6. 保護比對：**與`044ec71e`比較，確認patch／detail guidance、B1/B2、api顧問與Skill正文不變；6組schema與來源tool不變。記錄歷史BUG→現有指令→回歸測試，必要條文不得因重複就刪。
- [x] **7. Review：**只讀review已查完整diff、候選偏差、共用讀取面的影響與未驗收事項，無實質finding。回歸與AST保護比對通過，見CT25§7。僅本輪檔案進本地commit／tag；保存結果以主register收尾紀錄為準。README既有dirty段落不一併提交；主register亦保留既有未提交內容。

**Verification commands:** 在`experiments/analysis-agent`執行`.venv/Scripts/python.exe -m pytest tests/test_memory_prompt_contract.py -q --tb=short --basetemp <fresh-workspace-temp>`；全離線回歸以`tests/test_*.py`排除`test_postgres_*`的明確檔名清單執行。Windows新pytest目錄使用已核准一般權限，不更改ACL或刪舊目錄。

**Exit／next gate:** 接線與機械安全網通過後才提出新的小額Luna／medium自然選擇驗證。CT22 FAIL與原證據保留；漏選根因仍不確定，不以離線綠燈宣稱穩定訪談。需要改核准候選的語意、模型或架構時先回報Owner。

## 自審

本計畫只有一個切片，M1與T1在同一完整模型請求交會；不拆成互相矛盾的提示版本。已核對測試使用獨立審核fixture、runtime不依賴docs、無付費／promotion授權。歷史測試是機械安全網，不能驗證自然模型是否保留語意細節。
