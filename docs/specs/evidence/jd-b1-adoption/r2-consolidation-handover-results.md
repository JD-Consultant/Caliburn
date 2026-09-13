# H4-R2：B1→B2→publication 的採用與有序交接

2026-09-14；JD-R002／OI-01、OI-02。實作[H4 計畫 §4 R2](../../../plans/2026-09-14-jd-h4-runtime-integration.md)，接續 [R1](r1-postgres-batch-results.md)。基準 `151723ea`／tag `jd-h4-r1-postgres-batch-20260914`。**0 provider、沒有新增資料表、沒有第二個發布權威。**

## 1. 先對應，再只採用缺少的

依計畫「先列 `4f94fbfb` B2 直接依赖與現有正常套件逐項對應，再只採用缺少部分」，不整批複製：

| `4f94fbfb` 的直接依賴 | 套件既有 | 本輪處理 |
|---|---|---|
| `memory.MemoryVersion`／`MemoryArtifacts`／`ReadOnlyFiles` | `caliburn_memory.memory` | 沿用 |
| `publication.PublishRequest`／`StalePublication`／`PublicationStore` | `caliburn_memory.publication` | 沿用 |
| `memory_patch.PATHS`／`PATCH_GUIDANCE`／`MemoryPatchError`／`apply_staged_patch` | `caliburn_memory.patch` | 沿用 |
| `consolidation_tools.staged_texts`／`StagedMemoryValidationError` | `caliburn_memory.staging` | 沿用 |
| `consolidation_tools.StagedFiles`／`consolidation_tools()` | — | **採用進 `staging.py`**（同一來源檔的其餘部分） |
| `memory_tools.MEMORY_EDIT_GUIDANCE` | — | **採用進 `read_tools.py`**（同一來源檔，B2 的工具說明需要） |
| `consolidation_feedback.*` | — | **新增 `consolidation_feedback.py`** |
| `consolidation.ConsolidationWorkflow`／`INSTRUCTIONS` | — | **新增 `consolidation.py`** |
| `runtime.native_context_view`／`context.server_compaction_view` | — | **不進套件**：provider 專屬，落在 App 的 `consolidation_app.py` |

`adoption.json` 現有 11 筆，全部 hash 實測相符。

## 2. 保持不動的與唯一接縫

`consolidation.py` 對來源的 `diff` 只有四段：docstring、import 改套件相對、建構子多一個 `context_middleware=()`、中介清單把 `native_context_view` 換成 `*self.context_middleware`。**prompt 逐字相同**（`instructions_sha256 = d4061fc9…`，以來源同法計算並比對為 `True`）。`JobState`、`stale→load`、五項預算、候選／詳記預算規則、`_repair_input`、由產物推導的 `_operation_id`、publish／receipt 路徑全部未改。

**唯一接縫**：套件不綁 provider，所以 provider 需要的 context view 由 App 傳入，中介順序不變。

App 的 `consolidation_app.py` 依已驗 profile 組裝：**effort high、顯式輸出 8192（不是類別預設 4096）、compaction 門檻 12000、16 模型步／15 工具呼叫**。這些是本案實測值，不是廠商預設。`truncation` 依 B1 adapter 已定的同一理由不送出（現行參考標為 deprecated、預設即 `disabled`，超量輸入回 400）；這是與 `4f94fbfb` 的明示差異。

## 3. 三層測試與它們各自釘住的事

**套件層（7 個，0 模型）**——B2 在模型迴圈**之外**的權責。一個 `NoModel` 替身讓任何誤觸模型的路徑直接失敗：

拒絕未完成的 B1 輸出、相同產物的已發布結果原樣查回、head 已涵蓋本範圍時直接回報、不在受理順序內的批次被拒、候選超量明示失敗而非截短、預算用盡不重置、operation 身分綁**確切產物**而非只綁來源。

**App 固定 SDK 層（8 個）**——真 agent 迴圈、真暫存檔工具、真 SDK：

完整整併並發布、請求逐字帶著採用的 prompt 與已驗 profile、超預算先丟內嵌詳記而不截短候選、未完成／被拒回覆不發布、暫存驗證錯誤在同一次嘗試內以**私有** runtime 回饋更正、寫入兩個暫存檔以外被拒且模型看得到、**C 較晚更正造成 stale→重讀**、**發布回覆遺失以原 request 查回**。

**真 PostgreSQL 層（5 個）**——真 Saver／Store／publication 表：

兩批有序交接（第二批只因第一批的發布推進游標而存在）、B1 完成但 B2 未開始時交接能撐過所有資源關閉重開、B2 pending 在重建資源後續作且**零次**再呼叫模型、發布已提交但回覆遺失的對帳、C 在 job 中途發布修補後 B2 重讀而非直接覆寫。

每個真 PG 案例都以 SQL 核 `q019_document_memory_head` 的實際列數；**B1 單獨執行時該表恆為 0 列**。

## 4. 實測

```powershell
$env:JD_RELATIONAL_TEST_DB='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache `
  pytest -c pyproject.toml -q -p no:cacheprovider tests/test_consolidation_postgres.py
```

| 範圍 | 結果 |
|---|---|
| `tests/test_consolidation_postgres.py`（真 PG） | **5 passed** |
| 受影響真 PG 全組（B1、B2、來源、Memory 核心、C 接合、C context、C 修補） | **28 passed／27.75s** |
| App 全離線測試 | **2821 passed／268 skipped／43.46s** |
| Memory 套件全測 | **154 passed／4.43s** |

兩批交接的實際數字（測試印出，全部量到）：`batches=2 http=10 revision=2 rows=12`——B1 兩批各 2 個窗口共 4 次呼叫，B2 兩次整併共 6 次，發布版號走到 2，Store 有 12 列。

**六個首敗全部是測試自身的假設或寫法錯，沒有為通過而放寬產品：**

1. `PublishedHead` 沒有 `kind` 欄位（kind 在 receipt 上，不在 head）。
2. Responses API 沒有 `instructions` 欄位：system prompt 在 `input[0]`，payload 在 `input[1]["content"]` 且是字串。
3. `max_candidate_chars=400` 連候選本身（638 字）都擋掉；實際要落在候選與候選＋詳記（1219 字）之間，改用 800。
4. 找 runtime 回饋時假設 content 是 block 陣列，實際是字串。
5. 模擬 C 介入的 monkeypatch 遞迴呼叫了自己（改為呼叫原函式，且先登記再發布）。
6. 真 PG 案例中 B1／B2 共用一條 transport，payload 過濾把 B1 的請求也算進來（改以 payload 是否含 `RECENT_REPAIRS` 選 B2 自己的請求）。

## 5. 限制與未完成

1. **R2 完成的是採用與交接本身。**通知註冊、背景准入、宿主生命週期、真新 Windows 程序全部未做——那是 R3。
2. **「同文件只能有一筆未交接完的 B 批次」目前仍靠 caller 串行。**本輪示範了正確順序並驗證其耐久性，但**沒有**在程式中加入阻擋「B2 未發布就開始下一批 B1」的門閘；那是 R3 的准入責任。不得由本稿推導該情形已被擋下。
3. 資源重建仍是**同一程序內**關閉再開。真新 Windows 程序取回原 B 工作是 R3 第 7 點。
4. 固定 SDK 回覆不是自然模型品質；B2 的整併內容由測試指定，不代表模型會自主寫出同樣的理解。**日常 AI 仍未啟用。**
5. 本輪沒有重建 wheel；`adoption.json` 的 hash 證明的是原始碼，不是已封裝產物。
6. C 較晚更正的案例證明 B2 會重讀並在剩餘預算內重發；**沒有**證明任意次數的競爭都能收斂——預算用盡時的行為由套件層「預算用盡不重置」那條案例涵蓋，兩者不合併宣稱。
