# 顧問配置對照

這個入口以固定案例比較候選 Prompt、Tool 說明、JD 讀取容量或 Plan 能力，使用正式 App、HTTP、Agent、工具及 PostgreSQL 保存。每個候選使用獨立 schema 與 SDK client；不複製 Agent，也不修改 module-global。工程責任見[程式組織](../../../docs/standards/code-organization.md)，評測判準見[貢獻指南](../../../CONTRIBUTING.md#模型品質比較)。

## 先確認配置

在 `apps/api` 執行：

```powershell
uv run --locked python -m evaluations.consultant_comparison evaluations/consultant-example.json --dry-run --output comparison-manifest.json
```

輸出檔必須尚不存在。dry-run 驗證候選名稱及工具，保存實際提示與工具定義，不連資料庫或模型。修改[範例](consultant-example.json)即可建立自己的比較；JSON 接受下列內容：

| 位置 | 用途 |
|---|---|
| `case.name`、`employee_name`、`inputs` | 同一案例的名稱、合成受訪者及依序送出的固定輸入 |
| `case.criteria` | 留給評閱者的判準；不送進受測 Agent |
| `candidates[].name` | 唯一候選名稱，也是輸出子目錄 |
| `prompts` | 替換 `professional_method`、`focus`、`interview_plan` 或 `occupation_references` 區段；省略者沿正式預設 |
| `tool_descriptions` | 按正式工具名稱覆寫說明；不改 schema 或 handler |
| `interview_plans_enabled` | 比較是否提供 Plan 能力，預設開啟 |
| `jd_read_max_result_characters` | 比較 JD 工具既有回傳容量；必須為正整數，不靜默截斷結果 |

一次比較宜只改要回答的變因。整組能力消融會同時改提示、工具及起始資料，不能稱作只有一句 Prompt 的差異。新增 schema／handler 變因要沿正式組裝介面實作並驗證相容性；此 JSON 不接受任意 Python 程式。

## 驗證正式執行與保存

先依[後端 README](../README.md)準備明示的 loopback 測試資料庫，其名稱必須以 `_test` 結尾。設定 `CALIBURN_TEST_DATABASE_URL` 後，在 `apps/api` 執行：

```powershell
uv run --locked python -m evaluations.consultant_comparison evaluations/consultant-example.json --scripted --output comparison-scripted
```

入口建立新的隨機 schema 並沿正式 migrations 升級，不清除已有 schema。`--output` 必須是新目錄。每組用合成 provider transport 走完整流程；沒有付費模型呼叫，也不評模型分析品質。腳本回應只支援 fixture 定義的合成情境，不是通用受訪者模擬器。

輸出包含：

- `manifest.json`：案例、整批固定候選、實際提示／工具、輸入檔及來源 archive 的 SHA256。
- `source.zip`：受測後端程式、評測入口與鎖定依賴；不含環境檔、憑證或資料庫。
- 各候選的 `runtime.json`：隔離 schema 與執行配置；不含 API key。
- 各候選的 `result.json`：沿正式 HTTP 觀察到的完成狀態與訪談／JD／Plan，取得後先保存。
- `diagnostics.json`：其後擷取的原始模型請求、工具參數／結果與捕捉綁定。擷取失敗則留下 `diagnostics-failure.json` 的階段及安全錯誤種類，正式結果仍保留；CLI 回非零、程式化入口回 `CandidateRun.diagnostics_available=False`，停止這批比較而不重送模型。
- 失敗時的 `failure.json`：錯誤類別。原件保留，入口停止，不自動追加輸入或重跑。

manifest 與 App 使用首次等待前固定的同一候選。實際發送內容以 `diagnostics.json` 為準；缺少診斷須明列觀測未完成；背景工作是否完成須查其狀態，不能由顧問 Turn 完成推定。診斷有正文，僅存放於授權的本機位置；真人測試的單次查閱沿 [runbook](../../../docs/operations/README.md#在-datagrip-查某個職務檔案的-ai-執行紀錄)，不必建立另一套 UI。

## 使用真 provider

程式化入口是 [run_authorized_comparison](authorized_consultant_comparison.py)。呼叫者提供已授權的模型設定、資料範圍及共用整批費用護欄的 client factory；它把所有候選組裝到同一正式流程，保存來源及結果。費用宣告只是紀錄，實際攔截由注入的 guard 執行；每次 execution 的上限不等於整批上限。

CLI 目前僅提供 dry-run／scripted。歷史比較原件及其 guard 保留原受測契約，不作新入口的隱藏依賴；沒有宣稱目前已支援任意模型、自動品質評分或所有工具插件。
