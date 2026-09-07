# CT13：提示保真與原文回查局部修復計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正已觀察到的範圍失真風險、過早收尾及原文地址搬運負擔，不更換 Memory 架構。

**Architecture:** 提示只校準已有的主顧問、B1、B2與讀取路徑。原文工具沿詳記既有 metadata 呼叫 ConversationReader；仍用官方 StoreBackend、LangGraph historical state、ToolRuntime／ToolException，不新增來源層或猜測定位。

**Tech Stack:** 現有 lock：LangChain 1.4.0／LangGraph 1.2.11／DeepAgents 0.7.13；不升版。

**Spec:** [CT13 診斷與方案 A](../specs/2026-09-07-ct12-quality-and-retrieval-remedy-research.md)、[A3 底層核對](../specs/2026-09-07-source-read-runtime-resolution-trace.md)。

## Global Constraints

- LLM-Q019；Owner 已核准局部方案與底層補證。G4 → isolated G7；不等於 G8 品質通過。
- 只改 `codex/analysis-only-agent` 隔離實驗；不接 JD／UI／production，不 merge／push。
- 不新增欄位表、語意 verifier、背景 agent、Memory／原文副本、模糊匹配或向量搜尋。
- 保留原文、舊詳記、CT12 trace；不手工清洗資料讓測試變綠。
- 付費 0／US$0。舊帳本關閉；不讀金鑰、不追加真模型呼叫。未來真測仍 Luna／medium，另定額度。
- 不改模型、推理、context 或工具／輸出上限；離線通過不能證明語意改善。
- 保留其他既有 dirty 檔案；README 只加本段 current 路由，不整份提交既有修改。
- 來源不明、指定 checkpoint 缺失、跨文件明確報錯，不回退最新、不猜資料。

## Preflight／順序

已回讀 root register／decision-process、兩份 spec、工作案例資訊取捨、目前提示與三份分析 Skill。既有 34 項來源／重抽測試作基線。三個切片分開驗證、記錄；A1 與 A2 為同組提示修改但效果分開判讀；A3 與 A4 共用讀取工具及完成判定，依序接線。

官方 prompting 依據：[OpenAI guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)（2026-09-07重新取得全文）：刪重複指令、保留事實與限制、明確成功／停止條件。工具底層固定來源／版本／限制見 A3 spec，不重複抄研究。

### Task 1: A1／A2 局部提示校準

**Files:**
- Modify: `experiments/analysis-agent/src/analysis_agent/extraction.py`
- Modify: `experiments/analysis-agent/src/analysis_agent/consolidation.py`
- Modify: `experiments/analysis-agent/src/analysis_agent/memory_tools.py`（只讀取提示）
- Modify: `experiments/analysis-agent/src/analysis_agent/api.py`（主顧問指令）
- Modify: `experiments/analysis-agent/README.md`（本段摘要）

**Interfaces:** 不改函式或模型 schema；既有三個 B1 文字欄位與現有 Skills 不變。

- [ ] 重看 CT12 Q01／Q03／Q04 首個失真與 Q02 收尾證據。它們是語意 red evidence，不另寫「提示含某句」的假測試。
- [ ] B1 取代原精簡候選敘述，明確：

```text
raw_memory 可比詳記短，但同一事實的對象、本人做法、適用條件、頻率與權限須同義；不能因分組或附近案例而縮窄／擴大範圍。刪條件會改義時保留完整短句。
```

- [ ] B1／主顧問：顧問回述不是員工確認；歧義詞保留員工用語與問答脈絡，不把自己的拆詞當新事實。
- [ ] B2 以條件式深讀補足既有指令：候選與已讀內容不一致、限制不明、或將改變既有工作邊界時，讀相關詳記再整理；不足則保留不確定，不強制每批全讀。
- [ ] 主顧問／reader 不跨案例套頻率、工具、限制。收尾前對照已談重要範圍的本人做法、責任交接、重要條件、結果及專業判斷；需要方法才用既有 Skills，不逐欄盤問、不要求固定輪数、不對未知外部資料無限重問。
- [ ] 離線跑受影響 factory／extract／consolidation／memory tests，僅證明接線未退化；語意品質維持 OPEN。核對 diff 無 fixture 答案硬編碼、無新必填欄位、无暴露隱藏推理。
- [ ] 保存獨立本地 commit；結果記載「提示已校準，品質待真測」，不宣称原失真已消失。

### Task 2: A3 同一工具沿詳記地址回查原文

**Files:**
- Modify: `experiments/analysis-agent/src/analysis_agent/memory.py`
- Modify: `experiments/analysis-agent/src/analysis_agent/memory_tools.py`
- Create: `experiments/analysis-agent/tests/test_conversation_lookup.py`
- Modify: `experiments/analysis-agent/tests/test_memory_read_path.py`
- Modify: `experiments/analysis-agent/README.md`

**Interfaces:**
- `MemoryArtifacts.source_window(summary_path: str) -> dict`：共用原有固定 header 解析，回 `source_reference/context_reference`；不要求 candidates。
- `extraction_window(summary_path)`：先呼叫 `source_window`，再保留配對 candidates 存在檢查，回原介面。
- 同一 `read_conversation(reference: str, runtime: ToolRuntime, offset: int = 0, part: Literal['source', 'context'] = 'source')`：`reference` 可填已見詳記地址或既有直接來源；不加工具數、不加 union。
- 詳記成功回原有分頁欄位，加 `summary_path/part/context_available`；原始 `reference` 仍是真實來源，便於追溯。C 直接來源且 `part='source'` 完全保留原回傳。
- 詳記沒有保存 context 且要求 context：回空 `segments`／`next_offset=None`／`reference=None`／`context_available=False`，清楚不是未讀到的新資料；直接來源配 `part='context'` 回 ToolException，不猜相鄰範圍。

- [ ] 先寫 real ToolNode + InMemoryStore/Saver 測試，紅燈驗證缺少摘要路徑模式，不 mock 自己的解析或 reader。

```python
message = invoke_tool(reference=record.summary_path)
assert message.status == 'success'
assert json.loads(message.content)['segments'] == source.read(ref)['segments']
```

- [ ] 加獨立 source/context 視窗：來源只有「不是」，前置問題在 context；兩者分開、role 正確、沒有 context 不猜。
- [ ] 缺候選的詳記仍純讀成功；`extraction_window` 同時仍拒絕。缺固定 header、缺詳記、錯 checkpoint、跨文件、body 偽 Source 皆不取最新資料。
- [ ] direct C 來源無詳記仍可讀；長中文／emoji 沿同一摘要與 part 分頁完整；model schema 無 runtime／document／checkpoint 參數。
- [ ] 最小實作：移出原 metadata parser，不改 regex、來源 validator、namespace 或 ConversationReader。

```python
def extraction_window(self, summary_path: str) -> dict:
    window = self.source_window(summary_path)
    self.read_text(summary_path.removesuffix('summary.md') + 'candidates.md')
    return window
```

- [ ] tool 將 `/interviews/` 路徑交 `source_window`；選已存 reference；其他 direct 路線交原 reader；已知 ValueError 仍走 ToolException／handle_tool_error。
- [ ] 更新既有 compiled-agent 路由測試改用摘要路徑；保留舊 direct 測試、原生推理／compaction與四個工具 assertion。紅綠後跑來源＋重抽＋live memory 回歸，保存獨立 commit。

### Task 3: A4 完成判定對齊與整批收尾

**Files:**
- Modify: `experiments/analysis-agent/tests/test_conversation_lookup.py`
- Create: `docs/specs/2026-09-07-ct13-local-repair-results.md`
- Modify: 本計畫、README 與 root register 的最新短入口。

**Interfaces:** 重用 `build_conversation`＋`memory_access`，不是新增 reader factory 或第二套完成 validator。過去 CT12 evidence 不改。

- [ ] 以 public service conversation factory 做新 reader 契約測試：成功原文工具結果後 `completed` 才成功；`incomplete/max_output_tokens` 應拒絕、不當正常結束；下一次付費驗證沿此 factory 或真服務，不能只用裸 build_agent。
- [ ] 不提升上限、不假裝 semantic PASS；程式已支持的完成規則以 characterization test 固定接線，不為製造 red 而破壞已有行為。
- [ ] 跑整個 isolated suite，必要 PG 僅現有專用測試資料庫；不重啟 Docker、不碰 current 產品資料。
- [ ] 獨立 review 依 CT13 規格看 scope／source／runtime／錯誤與測試，不重開框架研究。修正實際 finding 後重跑相關測試。
- [ ] 結果分列機制與品質，回寫 root register；本地 commit/tag，不 merge/push。

## 下一 gate 與停止線

本輪不做付費測試。後續另行小額 Luna／medium 驗證 A1 資訊範圍、A2 自主收尾、A3 原文低負擔回查及完整回答，再做整份工作長訪談。沒有品質證據前不能稱「正常訪談全驗收」；若已知局部提示仍反覆失敗，回報具體 trace 再討論，不不停追加警告或新 verifier。

## 執行紀錄

- Task1：提示候選已修改，沒有新測試答案、欄位、Skill 或模型步驟。語意 red 沿 CT12 Q01–Q04；尚無新的語意 green，保留品質 OPEN。94 項抽取／整併／讀取／API 接線回歸通過（13.93s，1項既有上游 warning）。兩次沙箱測試在 pytest 暫存權限失敗，改用沙箱外隔離暫存重跑，未改產品權限或測試行為。獨立唯讀 spec／quality review 無 finding；最後僅修繁中字形。
- Task2：測試先行，修正一個未關閉回合的 fixture 後，7 failed／9 passed（7.54s）。失敗是尚無摘要路徑／context 選擇介面，不是來源底層找不到；接續最小實作。
