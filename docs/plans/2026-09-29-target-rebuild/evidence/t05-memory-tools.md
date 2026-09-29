# T05：Memory 工具與唯一 V4A

- 日期：2026-09-30；範圍：**工具元件的實測與接續界線**。任務完成狀態在 [tasks](../tasks.md#t05-memory-讀寫工具與唯一-v4a)，以下各切片保留當時的證據，不作第二份進度表。
- 上位：共同工具、Memory read/update 契約由任務表路由；編輯機制的唯一說明在 [正文編輯接線](../../../implementation/memory-body-editing.md)。無 production 切換、無舊資料搬遷。

## 1. 研究與取捨

主代理讀完三份工具責任契約、CRUD 範例與工程規範；官方 OpenAI Docs 技能用於核對 V4A 的執行方責任。研究子代理唯讀核對最新／本地 helper source、license 與合成反例；主代理直接讀完整本地 source 及固定版 MIT 全文。

- 官方 helper 的 `_read_section` 可重用；first-match、EOF 內文 fallback、忽略終止符後資料不符合本案契約。只抽取語法演算法，不引入 Agents SDK orchestration。
- 子代理核對固定 source 與新 main，另執行 22 項原 helper 純字串 assertions；此為研究證據，**不是新 adapter 驗收數字**。具體來源、commit、hash、license 見 [第三方註記](../../../../apps/api/THIRD_PARTY_NOTICES.md)。
- 主代理核對 RapidFuzz 官方 API／PyPI 3.14.6、安裝包 MIT；只新增成熟字串距離套件，不自製距離演算法。版本與 hashes 在 backend lock；新隔離 Python 3.14.7 可安裝。
- 不採早期探針的「精確先於模糊」政策；合格位置全部計數，避免有精確位置就忽略另一個近似位置。這是可測的保守取捨，不宣稱最優或完全避免模型語意誤改。

## 2. Red → Green 與審核發現

1. 新介面先無編輯效果；中文模糊 context／混合換行測例實際 **1 failed**，正文仍是每月而非每週。不是 import／安裝失敗冒充 Red。
2. 接上完整 parser／定位／原文切片後，該例通過；後續加入歧義、非法尾段、零匹配、多 hunk 與長文反例。
3. 獨立來源審核指出合法 EOF 純新增會被過嚴語法拒絕；主代理另補重用父 anchor 測例，得到 **5 failed、47 passed**。依唯一 EOF 與順序游標修正後 **52 passed**。不因既有測例綠色就縮減 V4A 能力。
4. 一個雙近似 fixture 的第二行實際只有 0.895、未達 0.90，已修正合成案例，使其真正有兩個合格位置；沒有降低政策讓錯誤 fixture 通過。
5. 獨立程式審核找到三個可重現缺口：結果可超 body 上限、相同多行替換改掉混合換行符、EOF 插入接受空白來源。主代理加入六個測例，實跑 **6 failed、53 passed**；修正後正文編輯器 **59 passed**。只補安全邊界，不新增保存或工具能力。

命令均在 `apps/api`：

```powershell
$env:PYTHONUTF8 = '1'
./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_memory_body_edits.py -q -p no:cacheprovider --tb=short
./.venv-target/Scripts/python.exe -m ruff check src tests --no-cache
./.venv-target/Scripts/python.exe -m mypy --cache-dir ../../.research-tmp/mypy-t05 src
```

最終切片檢查（2026-09-30）：

- `pytest tests/unit tests/contracts -q -p no:cacheprovider --tb=short`：**246 passed**，含上述 59 項正文編輯測例；不是整個 T05 或產品驗收。
- `ruff check src tests --no-cache`、`ruff format src tests --check --no-cache` 通過（134 files）；`mypy --cache-dir ../../.research-tmp/mypy-t05 src` 通過（108 source files）。修正期間曾有一行超長，已調整，不弱化檢查。
- uv 0.12.20 在新目標隔離環境建 wheel，檢查包內確有 adapter 的 MIT 授權文件與 RapidFuzz 3.14.6 dependency；未發布套件。系統 uv 0.10.8 不符專案版本要求，改用既有研究 runtime，不修改舊產品環境。
- 本地文件檢查涵蓋 14 個本切片／責任檔案、232 個連結，0 errors；`git diff --check` 通過。
- 獨立程式審核另做 20 項記憶體內控制測試；三個 findings 已用主測試重現並修正，不將控制測試混入 pytest 數字。
- 132,035 字元中文 Markdown 合成 probe 單次約 3.91 ms；只證明本例可執行，不是完整負載基準或時限保證。

本切片未碰 DB schema／交易，故依風險執行純運算、unit／contract 及靜態驗證，沒有重跑 PostgreSQL 整合；多欄原子採用仍是下一切片的真 DB gate。

## 3. 第二切片：按需讀取與來源導航（2026-09-30）

主代理接線與文件；子代理在明確限定的 schema／生成器／contract tests 範圍施工，完整讀相應規範後完成，再做一輪唯讀權限／來源／基準審查。沒有各造一套保存；接線唯一說明見 [Memory 模型工具](../../../implementation/memory-tools.md)。

- 研究：主代理使用 OpenAI Docs 技能讀官方 [strict mode](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)，明確 `strict: true`、closed objects／required、巢狀分支；未將 SDK 能序列化當成遠端接受。schema 本身是唯一 shape，生成原樣 package resource，避免 Python DTO 再生不同 wire。
- 行為 Red：`MemoryReadWorkflow.read_map` 先返回空集合；真 PG 候選新增後要求 `盤點` 的測例 **1 failed**。不是 missing import 當行為 Red。補上既有候選 map owner 接線後通過。
- 真 PG 新增 7 項場景：候選 map 更新；改名／標題重用仍沿原物件引用；A 固定舊快照與原本空基準；B1 越層／舊 stage／取消拒絕；批次訪談上界；工具完整精簡回传／合法空來源／不合法選取；容量整筆拒絕。另於同一 read 的 map／正文之間注入真 DB 刪除與同名建立，證明本次 view 不混版，下次才看到新位置。
- 7 份讀取 schema 加共同 rejection schema，生成 Python／TS 與 8 份包內 JSON；參數禁止模型填 execution／snapshot／scope。63 個生成／契約案例與 5 個工具／離線 SDK 案例通過；schema 缺少時的生成失敗只算施工檢查，不冒充產品行為 Red。
- `pytest tests/unit tests/contracts` 加全部 `test_memory*`／`test_interview*` PostgreSQL 整合檔：**444 passed in 81.92s**。使用既有 55439 隔離 test DB、每測試新 schema；未停止共享 DB、未讀舊資料。
- Ruff check／format 通過（143 files）；mypy 通過（122 source files）；生成器 `--check`、前端 TypeScript 檢查通過。工具 output DTO 失效不被當成模型參數錯誤；基礎設施 timeout 交 Runtime 的控制測試通過。
- uv 建 wheel 成功，檢查 **8** 個 tools schema；直接由 wheel 的 Python resources 讀取訪談 schema，bytes 與正式來源相同。未發布或替换 production 環境。
- 獨立快審沒有確認的新 finding；它未重跑 DB／wheel，這兩項由主代理實測。沒有聲稱審查能證明絕無缺陷。
- 文件檢查 16 檔、267 連結、0 errors；初次將既有 HTML anchor 誤報缺失，已修檢查器辨認顯式 anchor，未任意改責任連結。主代理生成檢查曾受 Windows 沙盒子程序暫存 ACL 阻擋，改以授權本地命令重驗，不改產品機制繞過。

上述沒有付費 API、外送員工資料或讀取金鑰。Native tool-call 保存／配對、模型接續、真 provider strict 與模型導航品質尚未驗證；單次讀取的字元上限不是 T06 token 預算。

## 4. 第三切片：受限寫入與原操作接續（2026-09-30）

主代理負責固定命令準備／候選採用／回傳與真 PG；子代理限定 schema、生成物及契約測試，再獨立唯讀審查整體接線。先讀 Goal、工程規範與原 CRUD／更新契約，沒有自行變更模型欄位或新造保存 owner。共同 wire 載入／拒絕格式由讀寫工具共用，領域不依賴生成 DTO。

### 研究、反例與修正

- Schema 延續前切片已核的官方 strict 契約，採 closed objects／required／巢狀分支。正文真實效果重用 Python 3.14.7 標準庫 `difflib.unified_diff`；主代理檢查已安裝標準庫原碼，未自製差異算法。此次 LangGraph／Python 網頁工具未返回並已停止等待，不能記作新的已讀官方證據；不據此新增框架保證。
- 行為 Red：準備函式先不產生修改，title＋V4A 案例 **1 failed**；實作純變更準備後通過，再加入 all-or-nothing／來源／權限／重入接線。
- 獨立審查找到 P2：diff 用 `splitlines()`，編輯器只認 LF／CRLF，會將 Unicode separator／VT／獨立 CR 誤報新行。正文保存正確但回傳行號失真。主代理補三個反例得到 **3 failed、7 passed**；共用 `split_body_lines` 後通過，未放寬定位或修改原文。
- 兩項測試 fixture 修正保留原因：歧義訊息應查 typed code 而非猜英文措辭；短 header 內部空白差異不符既有模糊政策，長文案例改用實際允許的行首空白差異，未降門檻讓錯例通過。
- 沒有新增依賴、資料表、收據或 checkpoint engine。工程接線、完整結果先驗及未知提交交 Runtime 的界線，只在 [Memory 工具 §4](../../../implementation/memory-tools.md#4-寫入準備採用與原結果接續)維護。

### 驗證

新增 10 項純準備案例、54 項 schema／generated contracts、10 項真 PG 寫入場景。真 PG 涵蓋：prepare 無副作用；title／description／body／references 共同採用；後段 hunk／引用／重名拒絕；原命令改名後 title 重用；準備後位置已變；B2 空／新增／移除來源；非法跨層；超過十萬字元 Markdown 的受控模糊修改與多處拒絕；CRUD／no-op 精簡結果；容量在採用前拒絕；真提交後注入確認遺失、原命令重入仍回原結果。未啟動 Graph 故障恢復。

在 `apps/api` 執行：

```powershell
$env:PYTHONUTF8 = '1'
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
$memoryToolTests = @(rg --files tests/integration | Where-Object { $_ -match 'test_(memory|interview)' })
./.venv-target/Scripts/python.exe -B -m pytest tests/unit tests/contracts @memoryToolTests -q -p no:cacheprovider --tb=short
```

- 上列 **518 passed in 82.27s**，全部 unit／contracts 加 Memory／Interview 整合；不是全部後端、UI 或產品測試。PG 每測試獨立 schema，保留共享 DB 程序。
- 審查修正後的正文／準備／寫入 PG 定向測試另為 **79 passed in 7.62s**，包含既有 59 項正文案例，不重複累加成新覆蓋數。
- Ruff check／format 通過（152 files）；mypy 通過（134 source files）；生成器 `--check`、前端 TypeScript 通過。新增 6 個 schema及相應 Python／TS／package resources 全從唯一來源生成。
- uv wheel 建置通過，包內 **14** 個工具 schema 與正式來源逐 byte 相同。首次受既有 uv cache 沙盒 ACL 限制，經授權本地建置重驗，未修改 cache 權限或產品程式。文件檢查 **19 檔／306 連結／0 errors**，`git diff --check` 通過。

本切片無付費 API、無秘密或真人資料外送。V19 的確定性機制與候選採用已驗；V20 只有 Memory 元件部分，完整 JD 導覽與自然模型按需使用仍待 T07／T16／T17。模型真正選對物件、strict 遠端接受、效果品質不能從這 518 項推得。

## 5. 下一個可執行切片

進入 T06 共用原生執行：可靠保存完整模型結果與 App 操作身分，再保存原 prepared command，之後執行工具並接回原 `call_id`。先用假 provider＋真 saver／PG 驗證 R 已存不重呼模型、多 call 依序、原命令重入與原生 opaque／phase metadata 保留；不新增 ResponseStore 或把 pending command 當第二份候選。

T06 須依已有授權建立有界全合成 provider 預檢；尚未進行的 API／checkpoint／模型品質 gate 仍明列，不能用函式／交易測試替代。
