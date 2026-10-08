# Agent 持續對照與可觀測性的工程判準

- 日期：2026-10-08。
- 狀態：**研究依據，工程判準已整合；平台選型為候選**。2026-10-08 依使用者確認，將替換、對照與觀測判準整合至既有工程規範；後續澄清 MCP、插件及平台均可採用，應處理測試繁瑣與真人查閱困難。本頁保留選型研究，後續已落地的明示組裝、原始診斷及有限對照入口見[工程證據 O1／E1](../../plans/evidence/full-system-review-2026-10-08.md)；候選平台不因此成為現行依賴。
- 目標：讓 Prompt、Tool 與元件能持續比較，並沿實際輸入、工具正文與正式結果找出改善位置。本研究聚焦對照與觀測；整體模組仍依[程式組織](../../implementation/code-organization.md)的責任、內聚與依賴規範設計。

## 官方資料支持什麼

| 第一手來源 | 可借鑑的事實與界線 |
|---|---|
| [LangSmith：Evaluation concepts](https://docs.langchain.com/langsmith/evaluation-concepts) | Experiment 對應特定應用版本在資料集上的輸出、評分與 trace；資料集可固定版本，參考答案供評閱而非送給受測程式。部署後發現的問題可回到離線案例。這是平台能力，不要求 Caliburn 採用平台。 |
| [LangSmith：Evaluate a complex agent](https://docs.langchain.com/langsmith/evaluate-complex-agent) | 分別評最終回答、執行路徑與單步決策。局部容易定位原因，整體才能檢查累積效果；範例明示省略正式認證，不能拿示範安全界線當正式設計。 |
| [Anthropic：Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | 受測對象包含模型與 Agent 執行框架；要求接近正式行為及乾淨、隔離的每次嘗試。執行紀錄與環境最終結果分開；混合程式、模型及人工評閱，檢查逐字紀錄，避免把唯一工具順序當成功條件。 |
| [Anthropic：Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents) | 工具名稱、說明、參數及回傳都影響模型使用。除正確率，需看工具呼叫、錯誤、耗時、token 與原始工具往返；以保留例防止只對調整案例有效。 |
| [OpenTelemetry：工具執行及正文](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-spans.md#execute-tool-span)、[模型呼叫](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/client-inference.md) | 可關聯工具名、call ID、錯誤及模型用量；參數與結果正文為選用，可另存並分開控管權限。失敗只記實際取得內容，不補造輸出。兩份仍為 **Development**，不能當穩定欄位契約直接照搬。 |

## Caliburn 的設計判準與取捨

**比較應重用正式執行路徑，在已有責任邊界替換目標。** 這是依來源與本案模組化單體提出的取捨，不是廠商統一架構。

| 要比較的項目 | 應能做到 | 需保持可核對 |
|---|---|---|
| Prompt | 純提示比較在角色組裝替換具名提示，不改全域變數或複製整個 Agent | 實際送出的完整提示、模型設定、Context 與工具版本；整組方案消融另標範圍 |
| Tool | 可只改說明、schema、handler 或回傳；四者須相容，明標變因及必要連帶變動 | 模型實際看到的契約、呼叫參數與回傳；業務權限仍由後端裁決 |
| 元件 | 在真正替換點使用窄介面／callable；其他正式流程照用 | 被替換責任、依賴、狀態範圍與失敗語意；不新增每類一套 interface |
| 執行環境 | 配置由組裝根提供；每次比較的業務資料互相隔離 | 版本、初始資料、外部服務、取消／重試／timeout；測試不得繞過正式保存與資格 |

局部比較固定同一 Context，可回答「這句提示是否改善下一步」；長旅程讓 Agent 自主問答，可回答「最後 JD 是否改善」。後者即使員工背景相同，實際問答與取得事實也會不同，不能宣稱逐字相同輸入。多項同改只能先歸因於整組變更。

先以少量真實失敗與反例定位，再用未參與調整的案例驗證；必要時重複以觀察波動。工程契約、Agent 行為、JD 品質及成本分開報告。樣本不足就保留結論限制，不用增加抽象層代替證據。

## 既有規範已涵蓋的部分

- [程式組織 §2、§4](../../implementation/code-organization.md)：組裝根、薄入口、依賴方向、窄 I/O 替換點及一般 log 不放正文。
- [撰寫規範 §4、§7](../../implementation/coding-standard.md)：顯式依賴、資源生命週期、行為測試；不為測試另造全域 App 或萬用介面。
- [開發規範 §7–8](../../implementation/development-standard.md)：Prompt／工具與程式版控、基準與保留例、分辨失敗來源、品質與負擔、保存實驗配置及適合公開的原件。
- [本機診斷 runbook](../../runbook.md#在-datagrip-查某個職務檔案的-ai-執行紀錄)：已有按需 checkpoint 投影，可查當時模型請求、工具原參數、回傳與正式修訂。這是受控本機正文查閱，一般 log 不輸出正文；不完整匿名化，也不自動外送。

以上是文件已定義的責任，**尚未據此判定目前程式都已落實**。

## 從工具正文追到正式效果

觀測的審查判準是：指定一次工作，能關聯**模型原參數 → App 綁定的可信作用範圍 → 工具回傳 → 正式保存／採用結果**。同時可核對當時實際提示、Context、工具契約及版本；不只留下「成功」及總費用。

現行本機診斷及正式操作表可供核查；runbook 要求先執行擷取，再查 VIEW，新進展需重新擷取。這描述現有查法，不能證明真人操作時已容易定位。可接入現成 trace 平台、受控查閱介面或其他更合適的方式；觀測副本仍不取得恢復或業務裁決權。既有 `recorded` 只表示找到回傳，可能仍是錯誤；`not_recorded` 不能證明未執行。候選採用看正式資料，`snapshot_at` 正文是按需擷取，不冒充即時全量紀錄。

需以有限反例檢查成功、拒絕、timeout／取消／部分結果、重試關聯、跨職務隔離與憑證遮蔽。缺失、截斷及遮蔽應能辨識；診斷或匯出失敗不改正式 JD。統計與敏感正文分開控管，一般 log 不放正文，既有資料不因研究自動外送。

## 現成工具與平台：以實際操作成本比較

使用者已明確指出對照測試繁瑣、真人透過 UI 訪談時難查內部執行。這是當前工程問題；改善其操作體驗不屬於沒有用途的額外功能。下列為 2026-10-08 查閱官方文件後的候選，未安裝或驗證接線。

| 候選及第一手來源 | 能改善什麼 | 必須核實的界線與成本 |
|---|---|---|
| **MCP＋Inspector**：[Tools 規格](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)、[Inspector Web](https://modelcontextprotocol.io/docs/2026-07-28/tools/inspector/web)、[架構](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture) | 標準工具探索、Schema 及錯誤契約；Inspector 可輸入參數、呼叫工具並查看往返。薄 adapter 可讓測試客戶端與 App 共用正式工具服務，方便重現 patch 拒絕等問題。 | Inspector 是另一個 client，不會自動旁觀 App 的全部訪談；完整 Prompt、Context、Memory 與採用效果仍需 App trace。MCP 可用本機 transport，不要求上雲；要核共同支援版本、可信 scope 及副作用測例隔離。 |
| **Langfuse**：[instrumentation](https://langfuse.com/docs/observability/sdk/instrumentation)、[self-host](https://langfuse.com/self-hosting)、[OpenAI 整合](https://langfuse.com/integrations/model-providers/openai-py) | 現成 Web trace UI、Python 自動／手動 observations，可沿 OTel context 串起模型、工具與自訂業務步驟；能在本機部署，適合優先比較真人查閱體驗。 | Self-host 需 Web、Worker、PostgreSQL、ClickHouse、Redis／Valkey 與 Blob Store，須計維護成本。本次 wrapper 文件不足以證明 direct Responses、原生 items、compaction 全數適配；可比較手動 span。背景批次傳送不保證即時或無遺漏，關閉需處理 flush。 |
| **LangSmith**：[評測概念](https://docs.langchain.com/langsmith/evaluation-concepts)、[self-host](https://docs.langchain.com/langsmith/self-hosted) | 現成 trace、資料集、experiment、評分與 Prompt 工作流程，可比較是否降低案例重跑及結果整理成本。 | Self-host 屬 Enterprise add-on，需比較商業與部署成本；本輪未核完整 direct Responses 接線。平台可管理實驗，公平變因、職務資料隔離及 JD 品質判準仍由本案定義。 |
| **MSW（前端網路情境）**：[官方介紹](https://mswjs.io/docs/)、[覆寫與清理](https://mswjs.io/guides/best-practices/network-behavior-overrides) | 在網路層攔截請求，同份 handlers 可用於 browser／Node 測試及開發除錯，個別案例覆寫後復原。可比較是否讓延遲、拒絕、錯誤回應與切檔競爭更容易重現，同時保留正式 HTTP client／runtime 驗證。 | 候選，尚未接入；需核目前測試環境、串流、handler 隔離及使用成本。它證明受控網路下的 UI 行為，不能代替真 API／PG 交易與恢復測試；mock 也須跟正式契約一致，不能變第二份業務實作。 |

**建議優先驗證現成 trace UI 與實驗管理入口，並把 MCP 作為工具測試的互補候選。** 這些可以沿目前 runtime 接入，也可與替換 harness 一起比較，不以先換整套 Agent 為前提。正式工具規則、資料權威及恢復資格沿共同模組；現成平台負責呈現、關聯與比較，避免再手工整理另一份業務真相。

具體驗收以兩項操作為中心：

- **真人查閱：** 用 UI 完成一次訪談，依已知職務與輪次找到 execution／trace；可順序核對實際請求、Memory 綁定及實讀內容、工具原參數／執行值／結果、JD／Plan／Memory 正式效果、取消或重試。記錄查找步驟、耗時及缺少的證據，不能只驗平台收到了 span。
- **對照與回歸：** 選一個既有失敗案例，替換一項 Prompt／Tool／元件後沿相同正式流程比較；能確認有效配置、隔離資料及正式結果，並把案例納入下次回歸。記錄改動位置、手工作業與執行成本；另起新模型執行和只查既有 trace 必須分清。

模型 wrapper 不會自動知道 Memory 版本、App scope 或正式採用；需由 Context、工具及保存模組提供相應關聯。跨背景工作、恢復及重啟的 trace 關係亦須核實。必要正文可在受控入口取得；外送目的地、權限與保留依選定部署處理，本輪沒有自動上傳真人資料。平台選用尚未決定，現有查法仍可作比對原件。

## 後續維護位置與待驗範圍

替換接縫及依賴已整合至[程式組織](../../implementation/code-organization.md)；介面、觀測寫法與全面審查面向由[撰寫規範](../../implementation/coding-standard.md)維護；比較層級、公平性與回歸由[開發規範 §7](../../implementation/development-standard.md#7-分析方法prompttool-與-context-共同驗收)維護。診斷操作及執行語意仍沿 runbook／`agent-execution.md`，本研究只保留來源與取捨，不建立第二份規範權威。

Code review 應實查：更換一個 Prompt／Tool／元件是否只動相關組裝與責任模組；對照是否真正走同一正式流程；能否從一次異常取得原參數、結果及正式效果；失敗案例能否加入既有局部與旅程測試。尚未選定新增資料表、觀測平台或通用實驗引擎。
