# Caliburn Consultant Memory

工作詳記、目前工作理解／導覽、發布與已採用 Memory 工作流程的獨立 Python 套件。新 JD App 以一般套件依賴使用；不 import 舊 checkout，不含 JD 編輯、HTTP 入口或宿主排程。B1 會執行 App 注入的 structured runnable，B2 會執行 App 注入的 chat model 與 context 中介；provider client、金鑰、角色配置及資源生命週期由 App 組裝。

## 保存與來源

- `MemoryArtifacts` 使用 Deep Agents `StoreBackend`／`CompositeBackend` 保存不可變詳記與準備版本；`ReadOnlyFiles` 提供固定版本讀取。正式內容不寫到操作者的檔案系統。
- `PublicationStore` 以 SQLAlchemy 的版本檢查，將目前版與操作回執寫入同一短交易；重取舊回執不倒退目前版。修補不推進背景整理游標。
- App 提供 `SourceReader(document_id, validate_reference, read)`。`validate_reference` 只驗格式／簽章／文件範圍，不讀資料庫；`read` 必須讀原先固定的來源，不能換成最新內容。無效地址用 `caliburn_memory.sources.InvalidSourceReference`；來源服務／儲存故障不可轉成該型別。本套件不擁有原始對話。
- `caliburn_memory.read_tools.readonly_file_tools(backend)` 提供原生 `ls`／`grep`／`read_file`，不掛檔案 middleware 的訊息 hooks。0.7 不支援 backend factory；App 用公開工具替換接點綁固定 reader，見[工具實證](read-tools-results.md)及[新 App 接合](../../docs/specs/2026-09-13-jd-memory-read-integration-slice.md)。
- 沿用原 `q019-memory` namespace 及 `q019_document_memory_head`／`q019_memory_publication_receipt` 表，沒有另建平行權威。`setup()` 是明示初始化，禁止在一般開啟或每次回合呼叫。

### 分層 Memory bundle 基礎

**2026-09-16：**新增尚未切換 production 的 G4 foundation。`MemoryArtifacts.save_bundle()` 可在同一不可變 `MemoryVersion` 保存 Runtime-owned manifest、案例 guide、逐案例 Markdown、工作理解 guide 與逐理解 Markdown；`case_id`／`understanding_id` 使用 Runtime UUID，manifest 固定來源、內容 digest、多對多 `understanding → case` 精確 binding 及合併／拆分後的 supersession。`case()`／`understanding()` 按穩定 ID 讀回時同時回傳已驗證來源或案例 binding，不把 manifest 當第三層 Memory。

`PublicationStore` 沿用原 head／receipt／CAS，另拒絕候選 bundle 的 `base_publication_revision` 或精確 base `MemoryVersion` 與目前 head 不一致；舊兩檔 `knowledge.md`／`guide.md` request digest 與讀寫路徑保持相容。這一段只有資料 authority、保存與驗證，沒有改 B1／B2 Prompt、舊 staging／repair、dispatcher、UI 或 production authority。完整語意與後續切片見 [MEM-L001](../../docs/specs/2026-09-16-layered-case-and-work-understanding-memory-alignment.md)。

## 即時修補核心

**2026-09-13：**新增公開 `build_repair_graph(resolve_workflow)`，供 App 固定 wrapper 在執行時取得同輪資源；`RepairWorkflow.graph` 共用同一六節點，未另寫引擎。建圖與檢視不執行 resolver、不開任何資源。`adoption.json` 已記此版實際 hash，wheel 在乾淨 venv 依 App lock 完成完整依賴安裝並通過隔離檢查，詳見[App 接合結果](../../docs/specs/2026-09-13-jd-memory-repair-app-integration-slice.md)。

`caliburn_memory.repair.RepairWorkflow(artifacts, publication, source).graph` 沿原生六節點子圖與呼叫者 Saver；`StateBackend` 暫存兩個 Memory 檔案，官方 `agents.apply_diff` 完整成功後才寫入暫存，整批驗證後才由原 PublicationStore 發布。詳見[修補採用與結果](../../docs/specs/2026-09-13-jd-memory-repair-core-slice.md)。

App 配發 operation／base／source，模型只提供 path／diff；本核心不自動准入、不啟動模型或背景工作。`reconcile(original_request: PublishRequest)` 只核對原生已保存請求的回執與目前版；不收 caller edits、不重播修補，沒有回執仍屬未知。回執證明發布內容，原 patch 文字須由 App 的原工具呼叫證明，兩者不互相代替。C 只改 Memory，不撤回原話或 JD；較晚背景版可作明示修補回覆的讀取版，原操作的 applied head 保留。

程式採用來源、hash 與實際調整見 [adoption.json](adoption.json)；三核心僅分離來源依賴，沒有重寫 Memory 引擎。[完整接合設計與結果](../../docs/specs/2026-09-13-jd-memory-core-adoption-slice.md)保存官方依據、限制與驗證層級。

## B1 訪談抽取核心

`caliburn_memory.extraction.ExtractionWorkflow` 已自 `4f94fbfb` 採用。三文字欄位、prompt、窗口迴圈、格式更正額度、`start/resume/reextract` 保持已驗語意；`ExtractionSourceReader` 由 App 提供固定窗口與前置消歧，`accepted(raw)` 由 provider adapter 核拒絕／終局。B1 保存詳記／候選，不發布目前理解，也不前進 publication 游標。

新 App `extraction_app.py` 的 OpenAI 固定接合已完成；同文件工作須由 caller 串行，已完成 B1 的 `files` 交給 B2 後才可進下一批。B1 已在真 `PostgresSaver`／`PostgresStore` 上驗過一批的保存、資源重建後續作、重抽與相同 input 查回（[R1 結果](../../docs/specs/evidence/jd-b1-adoption/r1-postgres-batch-results.md)），套件程式未因此改動。

## B2 整併核心

`caliburn_memory.consolidation.ConsolidationWorkflow` 已自 `4f94fbfb` 採用。prompt 逐字相同（`instructions_sha256`）、`JobState`、`stale→load`、模型／工具／輸出／候選／修補五項預算、`_repair_input`、由產物推導的 `_operation_id` 與 publish／receipt 路徑都未改。暫存兩檔的編輯工具（`staging.consolidation_tools`）與最終回饋迴圈（`consolidation_feedback`）同批採用。

**唯一接縫是本套件不綁 provider**：原本 import 的 `native_context_view` 改由 caller 以 `context_middleware=` 傳入，中介順序不變。B2 只從**已完成**的 B1 checkpoint 取 `files`；它推進 `processed_source`，C 的修補不推進背景游標。

App adapter（`consolidation_app.py`）已接，並在真 `PostgresSaver`／`PostgresStore`／publication 上驗過兩批有序交接、pending 續作、發布回覆遺失查回與 C 較晚更正（[R2 結果](../../docs/specs/evidence/jd-b1-adoption/r2-consolidation-handover-results.md)）。**尚未接 runtime：**通知註冊、背景准入與宿主生命週期仍待施工；「B2 未發布不得開始下一批」目前由 caller 串行負責。[H4 執行計畫 R3](../../docs/plans/2026-09-14-jd-h4-runtime-integration.md)。

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

目前完成保存／發布、原話接點、固定只讀工具、C 修補核心及其 App 停止／恢復接合，B1／B2 兩個背景階段的採用與真 PG 交接，以及顧問方法資產（A 指引、三項分析 Skills、Memory 行動指引）的採用與 App 組裝。**新宿主程序恢復與完整旅程仍未完成**；不要把 package 測試或固定組裝測試代稱日常顧問可用，也不能宣稱自然訪談品質已驗。
