# Caliburn Consultant Memory

Memory artifact、來源、發布與 Agent staging 的獨立 Python 套件。新 JD App 以一般套件依賴使用；不 import 舊 checkout，不含 JD 編輯、HTTP 入口或宿主排程。最新產品語意依 `MEM-L001`：B1 維護完整案例層，B2 維護穩定工作理解層，兩者完成後才共同發布。舊三欄 extraction／兩檔 consolidation 仍保留已驗來源、checkpoint、錯誤與恢復證據，但不再代表新 B1／B2 的最終產物。provider client、金鑰、角色配置及資源生命週期由 App 組裝。

## 保存與來源

- `MemoryArtifacts` 使用 Deep Agents `StoreBackend`／`CompositeBackend` 保存不可變詳記與準備版本；`ReadOnlyFiles` 提供固定版本讀取。正式內容不寫到操作者的檔案系統。
- `PublicationStore` 以 SQLAlchemy 的版本檢查，將目前版與操作回執寫入同一短交易；重取舊回執不倒退目前版。修補不推進背景整理游標。
- App 提供 `SourceReader(document_id, validate_reference, read, history_exchanges)`。`validate_reference` 只驗格式／簽章／文件範圍，不讀資料庫；`read` 必須讀原先固定的來源，不能換成最新內容；`history_exchanges` 由來源 owner 依固定上界回傳 canonical `oldest_to_newest` 順序。無效地址用 `caliburn_memory.sources.InvalidSourceReference`；來源服務／儲存故障不可轉成該型別。本套件不擁有原始對話，也不另建來源順序索引。
- `caliburn_memory.read_tools.readonly_file_tools(backend)` 提供原生 `ls`／`grep`／`read_file`，不掛檔案 middleware 的訊息 hooks。0.7 不支援 backend factory；App 用公開工具替換接點綁固定 reader，見[工具實證](read-tools-results.md)及[新 App 接合](../../docs/specs/2026-09-13-jd-memory-read-integration-slice.md)。
- 沿用原 `q019-memory` namespace 及 `q019_document_memory_head`／`q019_memory_publication_receipt` 表，沒有另建平行權威。`setup()` 是明示初始化，禁止在一般開啟或每次回合呼叫。

### 分層 Memory bundle 基礎

**2026-09-16：**新增尚未切換 production 的 G4 foundation。`MemoryArtifacts.save_bundle()` 可在同一不可變 `MemoryVersion` 保存 Runtime-owned manifest、案例 guide、逐案例 Markdown、工作理解 guide 與逐理解 Markdown；`case_id`／`understanding_id` 使用 Runtime UUID，manifest 固定來源、內容 digest、多對多 `understanding → case` 精確 binding 及合併／拆分後的 supersession。保存時由 Runtime 另給本次 B1 固定來源上界 `evidence_through_reference`，所有案例引用必須由 source owner 的固定歷史證明並按 owner 順序 canonicalize；不能只因 reference 可讀就納入。`case()`／`understanding()` 按穩定 ID 讀回時同時回傳已驗證來源或案例 binding，不把 manifest 當第三層 Memory。

`manifest.json` 是 Runtime 自行產生與驗證的結構化 JSON，不套用模型 Markdown 正文的單行長度限制；案例／理解正文與 guide 仍沿原文字規則。這只解除結構資料隨案例與 binding 數量自然成長時的錯誤限制，不改 manifest schema、舊版本解析或 publication digest 的 canonical 計算。

`PublicationStore` 沿用原 head／receipt／CAS，另拒絕候選 bundle 的 `base_publication_revision` 或精確 base `MemoryVersion` 與目前 head 不一致。foundation 當時仍讓舊兩檔 `knowledge.md`／`guide.md` request digest 與讀寫路徑通過歷史相容測試；依 2026-09-17 Owner 決定，這已不是正式新 App 的產品需求，後續 layered C 切片不得繼續暴露雙格式，legacy 程式與測試只作有界清理前的歷史證據。這一段只有資料 authority、保存與驗證，沒有改 B1／B2 Prompt、舊 staging／repair、dispatcher、UI 或 production authority。完整語意與後續切片見 [MEM-L001](../../docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md)。

### B1 案例 staged state／證據 registry／固定 canonical batch Agent graph

`caliburn_memory.case_maintenance` 已完成零 provider 的 B1 stage、Agent graph 與 evidence registry 切片：`CaseMaintenanceStage` 保存固定 base、canonical source、本 attempt 已讀案例、目前 staged upserts／supersessions／guide、change set，以及 attempt-scoped `evidence_key → signed source`、owner order proof 和 Runtime paging cursor。stage 只保存 reference 與 message ID／role，不複製訪談原話。模型不填 document、signed reference、offset、cursor、版本、路徑、digest 或新案例 ID。

修訂、拆分、合併或淘汰已發布案例前必須先成功 `read_case`；它會從固定訪談歷史重新證明案例所有引用的 canonical 順序，再回傳 `oldest_to_newest` evidence blocks。證明不到任何一筆即拒絕，不能相信 artifact tuple 或 reference 字典序。模型可用無參數 `browse_interview_history` 取得下一批安全歷史，也可用 `read_more_evidence(evidence_key)` 續讀長來源；兩者的 offset 都由 checkpoint 管理。同一模型步的多工具呼叫仍全部拒絕，避免平行 state update。

`CaseMaintenanceWorkflow` 已將 Runtime 固定的整批 canonical source 接到新 B1 Prompt 與上述工具。這個 batch 是語意整理與 `processed_source` 單位，不是案例引用；正式 App 能在實際 request 預算內完整提供時應使用單一來源窗口，只有來源或模型限制確實需要時，來源 owner 才在同一 batch 內提供多個有界 `NEW_SOURCE.window`／`CONTEXT_ONLY` 讀取窗口。每個 `NEW_SOURCE` 另帶 owner 排序的完整問答 evidence blocks，所有窗口共用同一 registry 與 staged attempt。若使用多窗口，非最後窗口不能提前完成，最後窗口必須明確 `changed`／`no_op`；模型與工具額度、完成修正、incomplete／refusal 防護及工具後 transport failure 的原 checkpoint resume 都由 graph 保留。窗口並非案例邊界或產品要求，package 的 `max_chars`／`max_windows` 也不是正式 App 的固定切割規則。

create／revise／split／merge 已使用 attempt registry 做精確 evidence 分配：模型只選 Runtime 已展示的短 keys，Runtime 解析、驗證並依 source owner 順序 canonicalize 正式 signed references。create 提交完整引用集合；revise 只送 add/remove 差異且可做純引用修補；split 為每個 replacement 分配完整集合並明示未沿用舊證據的理由；merge 從既有聯集套用差異。`finish_case_maintenance()` 不收 outcome，由 Runtime 計算 `changed/no_op`。guide link、穩定 UUID 與 supersession 仍由 Runtime 產生；這些結果仍是 staged，尚未發布新 bundle。

B1 正常以一個完整 canonical 訪談 batch 工作，不固定呼叫 compaction。若來源交付實際分成多個窗口，目前尚未完整處理的最新窗口必須逐字保留；已完整交付、其模型／工具 wave 安全完成且 Runtime checkpoint 已推進的舊窗口，才可在後續 request view 中像 A 的舊對話一樣被 continuity compaction。原始訪談、signed references 與 evidence registry 仍由來源 owner／checkpoint 完整保存並可按需回查；continuity summary 只作工作延續 Context，不能當案例證據、Memory 或 JD basis。

這仍是 package 內的 B1 候選；目前已由 `BackgroundMemoryWorkflow` 與 B2 staged result 組成同一完整 bundle 後一次發布。後續 App 已從精確注入的 B1 role model 與明示 output reserve 建立 request-only compaction middleware；package 只接受 middleware 並攜帶 state，不選 provider。正式 OpenRouter／Luna role factory、managed callback 與 layered C 已完成各自離線切片；UI、provider／自然模型、完整瀏覽器 App journey 及 production authority 仍未完成。完整語意、驗收及下一接點見 [MEM-L001](../../docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md)及[B1 前兩施工切片](../../docs/plans/2026-09-16-b1-case-maintainer.md)。

### Ordered evidence source port（App 接點與 B1 stage 已接）

`caliburn_memory.sources` 現提供 immutable typed evidence records：固定 window 內的逐輪 records、以同一 window 為上界的安全歷史分頁，以及 exact `source` 的有界文字頁。records 只含 signed reference 與 message ID／role；App source owner 才擁有 canonical order、lineage 與原文，adapter 不重排、不重簽、不建立第二份索引。B1 與 B2 stage 已消費這些 port 並保存 attempt-scoped key／order proof／Runtime paging cursor；offset 不是模型參數或持久 citation。B1 create／revise／split／merge 的精確引用分配、bundle 保存時的 owner-order 再驗證，以及 B2 case-bound exact-source key 工具均已依[引用施工計畫](../../docs/plans/2026-09-17-interview-evidence-citations.md) Task 5 接入。

### B2 工作理解 staged state／語意工具／durable Agent graph

`caliburn_memory.understanding_maintenance` 與 `understanding_workflow` 已完成兩個零 provider 切片。`UnderstandingMaintenanceSession` 固定一份 completed B1 stage 與 exact base bundle，從 B1 semantic case changes 及 base `understanding → case` bindings 自動推導必讀的 candidate cases 與直接受影響 understandings；模型不能提供或縮小 impact set。新案例即使沒有反向 binding 仍是必讀項目，讓 B2 判斷是否揭露新的穩定工作理解。

Runtime 另可把 publication receipts 推導出的既有 C repair impact 加入同一 required-ID gate；它只能增加目前有效的案例／理解，不能移除 B1 自己推導的要求。同一 durable attempt 恢復時會核對最終 required tuples，避免用同一 attempt ID 偷換修補影響；stage schema 沒有新增模型可填的 repair 欄位。

十個窄語意工具提供 case／understanding 讀取，以及 create、revise、revalidate、split、merge、retire、route、finish；另有兩個窄 workflow 工具處理 case-bound 原話分頁與要求 B1 rework。已發布理解採 read-before-write；所有 support case 必須屬於同一 B1 candidate 且已實際讀取。`revalidate_work_understanding` 讓正文語意不變時明確更新支持案例，binding-only refresh 不建立假正文修改；零參數 `finish_understanding_maintenance()` 仍要求變更案例已讀、直接受影響理解已 revise／revalidate／supersede／retire，`changed/no_op` 由 Runtime 從 staged 變更計算，避免只換 digest 或漏掉新案例。Runtime 擁有 UUID、guide route、scope、base 與後續 digest。

`UnderstandingMaintenanceWorkflow` 以新 B2 Prompt 接上同一 stage／tools、response guard、thread-scoped 模型／工具額度與 durable checkpoint。初始 request 只帶 base revision、兩份 guide、B1 change set 及 Runtime 推導的必讀 ID，不預載案例正文、工作理解正文或原始訪談。模型按需讀取案例與理解；`read_case` 只顯示該案例 owner-ordered、attempt-scoped 的 `evidence_key` 與角色形狀，不洩漏 signed reference 或原文。只有先讀案例後，模型才能選該案例的 key，由 Runtime 解析固定 reference 與 cursor 並有界讀取原話。來源讀取證據以 `(case_id, source_reference)` 配對保存，不能把同一來源在案例 A 的核對冒充案例 B 已核對；同一 signed reference 在不同案例會得到不同 key。

若原話只補足細節，B2 繼續整理；若原話證明 B1 有會影響工作理解的實質錯誤或缺漏，`request_case_rework` 只收已讀 `evidence_key` 與理由，由 Runtime 寫入正式 case／reference 配對並以結構化 `case_rework_required` 結束 attempt。該結果不能交給 `current_understandings()` 或 publication；B2 不改案例，也不自行重跑 B1。所有 B2 工具 schema 都拒絕模型填入 document、signed reference、offset、版本與 outcome；目前已驗的是 Runtime／ToolNode 的 strict 拒絕，OpenRouter wire-level strict 尚未證明。這一片已驗 changed、semantic no-op／完整 binding 重驗、按案例限制的來源讀取、rework terminal、同輸入冪等、新 B1 attempt 清除舊訊息、transport resume、完成修正及 incomplete／refusal／額度防護。

B2 本身仍不越權重跑 B1 或發布；package 外層 `BackgroundMemoryWorkflow` 現已消費這個 terminal，建立新 B1／B2 attempt，並在最多一次返工後發布或 blocked。後續 App 已用精確注入的 B2 role model 組裝 request-only middleware：同一 attempt 固定第一個 task message 並恢復 `continuation_compaction`，新的 stale attempt 從空 state 開始。正式 role factory、managed callback 與 layered C 已完成各自離線切片；provider／自然模型、完整瀏覽器 App journey 及 production authority 仍未完成。完整契約與結果見 [B2 staged maintainer 計畫](../../docs/plans/2026-09-16-b2-understanding-maintainer.md)、[B2 Agent graph 計畫](../../docs/plans/2026-09-16-b2-understanding-agent.md)及[完整背景 workflow 設計](../../docs/specs/2026-09-17-layered-memory-background-workflow-design.md)。

### 分層完整背景 workflow（package 已完成）

`caliburn_memory.background_workflow.BackgroundMemoryWorkflow` 是純 Runtime 的 document-scoped durable graph：先由 source owner 判定固定 batch 對目前 publication cursor 是 `covered` 或真正的 `next`，再依同一 exact base 執行 B1、B2、組裝完整 bundle、checkpoint 完整 `PublishRequest`，最後才呼叫既有 `PublicationStore.publish()`。它不尋找 latest conversation、不新增第三個 LLM orchestrator，也不重算 B1／B2 語意規則。

B2 回報 `case_rework_required` 時，outer Runtime 從被拒 B1 stage 取得當時案例正文，把 B2 的 case/source/reason 轉成非員工證據的 `CaseRuntimeReview`，配置新 `case_attempt_id` 後最多重跑一次 B1→B2。正式 base 案例可保留 ID 修正；未發布 candidate ID 只作 locator，若保留內容須由新 B1 建立新 ID。每個 review 指向的 canonical source 必須完整重讀；第二次 rework 以 `case_rework_limit_reached` blocked，不發布。

CAS stale 時舊 stages、candidate 與 request 不會換版重送；Runtime 保留 source 與 rework 次數、增加有界 stale counter，重新取得 head。若新 cursor 已涵蓋來源，直接回正式 head；只有 source owner 證明為 `next` 才建立新的 B1／B2 semantic attempts。`PublicationUncertain` 不配置新 operation：outer checkpoint 保留原 `PublishRequest`，resume 以相同 operation／digest 由 receipt 查回。所有 outer `invoke` 使用同步 durability。

背景工作固定 base 後，還會把最近一次成功 consolidation 之後、該 base 以前的 repair receipts 視為尚待背景重新分析的 durable delta。Runtime 沿每筆 result manifest 的精確 base version 比較修補前後案例 digest、理解 digest 與完整 bindings；舊／新 bindings 都參與，結果與本次 B1 impact 聯集後交給既有 B2 gate。B1 即使 `no_op` 也不會抹掉這份影響；成功 consolidation receipt 自然成為下一個邊界，不另建 watermark、queue、Agent 或資料表。這個接點不放寬 C 當次完整 publication；layered C 現已沿相同 receipt 流進入後續對帳。

本 workflow 自身的證據是固定模型＋real package sessions／Store＋SQLite publication 的離線契約測試，以及相鄰 App source-owner 測試；後續 App 窄切片另有 PostgreSQL／新程序資源恢復證據。2026-09-18 layered C 完成後，package 全套為 **281 passed**，相鄰 App 受影響範圍為 **270 passed**；其中 A/B/C→U 反例證明 B1 `no_op` 時仍從舊／新 binding 把 C 與 U 送入 B2。這些仍是離線契約證據；provider wire／自然模型品質及完整瀏覽器 App journey 尚未通過，也不等同完整瀏覽器下 publication／JD byte-for-byte 驗收。

## 分層 C 即時修補（已完成離線切片）

layered C 是例外性的 live repair，不是日常 Memory writer。A 只有在已讀 latest publication 的既有案例／工作理解及必要 canonical-ordered 引用、使用者已在當輪或已核對的 canonical 原話中明確指出目前哪項內容錯誤與正確適用範圍、目標 stable ID 唯一、當輪後續確實依賴修正版，而且所有直接影響可以有界完整處理時，才能提出修補。歷史原話互相矛盾但尚未裁決、普通補充、較新的敘述或模型推測時必須先詢問；真正新案例／理解、split／merge／supersede 及廣泛跨案例重整交給 B1／B2。

C 第一版只處理 existing stable IDs。案例修訂使用 Runtime 已提供／已讀的 evidence key，由 source owner 解析、驗證並按 canonical order 保存 signed references；工作理解只綁定同一候選 bundle 中的 `case_id＋case_digest`，不能把原話越層保存為理解 citation。明確更正若同時影響既有案例與可完整辨認的既有理解，理解正文已錯就 revise，正文仍正確則 revalidate 並刷新修訂後案例 digest；兩層在同一完整 bundle 一次 CAS，不製造假正文變更。影響不明或無法完整處理就整次拒絕，不發布半套結果。真正新內容由 canonical conversation／Working State 承接，再由 B1 建案例、B2 建立或修訂理解。

`LayeredRepairWorkflow` 沿既有 B1／B2 maintenance session 完成 `seed → edit* → validate → save → prepare → publish`；App 只從本回合已保存的 `read_case`、完整 `read_conversation` 與 `read_work_understanding` 結果建立 read proof，再把模型 evidence key 解析成 canonical source。正式工具不接受 signed reference、revision、version、digest、path、offset 或 operation ID。latest 已變時在解析舊修改前回 stale；成功 publication 的原 START／request／receipt 可恢復，並只把本回合讀取基準推進到該次 applied head。legacy 兩檔程式只留給既有歷史 checkpoint／測試證據，不在正式 schema、分層提示或 model-facing result 暴露。

OpenAI 公開 Sandbox Memory 將 live update 描述為修正 stale Memory 或依使用者要求更新，另在 run 結束後做 extraction／consolidation；本契約沿用這個窄即時修補與背景整理的責任形狀，但 stable IDs、案例→理解引用與完整 bundle publication 是 Caliburn 的產品映射。[OpenAI Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)、[MEM-L001](../../docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md)。

## 舊即時修補核心（歷史工程證據；正式產品契約已取代）

**2026-09-13：**新增公開 `build_repair_graph(resolve_workflow)`，供 App 固定 wrapper 在執行時取得同輪資源；`RepairWorkflow.graph` 共用同一六節點，未另寫引擎。建圖與檢視不執行 resolver、不開任何資源。`adoption.json` 已記此版實際 hash，wheel 在乾淨 venv 依 App lock 完成完整依賴安裝並通過隔離檢查，詳見[App 接合結果](../../docs/specs/2026-09-13-jd-memory-repair-app-integration-slice.md)。

`caliburn_memory.repair.RepairWorkflow(artifacts, publication, source).graph` 沿原生六節點子圖與呼叫者 Saver；`StateBackend` 暫存兩個 Memory 檔案，官方 `agents.apply_diff` 完整成功後才寫入暫存，整批驗證後才由原 PublicationStore 發布。詳見[修補採用與結果](../../docs/specs/2026-09-13-jd-memory-repair-core-slice.md)。

歷史接法由 App 配發 operation／base／source，模型只提供 path／diff；本核心不自動准入、不啟動模型或背景工作。`reconcile(original_request: PublishRequest)` 只核對原生已保存請求的回執與目前版；不收 caller edits、不重播修補，沒有回執仍屬未知。回執證明發布內容，原 patch 文字須由 App 的原工具呼叫證明，兩者不互相代替。依 2026-09-17 Owner 決定，正式新 App 不再使用這個兩檔 path／diff 契約；layered C 改用 stable-ID 受控修訂與完整 bundle publication。此段只記已驗工程沿革，不能作正式工具 schema。

程式採用來源、hash 與實際調整見 [adoption.json](adoption.json)；三核心僅分離來源依賴，沒有重寫 Memory 引擎。[完整接合設計與結果](../../docs/specs/2026-09-13-jd-memory-core-adoption-slice.md)保存官方依據、限制與驗證層級。

## 舊 B1 訪談抽取核心（底層證據，產品語意已取代）

`caliburn_memory.extraction.ExtractionWorkflow` 已自 `4f94fbfb` 採用。三文字欄位、prompt、窗口迴圈、格式更正額度、`start/resume/reextract` 保持已驗語意；`ExtractionSourceReader` 由 App 提供固定窗口與前置消歧，`accepted(raw)` 由 provider adapter 核拒絕／終局。新 B1 已沿用其來源固定、窗口 pair、checkpoint、拒答／截斷與有限恢復原則；舊三欄輸出與「保存詳記／候選即完成」仍只作底層證據，不能接成新案例層的正式完成條件。

歷史採用切片中，App `extraction_app.py` 的固定接合及真 `PostgresSaver`／`PostgresStore` 一批保存、資源重建後續作、重抽與相同 input 查回已驗（[R1 結果](../../docs/specs/evidence/jd-b1-adoption/r1-postgres-batch-results.md)）。這證明可沿用的底層能力，不代表新 B1 已接 App。

## 舊 B2 兩檔整併核心（底層證據，產品語意已取代）

`caliburn_memory.consolidation.ConsolidationWorkflow` 已自 `4f94fbfb` 採用。`JobState`、`stale→load`、模型／工具／輸出／候選／修補預算、`_repair_input`、由產物推導的 `_operation_id` 與 publish／receipt 路徑仍是可沿用工程證據。舊 Prompt、兩個固定檔案 staging 與「B1 artifact 直接交 B2 發布兩檔 Memory」已由 `MEM-L001` 取代；新 B2 必須消費 staged current cases、處理多對多影響並和 B1 一次發布，不能直接復用這個產品流程。

歷史流程唯一 provider 接縫是 `context_middleware=`；舊 B2 從已完成的舊 B1 checkpoint 取 `files`、推進 `processed_source`，而 C 不推進背景游標。這些 provider 分離、游標與恢復原則可沿用，`files`／兩檔 Memory 的產品形狀不可沿用。

歷史 App adapter 在真 `PostgresSaver`／`PostgresStore`／publication 上驗過兩批有序交接、pending 續作、發布回覆遺失查回與 C 較晚更正（[R2 結果](../../docs/specs/evidence/jd-b1-adoption/r2-consolidation-handover-results.md)）。新分層流程仍須在後續 B1／B2 完整背景工作重新接合；不得把這份舊 R2 證據冒稱新 bundle 已發布通過。

## 顧問方法資產

`caliburn_memory.skills` 與三項分析 Skills（`work-scope-interview`／`compare-work-patterns`／`outcomes-and-expertise`）已自 `033540ce` **位元組相同**採用；`SkillAssets` 只讀，沒有 write／edit／delete／execute，`upload_files` 不實作。`analysis_skills(SkillAssets())` 以官方 Skills middleware 把方法**名稱、用途與讀取路徑**放進 system prompt，SKILL.md 內文由模型按需以既有 `read_file` 讀取，不每輪全載。後加的 `write-customized-jd` **不採用**。

`caliburn_memory.guidance.MEMORY_ACTION_GUIDANCE` 的背景通知段逐字保留已驗內容，live-repair 段則已替換為上方分層 C 契約；測試會逐字比對背景段，避免接線時改壞既有通知判斷。`repair_memory` 與 `request_memory_consolidation` 都由本套件提供；新內容仍交 B1／B2。舊 `live_memory.py` 的其餘部分是舊 host 組裝，不採用。

wheel 已含這些 `.md` 資產（`uv build` 後於 `caliburn_memory/skills/*/SKILL.md` 可見）。

## 安裝與驗證

Python 3.12。App 的 `uv.lock` 固定實測組合；獨立 wheel 由 Hatchling 產生。B2 直接使用 `langchain` 的 Agent 與中介 API，故 `langchain==1.4.0` 已明示宣告，不再只靠 Deep Agents 的傳遞依賴。

```powershell
# 在 experiments/jd-relational-app 使用其正式本地依賴
uv sync --frozen
uv run --offline --frozen --no-sync pytest -c pyproject.toml ../../packages/consultant-memory/tests -q -p no:cacheprovider

# 在本套件目錄建 wheel，輸出至指定暫存目錄
uv build --out-dir ../../.research-tmp/jd-memory-core-dist
```

Deep Agents 的標準 distribution 會連帶安裝 Anthropic／Google 等 provider 套件；OpenAI Agents SDK 0.22.0 提供公開純文字 patch 函式，patch／保存核心不建立 provider；B1 執行由 App 注入的模型 runnable。未為減少套件數自行複製框架 backend 或 matcher。此次新增 SDK 及其相依共八包，原 App 既有套件無升降；後續按具體相容性驗證，不追逐版本號。

目前最新分層 bundle authority、完整回合引用、B1／B2 staged Agent graphs、durable attempts、外層 B1→B2 有界 rework／共同 publication／stale recovery，以及分層 C bundle repair 已在 package 完成；App 已完成 A 分層讀取、C read-proof／tool／recovery、B1／B2 request-only compaction、正式 OpenRouter／Luna role factory及 managed callback 的各自離線切片。summary 只是非權威 Context，canonical source、signed references 與 evidence registry 仍可查且具權威。**provider／自然模型、完整瀏覽器 App journey 與 production authority 仍未完成**；不要把 package、compaction 或組裝測試代稱新分層流程已可日常使用，也不能宣稱完整瀏覽器下 publication／JD byte-for-byte invariance或自然模型品質已驗。
