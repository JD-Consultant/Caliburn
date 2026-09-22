# Q019-MEM-SUMMARY-01：詳記按需重抽與更正路由

> 2026-09-06 · Owner 已准隔離實作；不接 API/UI/JD。執行結果另記，不以計畫當完成證據。

**Goal：**既有詳記可按相同來源重新抽取；新結果經 B2 整併後發布目前工作理解及引用，原文、舊版本、普通背景进度不受破壞。

**Architecture：**仍用 LangChain structured output、LangGraph Saver、DeepAgents StoreBackend/file tools、SQLAlchemy 現行 head/receipt。重抽只另用技術 checkpoint 保存中斷狀態；不增業務資料庫／Case schema／前台工具。B1 三字串輸出不變。B2 仍模型按需修改 staged knowledge/guide，驗證後 CAS 發布。

**Spec／status：**主 checkout [current decisions](../../../../docs/current-decisions.md)、[接法稿 §7](../../../../docs/specs/2026-09-06-interview-summary-correction-routing-proposal.md#7-已授權的小切片工程接線)。不要回讀 worktree 歷史 register 猜目前決策。

**Evidence：**[OpenAI source review](../../../../docs/specs/2026-09-06-openai-rollout-summary-correction-source-review.md) 及其中固定 SHA；[Codex Stage1 source-key update](https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/state/src/runtime/memories.rs#L853-L942)、[consolidation](https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/templates/memories/consolidation.md#L306-L351)、[reader](https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/ext/memories/templates/memories/read_path.md#L33-L73)。框架：[backend](https://docs.langchain.com/oss/python/deepagents/backends)、[durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)。本案 bounded windows/immutable versions/repair publication 是達成已准目的的工程映射，不稱底層與 OpenAI 相同。

## Global constraints

- 保存所有已接收原始訪談；重抽只看既存詳記確實引用的 source/context，不把摘要冒充原話、不靠頭尾截斷。
- 舊詳記保留歷史語境；不同段更正仍寫新詳記，再修目前理解，沒有全詳記自動同步。
- 新舊替換引用由 Runtime 提供；模型不新增 UUID/time/lineage/schema 欄位。
- 主 agent、背景 agent 的既有分工不變；重抽為明確 Runtime 動作，不每輪自動重抽。
- 機械引用存在性不是語意品質保證；測試只證明機制及資料可用。
- 不改 production、不要 Docker restart/reset、不要真實 API 費用、不 merge/push。

## Task 1：來源還原、重抽與 B2 發布（同一耦合切片）

Files（相對 experiments/analysis-agent）：
- 修改 `src/analysis_agent/memory.py`、`extraction.py`、`consolidation.py`、`sources.py`；reader instructions 在 `memory_tools.py`／`live_memory.py`。
- 新增 `tests/test_summary_reextraction.py`，延用 `tests/test_extraction.py`／`test_consolidation.py` fixture。

1. 先跑原 suite 留 baseline。
2. RED：普通同來源 start 仍 no-op；明確 reextract(summary_path) 重新呼叫抽取，source/context 與原詳記一致；回傳新地址、原地址／原文未改。
3. 實作 `MemoryArtifacts.extraction_window(summary_path)`：只讀本文件、Runtime 產生的 `/interviews/<uuid>/summary.md` header。檔案開頭格式標記＋明確 context 空值＋結束行，回傳 source/context，驗候選配對存在，不讓模型提供新來源。舊格式只允許讀取，不猜測轉換。
4. 實作 `ExtractionWorkflow.reextract(summary_path)`／`resume_reextraction(summary_path)`；同一原詳記對應固定技術 checkpoint，已 pending 時要求 resume。新明確重抽可生成新結果；normal extraction checkpoint 不變。來源超过配置上限明確拒絕，不靜默再切範圍。State 增 nullable `replaces_summary`，normal start 清空。
5. RED→GREEN：失敗保存後用已 checkpoint 的模型結果 resume；不存在／外文件／非詳記路径拒絕且沒有模型費用；重抽不影響普通前進位置。
   `ConversationReader.validate_saved_window` 共用已完成 source range 檢查，但只計算原保存 source/context 額度；不再跑選窗 planner，以免放寬額度反而改掉或拒絕既有輸入。
6. 實作 B2 `start_reextraction(summary_path)`，讀已完成的重抽 snapshot；共用 `_start` 驗 B1 完成。一次工作身份以來源＋實際產物地址辨認，不因來源相同忽略新产物。
7. B2 重抽不走普通來源前進判断；payload 帶系統提供的 `REEXTRACTION`（old/new address）。Instructions 要重新看與舊詳記相關的結論／引用，不能把重抽當成員工後來改口；跨段更正若共同模式未變，也不得省略案例層更正。
8. `_prepare` 對重抽用既有 `kind=repair`＋source reference，不挪動 processed_source。正常 B2 保持 consolidation 語意。不改 PublicationStore schema。
9. RED→GREEN：重抽在已整併相同來源後仍會 B2；成功 head/refs 可讀、失敗旧 head 有效、重複 start/resume 不新增費用；歷史重抽不退 cursor；stale 路徑維持既有模型/tool累計限額。

## Task 2：PG 驗證、獨立審核、文件保存

- 新增 `tests/test_postgres_summary_reextraction.py`，真正 PostgresSaver/Store/PublicationStore 重建物件後 resume 一個重抽／發布流程。
- DB 只 `q019_agent_test`，DSN 沿外部環境，不讀印 API key/password；未提供則明確 skipped。
- `uv run --no-sync pytest -q`；`uv run --no-sync python -m compileall -q src tests`；`uv lock --check --offline`；`git diff --check`。
- 獨立 code review 檢查來源範圍、進度、重試、版本及引用，修正具體問題再驗證。
- 更新本實驗 `README.md`、新增短 results；主 checkout register/接法稿連至成果，研究事實留 source review 不複製。
- 僅本切片指定檔案 commit／本地 tag。停在本段，不開始 API/UI 或自動排程。

## Progress

- Preflight：已回讀最新 register、process、接法稿、OpenAI source、Memory 設計及實作；Task1各檔案緊密耦合，主 agent 連續 TDD，Task2依賴完成結果；交付前獨立 reviewer。沒有新產品選擇。
- Baseline：189 passed／20 skipped（尚未注入專用 PG DSN）。
- Task1：最初8個 missing-feature RED；實作後基本接線 GREEN。新增2個 RED 揭露跨工作重送需查 receipt，以及模型正文不能混入 runtime context header；已修正並 GREEN。來源 header 增明確空值／結束界線，舊實驗格式可讀但不猜測來源重抽；不搬移舊資料。
- Task2：已增加2個真 PG 斷線重建用例，第一輪全 suite 222 passed／0 skipped；又補案例更正回查與 stale 用例，最新 focused 13 passed。最後 suite／獨立 review 結果見 [results](../specs/2026-09-06-summary-reextraction-results.md)，此處不重複維護最終數字。
- Publication operation 由文件／來源／immutable artifact 地址決定，沿既有 receipt 對帳；模型不填新欄位，無新表。這是既有協調的延伸，不冒稱 OpenAI 原碼。
- 獨立 review R1/R2：先重現2 RED，修正文偽裝舊header及放寬context造成重新選窗；focused70 GREEN。最終全 suite **226 passed／0 skipped／28.00秒**；compileall／offline lock／diff check通過，獨立限定複核 R1/R2 CLOSED。
- Task1／Task2 complete：僅保存本切片 commit/tag；不 merge/push，不開始 API/UI/排程/JD。內容／限制／後續路由見 results。
