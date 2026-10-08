# 三、程式內部的責任分工

[報告目錄](README.md) · 上一章：[系統全貌](02-system-overview.md) · 下一章：[訪談執行](04-agent-execution.md)

## 把「分析什麼」和「怎麼安全執行」分開

![圖三：後端主要靜態依賴](../../diagrams/implementation/code-organization/python-dependencies.png)

[圖源](../../diagrams/implementation/code-organization/python-dependencies.mmd) · [SVG](../../diagrams/implementation/code-organization/python-dependencies.svg)

圖三由[程式組織的依賴圖](../../implementation/code-organization.md#2-依賴方向與可檢查限制)生成，箭頭表示主要允許的 Python import 方向，並非執行先後。流程層協調一輪訪談或一批整理；分析角色定義方法、工具及 Context，並使用共用執行層；業務模組判定修改是否有效、何時正式生效。共用執行層使用角色注入的工具，不反向 import 角色；執行時序另見下一章。

例如 A 想新增「整理出席紀錄」任務：模型決定任務內容與來源；工具接收型別化參數；App 提供所在職務檔案、執行資格與候選位置；JD 業務模組執行修改。模型不需要猜資料庫 ID、快照版本或交易結果。

## 模組依「變動原因」拆分

| 程式區域 | 負責的事情 | 不應承擔的事情 |
| --- | --- | --- |
| `transport/http` | 請求驗證、公開格式、回應與串流 | 複製 JD／Memory 業務規則 |
| `workflows` | A Turn、Memory 批次、跨模組完成與失敗流程 | 重複保存或判定其他模組負責的業務結果 |
| `agents` | 各角色的 Prompt、工具集與 Context 綁定 | 自己實作資料庫交易或通用恢復系統 |
| `agent_execution` | 原生模型項目、工具配對、有序執行、Checkpoint 與容量檢查 | 分析員工工作或決定 JD 的事實 |
| `features` | 職務檔案、訪談、JD、Memory、公版參考 state、執行身分的業務能力 | 呼叫外部模型來判定交易是否成功 |
| `adapters` | OpenAI、資料庫、Checkpointer、PDF、可選公版 HTTP 等外部機制接線 | 決定各角色應負責哪些產品行為 |

模組按各自會改變的責任拆分，例如調整角色提示、替換模型接線與修改 JD 保存規則，應有不同的修改位置。同一業務規則集中維護，避免模型工具、HTTP 與 UI 各寫一份。

實作上，純計算使用純函式，需要協作或管理生命週期的部分才封裝，不為每個檔案都建立介面、工廠與服務類別。

## 三個分析角色的非對稱分工

**A：職務顧問。** 直接訪談員工，讀取工作記憶與原話，按需編輯 JD，必要時要求背景整理。它不負責直接維護 Memory 兩層工作稿。

**B1：工作情境分析。** 從限定範圍的有效訪談整理具體工作情境，保留條件、過程、例外及未知；能讀寫情境，不能讀寫工作理解。

**B2：工作理解分析。** 依目前情境分析跨情境的工作理解，能讀情境、讀寫理解，並可按需回查合法範圍原話；不能修改情境，也不要求 B1 返工。資訊不足或矛盾須如實保留，不猜測補齊。背景整理採 B1 → B2 → 發布，流程見[第五章](05-work-memory.md#背景整理如何開始與交接)。

三者共用模型與工具的執行程式，但各自保有 Context 與工具權限。合作方式由流程與資料介面約束，不採用任意互相對話的模式。

## 前端也不另造資料真相

前端依職務檔案、訪談、JD 編輯與來源檢視劃分功能模組。伺服器資料由共用查詢機制讀取；人工編輯鎖定、候選呈現與暫停／取消控制使用同一份 Turn 狀態，避免多個元件分別保存而產生不一致。

例如「畫面收到一段回覆」與「後端已完成這輪」必須區分。UI 可以先顯示串流與候選，但正式完成要以後端結果為準。跨邊界 DTO 由正式契約生成，避免前後端手抄兩份不同格式。

### 延伸閱讀

[系統分工](../../architecture/system-boundaries.md)說明各模組的資料與互動，[契約策略](../../contract-strategy.md)說明前後端如何共用傳輸格式。具體合作方式可參閱 [A Context 綁定](../../../apps/api/src/caliburn/agents/job_consultant/context_binding.py)、[共用工具 Step](../../../apps/api/src/caliburn/agent_execution/tool_steps.py)與 [Memory 批次編排](../../../apps/api/src/caliburn/workflows/memory_batch.py)。
