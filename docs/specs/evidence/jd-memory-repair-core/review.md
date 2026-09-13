# C 修補核心：獨立分段審查

2026-09-13；基準 `7d3f474a`。本審查者沒有撰寫本輪 package patch／staging／repair 或 App source bridge，也沒有修改產品或作者測試。前置反例及原政策核對留在 [runtime-preflight](runtime-preflight.md)，不把初審發現覆寫成原本就正確。

## 階段 A：patch、staging 與來源橋接

**結論：此限定範圍 PASS，未發現新增可重現的 P1／P2。**RepairWorkflow 的後續獨審見階段 B；兩段均不代稱新 App C runtime 接線完成。

| 範圍 | 獨立核對 |
|---|---|
| [patch.py](../../../../packages/consultant-memory/src/caliburn_memory/patch.py) | 直接取原 commit 的 `memory_patch.py` git 物件比 AST；排除 module docstring 後完全一致。使用公開 `agents.apply_diff`，沒有複製 matcher。保留兩個既有路徑、12000 字元、完整函式成功才 queue staging write；失敗第二 hunk 不 queue 第一段半成品。合法三種尾端 marker 可用，尾隨別檔／內容拒絕。 |
| SDK 既有取捨 | 真 native 測試仍觀察 first-match／不存在的單一 advisory anchor 可改第一處；沒有假稱唯一匹配。完整 context 區分同文案例，no-op、倒序 hunk、缺 context／缺檔／非 Memory 路徑均有實際反例。不改這些已知 matcher 契約。 |
| [staging.py](../../../../packages/consultant-memory/src/caliburn_memory/staging.py) | 從 StateBackend 讀兩檔、沿同 `MemoryArtifacts.validate_texts` 檢查。缺 staged file 為已知內容錯誤；其他 download 錯誤／沒有 bytes 為不可用，不假說模型重寫可修。只有已知長度、guide presence 及引用錯誤成 `StagedMemoryValidationError`，來源診斷不複製到可修錯誤文字。這裡不保存 artifact／不發布。 |
| [sources.py](../../../../packages/consultant-memory/src/caliburn_memory/sources.py) 與 [MemorySourceReader](../../../../experiments/jd-relational-app/src/jd_relational/memory_sources.py) | `InvalidSourceReference` 是 source port 的已知地址錯誤；App 只將原 owner 的 `invalid_ref` 轉成這類型。signature／document 檢查仍委派同 owner，不新解析 token。`source_not_available`、未知 ValueError／OSError 仍向上傳，不降格成模型可修錯誤。 |
| [memory_read_tools.py](../../../../experiments/jd-relational-app/src/jd_relational/memory_read_tools.py) | summary source-window 與直接 source.read 兩條入口均捕新的 typed invalid reference，保留固定 `invalid_ref` ToolMessage；未知錯誤仍停止，沒有原話或診斷 marker 外露。原 reference 不重發，ToolRuntime 隱藏注入／call id／公開角色及原話完整續頁仍通過。 |

獨立實跑四個專檔：[test_patch.py](../../../../packages/consultant-memory/tests/test_patch.py)、[test_staging.py](../../../../packages/consultant-memory/tests/test_staging.py)、[test_memory_sources.py](../../../../experiments/jd-relational-app/tests/test_memory_sources.py)、[test_memory_read_tools.py](../../../../experiments/jd-relational-app/tests/test_memory_read_tools.py)，**73 PASS／15.14 秒，exit 0**。本審查首跑即通過；未製造新測試或修改 fixture。

工作目錄為新 App，使用鎖定環境：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -c pyproject.toml ../../packages/consultant-memory/tests/test_patch.py ../../packages/consultant-memory/tests/test_staging.py tests/test_memory_sources.py tests/test_memory_read_tools.py -q -p no:cacheprovider
```

另以 AST 純比較核對舊 git 物件與本輪 patch，exit 0。這些是原生 StateGraph／StateBackend／InMemorySaver／Store 與合成 source 測試；**零 provider／SQL／服務／新程序**。不與作者 patch 22 或 root staging/source 51 相加，也不代稱自然模型修補、背景 B1／B2 或整個 C runtime 完成。

## 階段 B：RepairWorkflow

作者停寫後，已讀 [repair.py](../../../../packages/consultant-memory/src/caliburn_memory/repair.py) 與完整 [test_repair.py](../../../../packages/consultant-memory/tests/test_repair.py)。**核心範圍 PASS；CR-R01／02／03 的核心修正 CLOSED，沒有新增可重現的 P1／P2。**原生 App tool binding／owner／模型 request 接線仍是後續責任，不以核心閉合冒稱已完成。

| 初審問題 | 實際修正及獨審判斷 |
|---|---|
| CR-R01 原意圖對帳 | `reconcile(request: PublishRequest)` 只接受確切 request 類型、repair kind、同文件、單一 source 及不推進 processed_source。原 receipt 必須同 operation／完整 request digest／kind／source／base／結果 Memory，結果 revision 為 base+1；缺或錯配皆 `PublicationUncertain`。舊三參數 ABI 已拒絕；對帳回覆沒有 `changes`，因此不能再 echo caller 的假 edits。receipt 證明 publication 而非 patch 文字，App 仍須以其原生已保存 binding 提供修改內容。 |
| CR-R02 錯誤歸因 | `_validate:93` 僅捕 typed `StagedMemoryValidationError`。直接未知 ValueError／RuntimeError，以及真暫存引用驗證時 source I/O 皆向上停止；沒有發生 `invalid_edit` 或出版。可修內容錯誤仍回 feedback，不變成一般故障。 |
| CR-R03 applied/current | `_current_after:109` 由正常 `_publish` 及 `reconcile` 共用，拒絕 current 缺失、較舊，以及 applied/current 另一文件。真正較晚 current 仍配其 guide 回覆，applied_head 保留原 receipt；沒有回退目前 Memory 或改變原政策。 |

另核六個 native 節點／每次 edit 的 checkpoint 邊界維持。來源返回值可為 owner 的 opaque object，C 不重解原話。第二個 patch 失敗不出版第一個的暫存；沒有 Memory 不由 C 初始化；stale base 不讀來源後盲套候選。`kind=repair` 的來源與原 `processed_source` 分開，仍由原 PublicationStore 短交易發布。

獨立執行同一新 App 鎖定環境的 `test_repair.py`，**32 PASS／13.29 秒，exit 0，無 warning**；沒有重跑原 memory／publication 全組。這 32 案包含實際 native parent／child、InMemorySaver、StateBackend／Store 及 SQLite publication：中斷後重建 workflow 可續接第二次 edit 而不重做第一筆；SQL commit 成功後人工丟失回覆，公開 native child 仍保留 `publish` pending 與原保存 request，`reconcile` 查回原 revision 2，實際 publish 仍只一次、pending 不被偷偷清除。

其中正向 reconcile 只查 receipt／current／guide，沒有 source body、artifact save、publish 或 graph resume；讀取錯誤回固定不確定訊息。這不是在證明 absent receipt 就等於 failed，也沒有把 native resume 能力當成取消路徑。外宿主停止證據、完整顧問 C call/result binding、初始／目前讀版刷新與 gate 仍由 App 接線驗證。

重跑入口：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -c pyproject.toml ../../packages/consultant-memory/tests/test_repair.py -q -p no:cacheprovider
```

本段沒有 provider／真 PostgreSQL／新程序／HTTP／Web。作者的首敗、31＋1 分批結果與原 34 回歸保留於 [repair-results](repair-results.md)，不混作本人的獨立執行。階段 A 與 B 分批報告，不改寫成一次完整 App suite 通過；本審查未修改產品或測試，僅寫此文件。

## 階段 C：真 PG 證據及切片宣稱的唯讀核對

已唯讀核對 [test_memory_repair_postgres.py](../../../../experiments/jd-relational-app/tests/test_memory_repair_postgres.py)、[作者 PG 結果](postgres-results.md)及[本輪切片](../../2026-09-13-jd-memory-repair-core-slice.md)。**文件／測試一致性 PASS，沒有具體 P1／P2 阻擋；本審查者沒有重跑 PG。**作者最後單案 `1 PASS／8.01 秒` 保持為作者執行證據，不併入階段 A／B 數字。

測試先於公開 fixed child checkpoint 取得原 `PublishRequest`，明驗無 receipt 的 reconcile 不發布；然後為注入故障才明示 resume，真正 `PublicationStore.publish` 返回後拋合成 ACK lost。兩次 patch／一次 artifact save／一次 publish 的計數與原 request 保留都有斷言。查回階段封鎖 patch、save、Store.put、publish、來源正文 read，仍取得原 applied revision 2；沒有用重播候選換來成功。

後續 B fixture 發布 revision 3，再退出原資源 context、以新連線／serializer／graph／source owner 重開，從原 fixed checkpoint 取得相同 request，回 applied 2／current 3／配對 guide。固定兩份原話文本（含原 CRLF／空白）、原完整訊息與閉合觀測、JD 完整 CurrentDocument 均前後相等，publication 回執數固定為 3；新連線未呼叫合成對話節點。

repair 父子圖明示使用獨立合成 thread，沒有覆寫原對話根。這是**同一 Python 程序中重開資源的核心 fixture**；並未關閉原 repair pending、提供外宿主死亡證據，或把 C 掛入日常 App／模型工具。結果及切片都保留這些界線，也分開記錄首次 latest overlay 的測試判斷修正，不把它說成產品修復或省略首敗。
