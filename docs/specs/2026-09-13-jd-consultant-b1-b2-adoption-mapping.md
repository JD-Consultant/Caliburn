# B1／B2 與顧問方法的採用映射

**SUPERSEDED 產品映射，2026-09-16：**本稿的已驗程式、來源窗口、checkpoint、Store／Saver、provider、publication、receipt、通知與宿主證據繼續有效；但「B1 固定抽取詳記／候選，B2 才維護兩檔 Memory」的產品責任已由 Owner 的 [MEM-L001](2026-09-16-layered-case-and-work-understanding-memory-alignment.md) 取代。後續須先完成 B1 案例 Agent＋案例 guide、B2 工作理解 Agent＋理解 guide、共同 publication 與 C 跨層修補的 G4 差距設計，不沿本稿的舊採用主表直接施工或宣稱既有 B1／B2 已滿足新效果。

**目前狀態（2026-09-14）：**source port、B1 核心／OpenAI adapter 固定接合及 **§3.6 的批次接點都已完成並在真 PG 上驗過（H4-R1）**；B2／背景／完整通知尚未接。§3.3 仍是未實作的隔離施工設計，未建表。下一依[H4 執行計畫 R2](../plans/2026-09-14-jd-h4-runtime-integration.md)採用 B2 並做 B1→B2→publication 有序交接；下方9/13初稿狀態只保留出處，不要求重做採用映射。

2026-09-13；JD-R002／OI-01、OI-02。[接續計畫 §5 H4](../plans/2026-09-13-jd-app-continuation-handoff.md) 要求的第一份交付。基準 `b76254f6`／tag `jd-memory-repair-app-review-20260913`。**本稿只做映射與差距判定，沒有改任何產品程式、沒有新增資料表、0 provider、日常 `enable_chat=False`。**

**提交後審查修訂：**原稿提交 `2e243d15`；[審查紀錄](evidence/2026-09-13-jd-b1-b2-adoption-review.md)發現已驗方法／整理通知漏接、背景恢復規則誤套及 source 契約不足，已在本稿改正。完成窗口契約另經[9/12–9/13 文件審查](evidence/2026-09-13-jd-window-source-contract-review.md)，補上觸發與連續範圍、B2 `processed_source` 用途感知驗證、source/context pair、offset 單位及 purpose salt 隔離。下文是接續依據；這是文件修正，不代表新 App 的 B1／B2 已通過驗收，也沒有決定新增背景資料表。

這是**採用已完成的顧問**，不是重新研究顧問。CT49／CT50 已驗的訪談理解、詳記、整併與即時更正能力一律沿用；新 App 只補「新接點確實需要」的部分。

## 1. 已驗來源的確切界線

採用來源是舊 checkout `.worktrees/analysis-only-agent` 的 `experiments/analysis-agent`。該 checkout 在 CT 驗收之後還繼續做了**舊 JD 編輯器**，兩者必須分開：

| commit | 內容 | 採用判定 |
|---|---|---|
| `309eaf21` | [CT49 固定新版長訪談](../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct49-fixed-long-interview-results.md)的固定基準：11 輪真模型、三層記憶、案例詳記、引用回查、晚期更正 | **已驗，採用** |
| `4f94fbfb` | [CT50 已測配置](../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct50-tested-profile-results.md)；角色限制分列於 §4。`src` 中改 3 檔、8 行替換（`api.py`／`conversation.py`／`service.py`），整個 commit 另有文件／測試 | **已驗，採用配置語意** |
| `622e548d` | [CT51 8K／16K 成對容量紀錄](../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct51-output-budget-results.md)（純文件，固定產品來源仍為 `4f94fbfb`） | 延續 8192 配置，不需重做容量比較 |
| `88eda480`..`033540ce` | 舊 JD 編輯器：`jd_*` 十餘個模組、`windows_lifecycle.py`、`sources.py` 增量、`write-customized-jd` skill 等；該區間 `src` 共 **2853 新增行、83 刪除行** | **不整批採用。**新關聯式 App 已取代此 JD 接合層；舊基準中原已存在的分析能力仍依下列映射採用 |

**核對事實：**`extraction.py`、`consolidation.py`、`live_memory.py`、`scheduling.py`、`memory.py`、`publication.py`、`memory_patch.py`、`consolidation_tools.py`、`repair.py`、`references.py`、`memory_tools.py`、`budget.py`、`provider.py` 在 `309eaf21..033540ce` 加起點的每個 commit，逐檔 blob hash 均只有一種。因此 `adoption.json` 既有的 `source_commit: 033540ce` 與各檔 hash 對 CT 已驗狀態同樣成立，不需要改指 `309eaf21`；但**顧問層的採用來源應引 `4f94fbfb`**，不是 `033540ce`，否則會把後加的旧 JD 編輯器算進已驗範圍。這項證據只證明來源內容一致，不代表新 adapter 已驗。

`sources.py` 的後續增量與新增 `write-customized-jd/SKILL.md` 沒有上述 CT 級驗收。**不能因此排除 `4f94fbfb` 已有的 `sources.py` 語意、`skills.py` 讀取路由與三項分析 Skills**；後續對既有 Skills 的 JD 尾句修改和舊基準內容分開處理。§5 明列已驗顧問方法，不重寫一套顧問。

## 2. 採用映射（主表）

| 已驗來源 symbol（`4f94fbfb`） | 正常 package 落點 | 新 App source／owner adapter | 沿用案例 | 只因新接點需補 |
|---|---|---|---|---|
| `memory.MemoryArtifacts`／`ReadOnlyFiles`／`ExtractionFiles` | **已在** `caliburn_memory.memory` | `memory_context.MemoryReadSession`、`memory_sources.MemorySourceReader` | 已沿用 | 無 |
| `publication.PublicationStore`／`PublishRequest`／`Receipt` | **已在** `caliburn_memory.publication` | `host_runtime` 的 `memory_engine`（schema-mapped） | 已沿用 | 無 |
| `live_memory`／`repair`（C） | **已在** `caliburn_memory.repair`（含 `build_repair_graph`） | `memory_repair_session`／`memory_repair_records`／固定 `memory_repair` 節點 | 已沿用 | 已於[C 接合](2026-09-13-jd-memory-repair-app-integration-slice.md)補完 |
| `memory_tools.readonly_file_tools` | **已在** `caliburn_memory.read_tools` | `memory_context.build_consultant_tools()` 的四個只讀工具 | 已沿用 | 無 |
| `extraction.ExtractionWorkflow`／`ExtractionOutput`／`INSTRUCTIONS`（B1） | **已在** `caliburn_memory.extraction`；App OpenAI adapter 固定接合完成 | `ExtractionSourceAdapter`／同一 source owner；原生 structured runnable，provider 接受條件由 App 組裝 | 原檔盤點：`test_extraction.py`(450)／`_feedback`(207)／`_role`(164)／`test_summary_reextraction.py`(269)；新實測見[B1 結果](evidence/jd-b1-adoption/app-wiring-results.md) | 有界整批引用、真 PG／新程序、B2 交接與 runtime；不是再做已閉合 pair／W-13 |
| `consolidation.ConsolidationWorkflow`／`INSTRUCTIONS`（B2） | **尚未採用** → 建議 `caliburn_memory.consolidation` | 沿既有 `PublicationStore`／CAS；需與 C 的 receipt 權責銜接 | `test_consolidation.py`(503)／`_delivery`(126)／`_feedback`(271)／`_request`(212) | C 更正不被晚到舊候選蓋回的配對案例 |
| `sources.ConversationReader` 的窗口／批次、`validate_saved_window`、`read`、`unprocessed_source`、`source_covered`／`require_new_source_after` | **不整批採用實作**（綁舊圖）；保留已驗語意 | package source interface＋App `conversation_sources`／`memory_sources` adapter（§3.1） | 原窗口、分頁、角色與範圍案例 | 新簽章引用、逐輪安全終局及有界歷史缺鏈 |
| `consolidation_request.request_memory_consolidation`／`has_saved_request`、`sources.pending_consolidation_turns`、`live_memory.MEMORY_ACTION_GUIDANCE` | 採用純通知與辨識規則；正常 package／App 接點於接線前具體定名 | 新 Agent 註冊工具、原 call/result 驗證、終局後來源投影（§3.5） | 原整理請求／節奏案例，CT51 自然通知證據 | 不能把終局當整理請求；不能只靠文字冒充成功通知 |
| `scheduling.BackgroundDispatcher`／`BackgroundRow`／`BackgroundAvailability` | 不整批搬舊 host；**保留背景工作狀態、限制與可用性通知的責任** | 同一宿主生命週期；六欄准入表設計已在 §3.3 收斂，尚未實作 | 原續作／排空／停止／可用性語意 | 新宿主重開後保留原工作、目標、錯誤及剩餘預算 |
| `api` 的 A 指引、三項分析 Skills、`skills.SkillAssets`／分析 Skills middleware 路由 | 採用已驗內容／讀取行為，不沿用舊 host（§5） | 新顧問 system／Skill 接點與唯讀檔案路由 | CT49／50／51 限定自然證據及既有 Skills 案例 | 已有「不製作 JD」範圍句改成新 JD 接點；其餘改動另列差異 |
| `service.AnalysisService`／`conversation.build_conversation`／`api` 的組裝與資源管理 | **不整批採用**（新 App 有自己的 host／HTTP／owner） | `managed_app.open_managed_app`／`ai_runtime.AiRuntime`／`chat_service` | 原組裝承載的行為按上述各列採用 | 角色配置與必要原生 context／budget helpers，不能因不搬 host 就漏方法 |
| `jd_*` 十餘模組、`jd_store`／`jd_engine`／`jd_tools` | **不採用** | 新關聯式十三表與 `build_consultant_tools()` 的十個 JD 工具 | 無 | 無 |

`ExtractionOutput.readable_artifact` 目前呼叫 package 的私有 `_prepare_text`，在模型步驟被接受**之前**就套用同一格式界線。採用時需要一個公開入口（或把該驗證移入 package），不要在 App 端複製一份格式規則。

## 3. 新接點的實際差距

### 3.1 完成窗口 vs 本輪來源（最大差距）

舊 `ConversationReader` 同時提供本輪輸入與跨輪完成窗口；新 `ConversationSourceService.capture(document_id, run_id)` 只發出本輪 scope，內容主要是該輪 Human 與最近前一則可見 AI，**不是完整 Human→該輪終局**。已發出的較早單輪引用仍可按固定 checkpoint 讀取；缺的是完整跨輪來源能力，不是完全不能讀歷史。

計畫已明示 **C 的本輪 source 不是 B1 完成窗口**，所以不能把 `capture` 直接餵給 B1。缺的是：

- 跨輪範圍引用（舊 `capture(start_id, end_id)`）與其簽章／範圍驗證
- 有已保存整理請求的安全終局清單（舊 `pending_consolidation_turns`；語意見 §3.5）
- 來源順序比較／覆蓋與 B1 admission 不回退保證。**已發布的 `processed_source` 已存在於 publication head，不在 source port 另存一份游標**；不以 UUID／時間排序代替原話順序
- 窗口切分、有限批次及已保存窗口驗證（`extraction_windows`／`extraction_batch`／`validate_saved_window`），含消歧前綴，不跳過中間員工答案

**安全終局改用新 App 證據。**`record.status != "running"` 且 `observed.closed`，由 `_settle` 核完 JD receipt 與 C 結果後成立；不用舊 `closed_turns`／`_turn_status` 推斷分支。完整窗口須在固定祖先鏈逐輪核對，不從最新終局推定全部歷史都安全。已安全收尾的 `failed`／`cancelled` 仍包含員工原話，並標 `answer_succeeded=false`；「安全結束」「答覆成功」「已請求整理」是三件事。

**B1 實際介面要先列清楚：**舊 `ExtractionWorkflow.start` 直接呼叫舊 `parse_reference`，`_source` 需要 `read(reference, offset)` 的 `segments / turns / omitted_content_types / next_offset`。新 `MemorySourceReader.read` 只有 `SourceExcerpt(messages)`，引用使用簽章；只新增 `extraction_windows` 不足以接線。先定正常 package 的來源介面與 App adapter，再替換此直接依賴；保留驗證／角色／分頁語意，不搬無簽章 parser、另發舊引用或削弱目前 C source 的檢查。重抽必須回到已保存的原窗口，不能改用最新本輪輸入。

來源讀取失敗、超過目前 256 祖先查找界線、缺鏈、消歧內容超預算都須明示無法取得完整來源；不截斷後假裝完整、不跳過未收尾回合、不重設 publication 游標。既有長歷史缺口沿 OI-05 處理，本切片不自建歷史資料庫。

### 3.2 B2 與 C 的權責銜接

C 寫 `kind="repair"` 的 publication receipt 並推進 head；B2 寫 `kind="consolidation"` 並推進 `processed_source`。既有 CAS 防止舊基準直接發布；已驗 B2 另有 stale→load、`_repair_input`／`RECENT_REPAIRS`，讓剩餘預算內的整併讀到新 C 更正及原話。**不能只換成最新版號再發布舊內容**。這是沿用既有能力，不是新發明的更正策略；新 App source／owner 接法尚須補 C 與 B2 配對驗收。原 receipt 查回不使 head 或游標倒退，C 不推進背景游標。

### 3.3 背景排空歸屬

舊版用框架排程器喚醒 `BackgroundDispatcher`；`BackgroundRow` 保存准入狀態、固定目標／本批來源、錯誤與恢復次數，B 工作進度由 Saver、發布與游標由 PublicationStore 負責。該表**不是第二份 Memory／原話權威**。新 `ManualRuntime` 目前只有前景／人工／登記讀取的排空，不具備背景准入狀態或其新程序恢復。

採用時共用本機宿主的啟停／資源管理；**不把背景工作硬套前景手改門閘，也不把「不能雙寫」誤寫成禁止必要背景表或框架喚醒器**。不整批搬舊 service、全域鎖或另一宿主，不新造通用排程器。

**2026-09-14 已選定：**缺口驗證已完成且成立（真 PG 逐欄實測 B1／B2 Saver state、publication head 與 `jd_document`，`target_reference`／`status`／`error_code`／`recovery_count` 皆不在其中；批次是 target 的前綴，不能代替它）。因此採用已驗 `BackgroundRow` 的六欄責任，新增 runtime 准入表 `jd_memory_admission`，決定見 [ADR0076](../adr/0076-jd-background-admission-record.md)、狀態機與恢復程序見[背景准入設計](2026-09-14-jd-background-admission-design.md)。**十三張 JD 內容表不增減欄位，但 App 總表數自十三增為十四。**下文保留當時的候選論證作為出處。

**（以下為 2026-09-14 選定前的候選敘述）先保留已驗 `BackgroundRow` 的六欄准入責任作最小基線，但尚未決定增加新表。**Saver 已保存 B1/B2 進度，但尚未開始的 target、未消耗尾端及跨重開的受阻／恢復額度並不在這兩個 workflow 的正式 state 中。將這些硬塞 B1、掃歷史猜測或另造調度 StateGraph 都增加額外接合；沿已驗小表語意可作為待驗替代。這不是 production adoption，也不要求沿用舊 host／constructor setup。R3 先驗證既有 Saver／catalog 是否確實無法承載准入責任；在該缺口成立並完成 migration／ADR 前，不建立此表。

| 欄位 | 最小保存內容／約束 | 單一責任 |
|---|---|---|
| `document_id` | PK、同型別 FK 指新 `jd_document.id`，一文件至多一列 | 不建立新文件身分；不含租戶／帳號／ACL |
| `status` | 非空；`idle/queued/running/blocked` 的 CHECK | 准入狀態，不代替 LangGraph node／pending 狀態 |
| `target_reference` | 可空的簽章 window ref | 原先准入的固定目標；後續新原話不能偷偷擴大此目標 |
| `source_reference` | 可空的簽章 window ref | 當前固定批次；invoke B1 前保存，不是已處理游標 |
| `error_code` | 可空、有界安全錯誤碼 | 不保存 stack、key 或原話；根因未變不重試 |
| `recovery_count` | 非空整數、預設0、CHECK >= 0 | 原工作已用的宿主恢復次數；與 B1 格式更正、B2 模型步分開 |

若 R3 證明需要，候選表的 schema 才以明示 Alembic migration 管理，暫名 `jd_memory_admission`。這是一張 runtime 准入表，**原十三張 JD scope 表不增減正文欄位**；未核准前不得先建表。普通 open 只檢查已安裝；不搬 q019 資料、不雙寫舊表。queued 必有 target、source 可尚未切出；running 必有 target/source；blocked 可在來源規劃之前發生，不能為填欄造假 ref；idle 清掉當前目標／批次／錯誤，不當成永久工作歷史。恢復計數只在確立新的工作或完成舊目標時重置，不因重新開程式歸零。DDL 與原生保存交接須在 R3 實測；這張候選表不是已存在的事實。

同一宿主管理有界 B worker；同文件 B1→B2→發布交接完前不可開始下一批或並行重抽。原生 `files`／工作進度仍在 Saver，發布及唯一 `processed_source` 仍在 PublicationStore。單一 B worker 的容量限制不阻擋所有文件的前景與人工操作；不持 DB／全 App 鎖等待模型。關閉先停新准入、等待已登記實際工作退出，再關 client／Store／Saver。原生續作及原回執處理見 §3.4；完整接線／新程序驗收見執行計畫 R2–R3。

封存後不准入新的 B 批次；已在執行的有限批次可完成保存／發布，未完成目標保留，恢復文件後再查原工作續作。封存不刪除准入資料或重設額度；不是另一套Memory撤回。R3須用既有封存／恢復操作驗證此生命週期，不新增背景管理頁。

保留 `BackgroundAvailability` 的已驗效果：本輪開場獲得整理受阻／尚未涵蓋的通知，通知不冒充員工原話、不從 context getter 啟動 B，不把未處理資料說成已入 Memory。

### 3.4 故障重開

**C 與 B 的已驗策略分開保留。**C 前景未知結果沿 H2–H3 原位置／原 request／receipt 只讀對帳，不放寬重播。B1／B2 已有同一工作 `graph.invoke(None, 原 config, durability="sync")` 的原生續作，以及持久預算／停止條件；B1 還沒有 publication receipt，不能要求它只憑 receipt 才恢復。

| 工作位置／事件 | 採用要求 |
|---|---|
| B1 某窗口未完成、B2 尚未發布 | 驗原工作與 checkpoint 後依既有原生續作；保留已存窗口、輸入、已用預算，不重新 start 或換新工作身分 |
| B2 发布結果遺失 | 依原保存 request／receipt 冪等對帳；是否需原生續作按原流程及位置證據，不重新生成發布意圖 |
| B2 基準被 C 更新 | 沿原 stale→load 與更正來源輸入，在原剩餘預算內處理；不能只換 CAS 版號 |
| 原生狀態不足、未知副作用、預算耗盡 | 明示受阻，保留現場與可用性通知；不能每次啟動清零或每次 tick 無限重試 |
| 詳記重抽 | 原窗口與獨立重抽工作沿原 `reextract`／`resume_reextraction`，不推進正常 B1 輸入位置 |

這是既有流程的移接，不是新增通用重試引擎。LangGraph 的 checkpoint 續作與 AWS 的同一意圖冪等原則支持此區分；並不保證未知副作用可以任意重跑。版本、官方依據與限制見[審查紀錄 §4](evidence/2026-09-13-jd-b1-b2-adoption-review.md)。

### 3.5 何時啟動背景整理

採用既有無參數 `request_memory_consolidation` 及 `MEMORY_ACTION_GUIDANCE`。模型只通知累積訪談值得整理；工具的原生 call/result artifact 表示收到請求，**不執行 B、不寫 Memory、不回報整理完成**。App 在安全終局後辨識 `has_saved_request`，再用 publication 游標判斷哪些請求尚未涵蓋；不得把普通文字、孤立 call 或不匹配 result 當請求。

沒有有效請求且沒有明示啟用的字數後備條件時，不啟動新批次；已存在的未完成工作則走 §3.4。語意請求決定何時開始，不讓模型挑哪些原話可被忽略：批次涵蓋連續、未處理且安全收尾的內容。新 App 的工具註冊、結果分類、關閉與停止路徑都須識別此純通知，不借 JD operation 或 C publication。**十五是 H1–H3 的既有工具清單數，不是 H4 不可增加的上限。**

### 3.6 固定目標到有界批次（2026-09-14 接續設計）

**狀態（2026-09-14）：**本節設計已由 R1 實作並驗證，見[批次接點結果](evidence/jd-b1-adoption/fixed-target-batch-results.md)與[R1 真 PG 結果](evidence/jd-b1-adoption/r1-postgres-batch-results.md)。下文保留原始設計語意；`through_reference` 只放准入列保存的固定 target，不放上一批的 batch ref。
這是尚未接 runtime 的有限缺口，不推翻現有 B1 adapter：`plan_batch()` 現在只回 `{windows, covers_whole_range}`，B1 `start()` 卻需要單一 source ref；舊 `ConversationReader.extraction_batch()` 所做的整批引用投影尚未移接。`unprocessed_source()` 目前只回 `{first_run_id,last_run_id}` bounds，而且沒有契約 §7.1 的 `through_reference` 參數；它是相對目前原話 head 的未處理範圍，不等於某個**已固定 target** 的剩餘範圍。

下一在同一 source owner 補兩個最小公開接點（名稱可依現有 API 慣例調整）：先讓 `unprocessed_source(after_reference, through_reference=None)` 在固定 canonical root 內回連續安全 bounds，並由 owner 發出一個固定的 `purpose="window"` target ref；再由 `plan_saved_batch(target_reference, document_id, *, after_reference=None, max_chars, context_chars, max_windows)` 回 `{source_reference: str | None, covers_whole_range: bool}`。這是 App 內部 port，不是新增 LLM 工具；不可讓 caller 用 first／last 自行拼 token。

- `after_reference` 只取 publication head 的 `processed_source`；`through_reference` 只由准入列保存的固定 target 傳入。兩引用各自驗固定位置、同文件、用途、安全邊界及實際祖先關係。不得因 UUID／時間／最後一個 message ID 相同推定已覆蓋。
- 在 target 原 snapshot 內選連續未處理的前綴，沿既有 `_plan` 最多取 N 窗口；回從該前綴第一個完整回合到最後一個完整回合的 **batch ref**，固定同一 target root。模型不產生任何其中的欄位。
- 已完整涵蓋 target 時回 `source_reference=None, covers_whole_range=True`；有批次時布林表示本批是否涵蓋 target 的全部剩餘範圍，不表示已完成保存／發布。若引用完整相同範圍可原樣返回，避免不必要的 input identity 變動。
- publication cursor 比 target 較晚時，必須沿既有 history owner 證明 target 在其固定有效鏈及覆蓋內才能回「已涵蓋」。缺鏈／超限／分支不明示為來源受限或無效，不回空成功。
- 長 target 分批時保留其尾端；B2 發佈本批後才帶新 publication cursor 求下一批，不需新通知、不換成 latest target。新原話另待後續准入。新 B1 的原生輸入仍是單一 batch ref，不新增另一種 windows 注入模式。
- 舊 `plan_batch()` 可保留為已有測試／規劃介面；runtime 不用它自行拼 token。錯誤與發配沿現有 owner、codec、history；不新增 parser、游標或配對引擎。
- `through_reference` 的 target 是本批要完成的上界；它不前進 publication cursor，也不代表 B1/B2 已成功。若 target 已被 publication 覆蓋，owner 回明確已涵蓋；若 target 分支、缺鏈或超限，回既有 source error，不把 bounds 當空成功。

必驗超過一批、第一批發布後接尾端、追加原話不擴大 target、原 target 已被同鏈游標涵蓋、合法簽章旁支仍拒絕。**這些已在 R1 建立並通過**（另加：較晚但未涵蓋的游標須拒絕、游標與 target 間留有回合須拒絕）；R2 的交接測試仍未做。

## 4. 保持已驗語意不動的部分

- **B1／B2 的 prompt（`INSTRUCTIONS`）逐字不動。**CT49 的逐段觀察（未確認的「印象中」保留、部分回答不擴寫成全未答、更正與矛盾的區分、候選作為下一位整理者的入口）都綁在這兩份 prompt 上。CT49 的 R03／R05／R06 Minor 保留為後續局部校準，**不在採用時順手改 prompt**。
- **兩種內容與短標籤**（`rollout_summary`／`raw_memory`／`rollout_slug` 三個輸出欄位）及格式界線不動。
- **配置分角色沿 CT50／CT51 已測 profile**：A／B2 為每工作 16 模型步／15 工具呼叫的 Agent 限制；B1 為 structured extraction graph，`max_windows=16`、`max_validation_corrections=1`，不是另一個 16／15 工具 Agent。A／B1／B2 effort high、顯式輸出 8192；provider 接線的 native compaction 設定 12000 不等於 B1 有對話 Agent 迴圈。保留共用傳輸／budget 接點及角色差異，不擅用 B1 類別預設 4096 代替驗收入口的顯式 8192。README 須寫明這是本案實測值，不是廠商預設，也不代表換 provider 後自然品質自動相同。
- **JD 相關的新增工具與成稿方法另列差異**，不混進 B1／B2 的已驗語意。

## 5. 顧問指引映射

先採用 `4f94fbfb` 的 A 訪談指引與三項分析 Skills，再將已同意 JD 方法接上新工具；不從後加的 `write-customized-jd` skill 整批複製。

| 已驗來源 | 新接點／必要差異 |
|---|---|
| `api.py` 傳入 `AnalysisService(instructions=...)` 的基本指引 | 新顧問 system：一次優先問一個有用問題、未知不反覆追問、保留主體／條件／本人做法、逐步收尾。只把「目前不製作或編輯 JD」等舊範圍限制改成已同意的 JD 能力；另存精確差異 |
| `work-scope-interview`、`compare-work-patterns`、`outcomes-and-expertise` | 正常套件分析 Skills；保留已驗內容与按需載入、唯讀路由，不要求每輪全讀，不把後加 JD 尾句算進 CT 來源 |
| `SkillAssets`／分析 Skills middleware、`MEMORY_ACTION_GUIDANCE` | 接新 App 已有檔案工具／本輪 context 與 §3.5 通知；核名稱、路徑與實際可讀內容，不只把文檔列入 README |

以下是新增 JD 能力的研究來源，不取代上述已驗顧問方法：

| 來源 | 映射到 |
|---|---|
| [工作完整分析](2026-09-09-complete-work-analysis-guide.md) | 訪談議程與「資料不足追問」的判斷點 |
| [客製化深度與訪談校準](2026-09-09-customized-jd-depth-and-interview-calibration.md) | 何時局部足夠可以撰寫、何時繼續追問 |
| [欄位寫作](2026-09-09-jd-field-and-writing-guide.md) | 十個 JD 工具的欄位寫法，不要求 LLM 填滿內部欄位 |
| [品質門檻](2026-09-10-jd-product-quality-acceptance.md) | 工作→JD／JD→依據的雙向核對與收尾條件 |

最後一輪訪談尚未進 Memory 時，仍核目前對話與原話，沿用已驗顧問的來源使用原則；**將此原則用到完整 JD 收尾是新接點，須另驗，不宣稱 CT49 已驗自然產出 JD。**

## 6. 建議的施工順序

**現行執行順序已由[H4 runtime 計畫](../plans/2026-09-14-jd-h4-runtime-integration.md)收斂。**以下1–5是初稿階段分工沿革；1及2的固定接合已完成，不按其中「下一有限實作」重做。新的有界 batch 與背景狀態接點以 §3.3／3.6 為準。

1. **完成窗口 source port**（§3.1／3.5）：先交 package interface／App adapter 的具體契約及固定情境，再完成有限實作。包含簽章驗證、分頁角色、逐輪終局、整理請求辨識、來源順序／覆蓋；publication 游標不另存。這是 B1 前置，無需為它重開框架廣搜。**契約已交付：**[完成訪談窗口 source port 契約與固定情境](2026-09-13-jd-interview-window-source-contract.md)，含 W-01–W-14 十四個固定情境；下一是依該契約的有限實作，契約本身尚未實作或驗證。
2. **B1 採用**：接來源及必要 package helpers，原 prompt／輸出保持；沿用原窗口、重抽、角色與故障案例，補新引用及同工作續作接合。不是只驗正常抽取。
3. **B2 採用**：沿原發布、stale／RECENT_REPAIRS 與原工作預算，補 C／B2 新來源配對及發布回覆遺失；不另造 Memory writer。
4. **背景接合**：在寫啟停程式前閉合 §3.3 的有限狀態／owner 映射，再接新宿主排空、新程序續作及受阻通知。不以缺回執推定可重跑，也不為零新表硬刪已驗責任。
5. **顧問與整理通知接合**：採用 §5 的 A 指引／分析 Skills，接 §3.5 純通知與新 JD 方法；工具清單由必要能力推導、同步契約與固定 wire 驗收。最後跑零 provider 固定完整旅程，付費／自然驗收另依原授權流程。

## 7. 界線與未決

1. 本稿是映射與差距判定，**沒有任何實作或測試執行**；上表的「沿用案例」是舊 checkout 既有檔案的行數盤點，不是已在新 App 通過的證據。
2. B1／B2 的既有案例綁舊 `ConversationReader` 與舊 service；實際可沿用比例要到接上新 source port 才能確定，本稿不預估百分比。
3. CT49／CT50／CT51 是代表性單一職位及有限續談的真模型驗收，不是所有職位或百輪成功率；採用不會自動延伸該結論。
4. 後加 `sources.py` 增量與 `write-customized-jd` 不整批採用；`4f94fbfb` 已有的方法依 §2／5 採用。目前待實作的是 §3.3／3.6 的批次／背景接合與 B2／通知／宿主驗收，不是重新做已驗來源或顧問。
5. H4 完成條件（零 provider 固定完整旅程可初始化、反覆修正、保留早期工作與案例、重開續談）**尚未開始驗證**；自然品質仍屬 OI-09。
