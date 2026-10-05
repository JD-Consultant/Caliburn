# 公版與 JD 按需工具的規範審核

2026-10-05。審核結論：**現行工具主要工程邊界符合，仍有說明及回傳缺口；新三層投影為設計稿，不能稱全部驗收通過。** 本輪為工程代理逐條核對與離線反例，不是新增第二位獨立審查者或真模型試驗。前輪獨立審查主要核對角色接線與恢復，不能替代這次 description／Prompt 語意審查。

**接續狀態：** 使用者之後授權修正，下述三項反例已補回歸並改善；最新實作、獨立審查及命令見 [hardening-verification](hardening-verification.md)。本頁、原件與來源 SHA 保留審核當時狀態，不用修正後程式覆寫基線；下方重算命令只適用原件記錄的來源版本。

## 依據與範圍

規範依[共同工具契約](../../../specs/2026-09-27-agent-tool-contract-design-research.md) §2、§6、§7、§10，[契約策略](../../../contract-strategy.md)及[分析方法／Prompt／Tool／Context 共同驗收](../../../implementation/development-standard.md#7-分析方法prompttool-與-context-共同驗收)。現行權責見 [ADR0080](../../../adr/0080-opt-in-public-reference-agent-tools.md)、[公版工具](../../../specs/2026-10-04-public-reference-completion-design.md)與[JD 工具](../../../specs/2026-09-29-jd-model-tool-contract-review.md)。

本輪核對 A 五項公版工具、B1／B2 的唯讀排除工具，以及 JD `read_jd` 的取用契約。審查名稱、模型參數、App 綁定、description、可選角色 Prompt、成功／空集合／錯誤回傳及恢復界線；沒有重審全部 JD 寫入工具或改其他人正在調整的分析 Prompt。

## 逐項結果

| 項目 | 結果與可核對依據 |
|---|---|
| 名稱與分責 | 符合動作＋業務對象 snake_case。A 搜尋／讀取／選用／排除，B1／B2 只讀排除，JD 保持獨立業務。 |
| App 已知身分 | 模型沒有職務／execution／generation／revision／operation 參數；只選已提供的定位。 |
| 輸入型別與限制 | 正式 JSON Schema、生成型別、strict、禁止額外欄位、required／nullable 均有離線檢查。query 長度與非空、task_id null、未知欄位與空參數均有反例。 |
| 選用參數語意 | **需修正：**description／schema 尚未明說 reference_ids 取代全部已選集合；Domain 確實是替換。 |
| 成功讀取 | 現行搜尋保留全部已解析目錄、沒有分數；單項讀取保留完整群組及共用區塊。JD map／局部 JSON、全文 Markdown，空集合與讀取故障分開。 |
| state 與資格 | null／[] 有不同語意，未知不是否認；選用與排除為本輪候選，不宣告 JD 完成，不自動入 query／Memory。 |
| 寫入成功回傳 | **待改善：**選用及排除回傳完整 state，可能重複大量內容；execute 未套讀取的字元上限。不能在已寫入後回「未改」。 |
| 錯誤格式 | `status/code/message/next_action` 統一、無 raw exception；故障沒有變空成功。 |
| 錯誤指引 | **需修正：**搜尋 query 不合法也回 add/remove 說明，不符合「指出相關欄位與合法下一步」。 |
| 現行 Prompt | 指定收尾查漏時按需查公版、正向 query、多選、多對多、否認及未知；沒有要求五份正文全載入。 |
| 新三層設計 | 前版缺少可直接審查的 description／Prompt 文字及完整輸入／回傳／錯誤表，本輪已補[草案](../../../specs/2026-10-05-jd-and-reference-demand-loading-design.md#44-輸入成功回傳與空值)。尚非正式 schema、部署或 provider／模型品質驗收。 |
| 保存／恢復 | 本輪沒有改原 request／command／output。前輪 runner／PostgreSQL 證據見[接線驗證](agent-integration-verification.md)。 |

## 三項反例與責任

### 1. 選用是替換，工具文字未明說

既有選用為 `ref_frontend + ref_backend`，傳入 `reference_ids=[ref_frontend]` 後，實際只留下 frontend。[Domain](../../../../apps/api/src/caliburn/features/occupation_references/models.py)的 `select_references` 以 replace 更新並精確去重；[工具 description](../../../../apps/api/src/caliburn/transport/model_tools/occupation_references.py)只寫「更新」，[參數說明](../../../../apps/api/contracts/tools/select-occupation-references-arguments.schema.json)也沒有說要把欲保留的舊 ID 一起提交。

原因是模型文字沒有完整交代集合替換意圖，不是保存出錯。候選修正為「本次完整選用集合，取代舊集合，欲保留的 ID 一併填」，保持原 Domain 行為。不能以新增 merge 行為避開說明問題。

### 2. 搜尋參數錯誤的下一步指向另一工具

`search_occupation_references({"query":"   "})` 正確拒絕且零外部呼叫，卻回：

```json
{
  "status": "rejected",
  "code": "invalid_arguments",
  "message": "參數、公版定位或排除範圍更新不合法，本次未改。",
  "next_action": "使用工具定義的欄位；移除請用已有排除範圍的精確文字，add/remove 不重疊且至少一項非空。"
}
```

原因是讀取與寫入都套用同一 `_invalid_arguments()`；現有測試核對 code／未呼叫上游，沒有核對下一步是否適用本工具。候選修正是在現有錯誤入口依實際工具給合法填法，不新增 validator 或另一套錯誤 envelope。

### 3. 寫入成功回傳沒有同等容量處理

以現行 tool handler、既有記憶體 fixture 及 64 字元上限核對：完整 state 讀取回 `read_limit_exceeded`；同內容的寫入成功則回 **244 字元完整 state**。這是小上限的工程反例，沒有真的寫 DB，也不是 production 已超量事故。

原因是 invoke 有輸出上限，execute 直接序列化整份 state。後續應獨立比較最小已成立效果／必要差異與完整 state 的回傳策略；不能在成功後用 rejected 冒充沒保存，也不能把已返回的原生結果事後縮寫。本輪不改現行正式成功格式。

## 執行與結果

本輪從 `apps/api` 執行下列相關離線檢查：

```powershell
& .venv/Scripts/python.exe -m pytest tests/unit/test_occupation_reference_tools.py tests/unit/test_occupation_reference_client.py tests/unit/test_reference_tool_registration.py tests/unit/test_excluded_work_reads.py tests/contracts/test_jd_read_tool.py tests/contracts/test_tool_schema_strictness.py -q -p no:cacheprovider --tb=short
```

結果：**173 passed in 2.05s**。這些測試證明既有行為與 wire，沒有推翻上述模型可用性缺口。未新增三項「已修正」測試，因本輪只審核、沒有改產品程式。

[audit_tool_contracts.py](audit_tool_contracts.py)另執行三項有界反例，[完整輸入、輸出及來源 SHA256](tool-contract-audit-probes.json)已保存。它使用既有記憶體 fixture 及真正 Domain／tool handler；零 DB、HTTP、GPU、模型及付費呼叫。重算：

```powershell
& .venv/Scripts/python.exe ../../docs/plans/evidence/2026-10-05-occupation-reference-tools/audit_tool_contracts.py
```

未改正式工具、schema、Prompt、環境檔或共用服務。規範靜態核對、離線 wire、provider 接受及模型正確選讀仍分開回報；不能把本輪合格的 schema 稱為所有規範與品質均通過。

## 官方核對

2026-10-05 透過官方文件 connector 核對 [OpenAI 定義函式](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)：名稱、參數、輸出含意與使用時機須清楚；[strict](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)要求 object 禁止額外欄位、properties 均 required，nullable 表達可空；[結果格式](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)由開發者定義字串內容。這些官方契約不保證工具說明可用性，也沒有替本案指定成功／錯誤 schema。
