# Caliburn Consultant Memory

Memory artifact、來源、發布與 Agent staging 的獨立 Python 套件。新 JD App 以一般套件依賴使用；不 import 舊 checkout，不含 JD 編輯、HTTP 入口或宿主排程。最新產品語意依 `MEM-L001`：B1 維護完整案例層，B2 維護穩定工作理解層，兩者完成後才共同發布。舊三欄 extraction／兩檔 consolidation 仍保留已驗來源、checkpoint、錯誤與恢復證據，但不再代表新 B1／B2 的最終產物。provider client、金鑰、角色配置及資源生命週期由 App 組裝。

## 保存與來源

- `MemoryArtifacts` 使用 Deep Agents `StoreBackend`／`CompositeBackend` 保存不可變詳記與準備版本；`ReadOnlyFiles` 提供固定版本讀取。正式內容不寫到操作者的檔案系統。
- `PublicationStore` 以 SQLAlchemy 的版本檢查，將目前版與操作回執寫入同一短交易；重取舊回執不倒退目前版。修補不推進背景整理游標。
- App 提供 `SourceReader(document_id, validate_reference, read)`。`validate_reference` 只驗格式／簽章／文件範圍，不讀資料庫；`read` 必須讀原先固定的來源，不能換成最新內容。無效地址用 `caliburn_memory.sources.InvalidSourceReference`；來源服務／儲存故障不可轉成該型別。本套件不擁有原始對話。
- `caliburn_memory.read_tools.readonly_file_tools(backend)` 提供原生 `ls`／`grep`／`read_file`，不掛檔案 middleware 的訊息 hooks。0.7 不支援 backend factory；App 用公開工具替換接點綁固定 reader，見[工具實證](read-tools-results.md)及[新 App 接合](../../docs/specs/2026-09-13-jd-memory-read-integration-slice.md)。
- 沿用原 `q019-memory` namespace 及 `q019_document_memory_head`／`q019_memory_publication_receipt` 表，沒有另建平行權威。`setup()` 是明示初始化，禁止在一般開啟或每次回合呼叫。

### 分層 Memory bundle 基礎

**2026-09-16：**新增尚未切換 production 的 G4 foundation。`MemoryArtifacts.save_bundle()` 可在同一不可變 `MemoryVersion` 保存 Runtime-owned manifest、案例 guide、逐案例 Markdown、工作理解 guide 與逐理解 Markdown；`case_id`／`understanding_id` 使用 Runtime UUID，manifest 固定來源、內容 digest、多對多 `understanding → case` 精確 binding 及合併／拆分後的 supersession。`case()`／`understanding()` 按穩定 ID 讀回時同時回傳已驗證來源或案例 binding，不把 manifest 當第三層 Memory。

`PublicationStore` 沿用原 head／receipt／CAS，另拒絕候選 bundle 的 `base_publication_revision` 或精確 base `MemoryVersion` 與目前 head 不一致；舊兩檔 `knowledge.md`／`guide.md` request digest 與讀寫路徑保持相容。這一段只有資料 authority、保存與驗證，沒有改 B1／B2 Prompt、舊 staging／repair、dispatcher、UI 或 production authority。完整語意與後續切片見 [MEM-L001](../../docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md)。

### B1 案例 staged state／語意工具／固定 canonical batch Agent graph

`caliburn_memory.case_maintenance` 已完成兩個零 provider 切片：`CaseMaintenanceStage` 保存固定 base、canonical source、本 attempt 已讀案例、目前 staged upserts／supersessions／guide 與 change set；`case_maintenance_tools()` 提供 `read/create/revise/split/merge/retire/set-route/finish` 八個窄工具。模型不填 document、來源、版本、路徑、digest 或新案例 ID。

修訂、拆分、合併或淘汰已發布案例前必須先成功 `read_case`，該證據與 stage 一起由 LangGraph checkpoint 保存；同一模型步的多工具呼叫全部拒絕，避免平行 state update。局部修訂沿既有 V4A matcher，但只接收案例內容與 diff，不把儲存 path 暴露給模型。新案例與修訂案例的來源由 Runtime 自動綁定；guide link、穩定 UUID 與 supersession 同樣由 Runtime 產生。

`CaseMaintenanceWorkflow` 已將 Runtime 固定的整批 canonical source 接到新 B1 Prompt 與上述工具。這個 batch 是語意整理與來源單位；正式 App 能在實際 request 預算內完整提供時應使用單一來源窗口，只有來源或模型限制確實需要時，來源 owner 才在同一 batch 內提供多個有界 `NEW_SOURCE`／`CONTEXT_ONLY` 讀取窗口。所有窗口共用一個 staged attempt，只有整批 source 成為案例證據。若使用多窗口，非最後窗口不能提前完成，最後窗口必須明確 `changed`／`no_op`；模型與工具額度、完成修正、incomplete／refusal 防護及工具後 transport failure 的原 checkpoint resume 都由 graph 保留。窗口並非案例邊界或產品要求，package 的 `max_chars`／`max_windows` 也不是正式 App 的固定切割規則。

B1 的 canonical 訪談 batch 是受保護來源：之後的 request-only compaction 不得摘要、截斷或替換它，也不能把 continuity summary 當作案例證據。compaction 只能處理 B1 自己已安全完成的舊模型／工具往返；原始訪談由來源 owner 持續完整保存。

這仍只是 package 內的 B1 候選：沒有 B2、共同 publication、正式 App model factory、dispatcher、compaction、UI 或自然模型驗收。完整語意、驗收及下一接點見 [MEM-L001](../../docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md)及[B1 前兩施工切片](../../docs/plans/2026-09-16-b1-case-maintainer.md)。

### B2 工作理解 staged state／語意工具／durable Agent graph

`caliburn_memory.understanding_maintenance` 與 `understanding_workflow` 已完成兩個零 provider 切片。`UnderstandingMaintenanceSession` 固定一份 completed B1 stage 與 exact base bundle，從 B1 semantic case changes 及 base `understanding → case` bindings 自動推導必讀的 candidate cases 與直接受影響 understandings；模型不能提供或縮小 impact set。新案例即使沒有反向 binding 仍是必讀項目，讓 B2 判斷是否揭露新的穩定工作理解。

十個窄工具提供 case／understanding 讀取，以及 create、revise、revalidate、split、merge、retire、route、finish。已發布理解採 read-before-write；所有 support case 必須屬於同一 B1 candidate 且已實際讀取。`revalidate_work_understanding` 讓正文語意不變時明確更新支持案例，binding-only refresh 不建立假正文修改；`finish(no_op)` 仍要求變更案例已讀、直接受影響理解已 revise／revalidate／supersede／retire，避免只換 digest 或漏掉新案例。Runtime 擁有 UUID、guide route、scope、base 與後續 digest。

`UnderstandingMaintenanceWorkflow` 以新 B2 Prompt 接上同一 stage／tools、response guard、thread-scoped 模型／工具額度與 durable checkpoint。初始 request 只帶 base revision、兩份 guide、B1 change set 及 Runtime 推導的必讀 ID，不預載案例正文、工作理解正文或原始訪談。模型按需讀取案例與理解；只有先讀案例後，才能沿該案例實際列出的 canonical reference 分頁核對原話。來源讀取證據以 `(case_id, source_reference)` 配對保存，不能把同一批來源在案例 A 的核對冒充案例 B 已核對。

若原話只補足細節，B2 繼續整理；若原話證明 B1 有會影響工作理解的實質錯誤或缺漏，`request_case_rework` 以結構化 `case_rework_required` 結束 attempt。該結果不能交給 `current_understandings()` 或 publication；B2 不改案例，也不自行重跑 B1。這一片已驗 changed、semantic no-op／完整 binding 重驗、按案例限制的來源讀取、rework terminal、同輸入冪等、新 B1 attempt 清除舊訊息、transport resume、完成修正及 incomplete／refusal／額度防護。

這仍沒有 B1→B2 自動重跑、共同 publication、stale 重整、dispatcher、compaction、App 組裝或自然模型驗收。完整契約與結果見 [B2 staged maintainer 計畫](../../docs/plans/2026-09-16-b2-understanding-maintainer.md)及[B2 Agent graph 計畫](../../docs/plans/2026-09-16-b2-understanding-agent.md)。

## 即時修補核心

**2026-09-13：**新增公開 `build_repair_graph(resolve_workflow)`，供 App 固定 wrapper 在執行時取得同輪資源；`RepairWorkflow.graph` 共用同一六節點，未另寫引擎。建圖與檢視不執行 resolver、不開任何資源。`adoption.json` 已記此版實際 hash，wheel 在乾淨 venv 依 App lock 完成完整依賴安裝並通過隔離檢查，詳見[App 接合結果](../../docs/specs/2026-09-13-jd-memory-repair-app-integration-slice.md)。

`caliburn_memory.repair.RepairWorkflow(artifacts, publication, source).graph` 沿原生六節點子圖與呼叫者 Saver；`StateBackend` 暫存兩個 Memory 檔案，官方 `agents.apply_diff` 完整成功後才寫入暫存，整批驗證後才由原 PublicationStore 發布。詳見[修補採用與結果](../../docs/specs/2026-09-13-jd-memory-repair-core-slice.md)。

App 配發 operation／base／source，模型只提供 path／diff；本核心不自動准入、不啟動模型或背景工作。`reconcile(original_request: PublishRequest)` 只核對原生已保存請求的回執與目前版；不收 caller edits、不重播修補，沒有回執仍屬未知。回執證明發布內容，原 patch 文字須由 App 的原工具呼叫證明，兩者不互相代替。C 只改 Memory，不撤回原話或 JD；較晚背景版可作明示修補回覆的讀取版，原操作的 applied head 保留。

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

`caliburn_memory.guidance.MEMORY_ACTION_GUIDANCE` 逐字採用（`instructions_sha256`），描述的 `repair_memory` 與 `request_memory_consolidation` 都由本套件提供。舊 `live_memory.py` 的其餘部分是舊 host 組裝，不採用。

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

目前最新分層 bundle authority、B1 staged state／語意工具／固定 canonical batch Agent graph，以及 B2 staged state／語意工具／durable Agent graph 已完成；舊 publication CAS／receipt 與顧問方法資產保留作接續基礎。**B1→B2 有界 rework orchestration／共同發布、C bundle repair、正式 App model factory／dispatcher、B1 compaction 與完整 App 旅程仍未完成**；不要把 package 測試、舊 B1／B2 真 PG 證據或固定組裝測試代稱新分層流程已可日常使用，也不能宣稱新流程自然品質已驗。
