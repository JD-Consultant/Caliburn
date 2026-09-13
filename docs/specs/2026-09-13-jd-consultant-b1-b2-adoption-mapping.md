# B1／B2 與顧問方法的採用映射

2026-09-13；JD-R002／OI-01、OI-02。[接續計畫 §5 H4](../plans/2026-09-13-jd-app-continuation-handoff.md) 要求的第一份交付。基準 `b76254f6`／tag `jd-memory-repair-app-review-20260913`。**本稿只做映射與差距判定，沒有改任何產品程式、沒有新增資料表、0 provider、日常 `enable_chat=False`。**

這是**採用已完成的顧問**，不是重新研究顧問。CT49／CT50 已驗的訪談理解、詳記、整併與即時更正能力一律沿用；新 App 只補「新接點確實需要」的部分。

## 1. 已驗來源的確切界線

採用來源是舊 checkout `.worktrees/analysis-only-agent` 的 `experiments/analysis-agent`。該 checkout 在 CT 驗收之後還繼續做了**舊 JD 編輯器**，兩者必須分開：

| commit | 內容 | 採用判定 |
|---|---|---|
| `309eaf21` | [CT49 固定新版長訪談](../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct49-fixed-long-interview-results.md)的固定基準：11 輪真模型、三層記憶、案例詳記、引用回查、晚期更正 | **已驗，採用** |
| `4f94fbfb` | [CT50 已測配置](../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct50-tested-profile-results.md)：`build_conversation`／`AnalysisService` 預設 16 模型／15 工具，A／B2 effort high，輸出 8192、native compaction 12000。**只動 3 檔 8 行**（`api.py`／`conversation.py`／`service.py`） | **已驗，採用配置語意** |
| `622e548d` | CT50 的成對容量紀錄（純文件） | 已驗範圍的終點 |
| `88eda480`..`033540ce` | 舊 JD 編輯器：`jd_*` 十餘個模組、`windows_lifecycle.py`、`sources.py` 增量、`write-customized-jd` skill 等，共 **2853 行** | **不採用。**新關聯式 App 已取代這一整層 |

**本次核對的事實：**`extraction.py`、`consolidation.py`、`live_memory.py`、`scheduling.py`、`memory.py`、`publication.py`、`memory_patch.py`、`consolidation_tools.py`、`repair.py`、`references.py`、`memory_tools.py`、`budget.py`、`provider.py` 在 `309eaf21..033540ce` 的整段區間內**完全沒有出現在 diff**，即與 CT49 驗收時逐位元相同。因此 `adoption.json` 既有的 `source_commit: 033540ce` 與各檔 hash 對 CT 已驗狀態同樣成立，不需要改指 `309eaf21`；但**顧問層的採用來源應引 `4f94fbfb`**，不是 `033540ce`，否則會把舊 JD 編輯器算進已驗範圍。

`sources.py` 與 `skills.py`／SKILL.md 落在舊 JD 編輯器區間內（`sources.py` +21、`write-customized-jd/SKILL.md` 為該區間新增），**沒有 CT 級驗收**；採用時須另行判斷，不能因為它在同一 checkout 就當成已驗。

## 2. 採用映射（主表）

| 已驗來源 symbol（`4f94fbfb`） | 正常 package 落點 | 新 App source／owner adapter | 沿用案例 | 只因新接點需補 |
|---|---|---|---|---|
| `memory.MemoryArtifacts`／`ReadOnlyFiles`／`ExtractionFiles` | **已在** `caliburn_memory.memory` | `memory_context.MemoryReadSession`、`memory_sources.MemorySourceReader` | 已沿用 | 無 |
| `publication.PublicationStore`／`PublishRequest`／`Receipt` | **已在** `caliburn_memory.publication` | `host_runtime` 的 `memory_engine`（schema-mapped） | 已沿用 | 無 |
| `live_memory`／`repair`（C） | **已在** `caliburn_memory.repair`（含 `build_repair_graph`） | `memory_repair_session`／`memory_repair_records`／固定 `memory_repair` 節點 | 已沿用 | 已於[C 接合](2026-09-13-jd-memory-repair-app-integration-slice.md)補完 |
| `memory_tools.readonly_file_tools` | **已在** `caliburn_memory.read_tools` | `memory_context.build_consultant_tools()` 的四個只讀工具 | 已沿用 | 無 |
| `extraction.ExtractionWorkflow`／`ExtractionOutput`／`INSTRUCTIONS`（B1） | **尚未採用** → 建議 `caliburn_memory.extraction` | 需要「完成窗口」source port（見 §3.1） | `test_extraction.py`(450)／`_feedback`(207)／`_role`(164)／`test_summary_reextraction.py`(269) | 窗口來源改接後的窗口規劃／驗證案例 |
| `consolidation.ConsolidationWorkflow`／`INSTRUCTIONS`（B2） | **尚未採用** → 建議 `caliburn_memory.consolidation` | 沿既有 `PublicationStore`／CAS；需與 C 的 receipt 權責銜接 | `test_consolidation.py`(503)／`_delivery`(126)／`_feedback`(271)／`_request`(212) | C 更正不被晚到舊候選蓋回的配對案例 |
| `sources.ConversationReader.extraction_windows`／`unprocessed_source`／`pending_consolidation_turns`／`source_covered`／`require_new_source_after` | **不整批採用**（綁舊對話圖與 `closed_turns`） | 需在 `conversation_sources` 擴出完成窗口能力（見 §3.1） | `test_current_input_source.py`(81)、`test_conversation_lookup.py` 的語意 | 回合完成權威改為 AI run record 後的全部窗口案例 |
| `scheduling.BackgroundDispatcher`／`BackgroundRow`／`BackgroundAvailability` | **不採用其 SQL 排程表** | 由既有 `ManualRuntime` 前景 owner 與 host 排空負責（見 §3.3） | 排空／可用性的語意 | 背景工作歸屬新 owner 後的啟停與排空案例 |
| `service.AnalysisService`／`conversation.build_conversation`／`api` | **不採用**（新 App 有自己的 host／HTTP／owner） | `managed_app.open_managed_app`／`ai_runtime.AiRuntime`／`chat_service` | 無 | 模型配置接點（見 §5） |
| `jd_*` 十餘模組、`jd_store`／`jd_engine`／`jd_tools` | **不採用** | 新關聯式十三表與 `build_consultant_tools()` 的十個 JD 工具 | 無 | 無 |

`ExtractionOutput.readable_artifact` 目前呼叫 package 的私有 `_prepare_text`，在模型步驟被接受**之前**就套用同一格式界線。採用時需要一個公開入口（或把該驗證移入 package），不要在 App 端複製一份格式規則。

## 3. 新接點的實際差距

### 3.1 完成窗口 vs 本輪來源（最大差距）

舊 `ConversationReader` 同時提供「本輪輸入」與「跨輪完成窗口」；新 App 的 `ConversationSourceService` **只有本輪**：`capture(document_id, run_id)`、`for_turn`、`read`、`validate_reference`、`resolve`，全部以 `_scope(document_id, run_id)` 綁單一回合。

計畫已明示 **C 的本輪 source 不是 B1 完成窗口**，所以不能把 `capture` 直接餵給 B1。缺的是：

- 跨輪範圍引用（舊 `capture(start_id, end_id)`）與其簽章／範圍驗證
- 待整併回合清單（舊 `pending_consolidation_turns`）
- 已處理游標與不回退保證（舊 `source_covered`／`require_new_source_after`）
- 窗口切分（舊 `extraction_windows(max_chars, context_chars)`，含 context_chars 消歧前綴）

**回合完成的權威改變了，而且更強。**舊版讀 `snapshot.values['closed_turns'][input_id]`（status ∈ completed／limit／tool_error／configuration_error／cancelled），並對更早的歷史回退到 `_turn_status` 推斷。新 App 的對應權威是 `jd_ai_run` 的 run record 與 `observed.closed`——那是 `_settle` 確認**所有 SQL receipt 與 C 結果**之後才寫入的終局，比舊的 boundary 嚴格。映射時直接用 run record，不要移植 `closed_turns` 或 `_turn_status` 的推斷分支。

### 3.2 B2 與 C 的權責銜接

C 已經會寫 `kind="repair"` 的 publication receipt 並推進 head。B2 寫 `kind="consolidation"` 並推進 `processed_source` 游標。既有 `PublicationStore` 已用 CAS 與 receipt 處理兩者，[C 接合結果](2026-09-13-jd-memory-repair-app-integration-slice.md)也已驗「晚到的背景整併不讓已收尾的 C 結果失效」。**反方向尚未驗**：B2 以較舊的候選整併時，不得蓋回較新的 C 更正。這正是需要新增的配對案例，不是重寫 Memory。

### 3.3 背景排空歸屬

舊版有自己的 `BackgroundRow` SQL 表與 `tick()` 迴圈。新 App 已有單一前景 owner（`ManualRuntime`）、host 生命週期與已驗的排空／重啟恢復。**不要搬第二套排程器與第二張表**；背景 B1／B2 應成為同一 owner 底下可排空、可在新程序查回的工作，沿用 C 已建立的「原 operation ＋ 原 receipt」恢復規則。

### 3.4 故障重開

舊版 `resume()`／`resume_reextraction()`／`background_max_recoveries` 各自處理中斷。新 App 的恢復語意已由 C 這一輪收斂為：只憑原生位置證據與原 receipt 收尾，不重播。B1／B2 採用時必須落在同一條規則下，不另寫一套重試。

## 4. 保持已驗語意不動的部分

- **B1／B2 的 prompt（`INSTRUCTIONS`）逐字不動。**CT49 的逐段觀察（未確認的「印象中」保留、部分回答不擴寫成全未答、更正與矛盾的區分、候選作為下一位整理者的入口）都綁在這兩份 prompt 上。CT49 的 R03／R05／R06 Minor 保留為後續局部校準，**不在採用時順手改 prompt**。
- **詳記／候選的兩欄結構**（`rollout_summary`／`raw_memory`／`rollout_slug`）與其格式界線不動。
- **模型配置沿 CT50 已測 profile**：16 模型／15 工具、A／B1／B2 effort high、輸出 8192、native compaction 12000。README 須寫明這是本案實測值，不是廠商預設。
- **JD 相關的新增工具與成稿方法另列差異**，不混進 B1／B2 的已驗語意。

## 5. 顧問指引映射

新 App 的顧問指引從主 repo 的既有研究映射到十五工具，不從舊 checkout 的 `write-customized-jd` skill 整批複製（該 skill 屬未經 CT 驗收的舊 JD 編輯器區間）：

| 來源 | 映射到 |
|---|---|
| [工作完整分析](2026-09-09-complete-work-analysis-guide.md) | 訪談議程與「資料不足追問」的判斷點 |
| [客製化深度與訪談校準](2026-09-09-customized-jd-depth-and-interview-calibration.md) | 何時局部足夠可以撰寫、何時繼續追問 |
| [欄位寫作](2026-09-09-jd-field-and-writing-guide.md) | 十個 JD 工具的欄位寫法，不要求 LLM 填滿內部欄位 |
| [品質門檻](2026-09-10-jd-product-quality-acceptance.md) | 工作→JD／JD→依據的雙向核對與收尾條件 |

最後一輪訪談尚未進 Memory 時，收尾仍核最新原話——這條沿 CT49 已驗行為，不因 Memory 尚未更新就略過。

## 6. 建議的施工順序

1. **完成窗口 source port**（§3.1）：在 `conversation_sources` 擴出跨輪範圍引用、待整併清單與游標，回合完成一律以 run record 為準。這是 B1 的前置，先做。
2. **B1 採用**：`ExtractionWorkflow` 進 package，接新 source port；沿用四組既有案例，只補窗口相關的新案例。
3. **B2 採用**：`ConsolidationWorkflow` 進 package，沿既有 `PublicationStore`／CAS；補 §3.2 的 C／B2 方向性配對案例。
4. **背景歸屬**（§3.3）：接同一 owner 的排空與新程序查回，不新增表或排程器。
5. **顧問指引**（§5）映射進十五工具，再跑零 provider 的固定完整旅程。

## 7. 界線與未決

1. 本稿是映射與差距判定，**沒有任何實作或測試執行**；上表的「沿用案例」是舊 checkout 既有檔案的行數盤點，不是已在新 App 通過的證據。
2. B1／B2 的既有案例綁舊 `ConversationReader` 與舊 service；實際可沿用比例要到接上新 source port 才能確定，本稿不預估百分比。
3. CT49／CT50 是代表性單一職位的真模型驗收，不是所有職位或百輪成功率；採用不會自動延伸該結論。
4. 舊 checkout 的 `sources.py` 增量與 `write-customized-jd` skill 未經 CT 驗收，本稿列為「需另行判斷」，尚未判定。
5. H4 完成條件（零 provider 固定完整旅程可初始化、反覆修正、保留早期工作與案例、重開續談）**尚未開始驗證**；自然品質仍屬 OI-09。
