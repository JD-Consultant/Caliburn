# T07 `read_jd_changes`：來源與人工差異窄切片

2026-09-30；狀態：**manual/source 完整工具已驗證，可由主線註冊；本切片不修改 registry，不代替整體 T07 gate 驗收**。Owner 後續已授權擴充原 feature 公開查詢。

## 交付與邊界

- 新增 `workflows/jd_changes.py`、`transport/model_tools/jd_changes.py`、`jd_changes_wire.py`、canonical schema 與三個測試檔；沒有修改 registry、bootstrap、generated。
- 經 Owner 擴檔授權，新增 JD `change_queries.py`，並擴充原 JD `persistence.py`、executions `history.py`／`history_persistence.py` 的窄只讀查詢；沒有第二資料 owner、資料表或 receipt。
- source 先讀一次本 execution 的候選位置／引用，再經原 Memory owner 讀引用固定舊 snapshot 與 Turn pinned snapshot。比同一 object identity，包含理解下直接情境的相關差異；同名重建不接替舊身分。
- 舊版只作相關 diff，不回任意歷史全文；重用 Memory 的 `describe_body_change`，未變正文不重貼。內部 typed result 不等於模型輸出。
- 固定 snapshot 存在且 membership 缺席才可明示來源已不在新版。固定資料缺失回 `source_not_available`，基礎設施例外交 Runtime，不解讀成刪除／空差異。
- 訪談先核正式 H，再回 `source_kind_not_supported` 與正式序號；current_input 指本輪原話，不編序號。讀取不寫 JD／來源／history，不確認 alignment。
- source 單筆超量回 `read_limit_exceeded`，不截斷、不回部分結果或偽造分頁。

## 現在可用的精確 API

```python
JdChangesWorkflow(sessions)
await reader.read_source(binding: PublishedMemoryRead, citation_ref: str) -> JdSourceChanges
await reader.read_manual(
    binding: PublishedMemoryRead, *, manual_jd_start_revision_id: UUID,
    scope: ManualChangeScope,
) -> JdManualChanges

tools = JdChangesTools(
    reader, binding, *, manual_jd_start_revision_id: UUID,
    max_result_characters: int = 1_000_000,
)
tools.names  # ("read_jd_changes",)
tools.definitions()  # list[FunctionToolParam]，等同 jd_changes_definitions()
await tools.invoke(name: str, arguments: str) -> str

parse_jd_changes(arguments: str) -> ManualChangeQuery | SourceChangeQuery
jd_changes_definitions() -> list[FunctionToolParam]  # 無 binding／業務資料讀取
project_jd_source_changes(result: JdSourceChanges) -> str
await read_jd_source_changes(
    reader: JdChangesWorkflow,
    binding: PublishedMemoryRead,
    citation_ref: str,
    *, max_result_characters: int = 1_000_000,
) -> str
```

`JdChangesTools` 位於 `caliburn.transport.model_tools.jd_changes`，`JdChangesWorkflow` 位於 `caliburn.workflows.jd_changes`；完整 handler 本輪已落地，不是只註冊 source 分支。definitions 可在尚無 binding 時建立，handler 再接 once-only Turn 的起點。

schema SHA256：`D78BF0139C4FE6BA61B785F6A14DE22705B107B21113F3C90CE82F20FFBB84B2`。本代理沒有啟動 shared codegen；第一輪在 OS temp 驗證 Python DTO。本輪已確認主線生成的 schema hash 一致，最後測試使用正常 generated import，不再依靠 temp。

## manual 原 owner 讀取接點（後續授權後已補齊）

第一輪既有公開介面缺少成功 Turn／人工操作區間。本輪補上：

- `history.read_previous_completed_execution(session, scope, role) -> ExecutionScope | None`：從當前固定 history binding 的 base 依引用相等值追溯；跨 prepared-only／重用準備／取消，僅接受 completed execution。缺失 ancestor 明確拒絕，不退到空基底；不解析 thread ID、不載入 native 全文、不改 head。
- `change_queries.read_manual_change_range(session, job_file_id, execution_id, *, start_revision_id, previous_completed_execution_id) -> ManualJdRange`：讀原 adopted candidate、JD ancestry 與人工 operation。跨 feature 資格仍由 workflow 公開呼叫組合，不直查別人的表。

workflow 現在取得：

1. 同檔、早於本 execution 的最後 completed consultant Turn；取消／失敗排除。對應已採用 JD 位置必須可取回；只有真的沒有成功歷史才用初始空 JD。
2. `base_revision_id` 到已捕獲 `manual_jd_start_revision_id` 的有序人工操作；排除候選操作，保留 no-op／改回，並提供受影響目標（單靠 before/after revision 相等無法辨認 no-op 的範圍）。

這些是 App 私有讀取結果，不是模型新增參數／receipt／DB。端點與 candidate.base_revision_id 核對，不能讀 candidate.current 當起點；只有 item 選取存活資格讀一次當前候選。人工差異以原操作＋淨差異分區，保留新增／刪除／文字／位置／關聯／來源資格變化；no-op 仍明示受影響範圍。歷史刪除定位不可再作 item／edit 目標。來源差異標實際 JD 所屬目標，讀取不確認 alignment。

non-noop 原操作依 revision ancestry 排序；不產生 revision 的 no-op 沿原 operation timestamp，在前次成功候選開始到本 Turn 起始候選建立的區間過濾。既有 manual admission 禁止候選執行期間人工寫入，因此不用 completion transaction 開始時間誤切掉完成後才成立的人工操作。

## 驗證

- 真 PG：新增 2 tests，涵蓋來源鏈變動、延後發布不漂移、舊物件刪除＋同名重建、範圍／正式 H、缺 endpoint、storage exception、跨檔引用隔離、current_input／正式訪談導向、取消後不可讀及 read 不 alignment。
- strict wire：新增 2 tests，接受兩類 canonical 分支及全部合法 scope，拒絕跨分支／null／未知區域／版本／App identity，不 fallback all。
- 主線 API 400 回報後，definitions 改走共用 `function_definition` 讀權威 generated schema；保留 generated model 驗 input，不重建模型送出的 schema。新增第 3 個 contract test，確認與權威 schema（僅去 `$schema`）一致、全部物件 strict、`$ref` 無 sibling keywords。修正前 **1 failed, 2 passed**，修正後通過；schema 語意與 hash 不變，未重跑付費 API。
- 容量行為 Red：限制 5 字時錯誤回完整 MD；補拒絕後 Green。前述來源讀取測試未記錄實作前 Red，不冒充全切片完整 TDD 證據。
- manual 新增 6 個真 PG tests：跨取消基準、候選不漂移、改回／no-op／無操作、成功後基準推進、首輪、錯誤起點、移動／unlink／刪除／新增條件／来源待核對、範圍縮小、刪除項目不可 item 讀、重用 prepared 不當完成、缺 ancestor 不冒充初始。
- manual 有效行為 Red：no-op 沒有受影響欄位、來源差異沒有 JD 所屬定位，**2 failed, 4 passed**；補投影後 Green。最初缺 class／新查詢的 ImportError／AttributeError 不列為行為 Red。
- 最後小回歸：manual/source/wire、completion、role history 與 JD candidate，**36 passed in 20.28s**；不代表真模型／完整產品驗收。
- Ruff 與 7 個 production 檔 mypy `--follow-imports=silent --cache-dir nul` 驗證；未宣稱全專案 typecheck／全測試通過。
- 未讀 `.env`、未付費、未 commit、未啟用子代理；只擴充本切片所需原 owner。
