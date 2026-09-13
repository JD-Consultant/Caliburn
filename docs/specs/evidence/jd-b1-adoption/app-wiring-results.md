# B1 接進新 App：完成訪談 → 既有詳記與工作資訊抽取

2026-09-14；JD-R002／OI-01、OI-02。依[採用映射 §6.2](../../2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)與本輪工作單位定義，基準 `353c400b`／tag `jd-b1-core-adoption-20260913`。

**B1 是訪談資料整理進 Memory 的既有階段**，不是重新設計 JD 編輯器，也不是另一個使用者頁面。本片只把已完成的 B1 接上新 App 的來源 owner 與 OpenAI，**不重做 B1、不改整個顧問**。

## 1. 只新增 App 端適配器

新增兩個檔案層級的東西，其餘全部沿用：

| 新增 | 內容 |
|---|---|
| `jd_relational/extraction_app.py` | OpenAI 綁定、`accepted` 終局證據、`ExtractionSourceAdapter`、`build_extraction_workflow` 組裝 |
| `ConversationSourceService.window_bounds` | 8 行唯讀存取器：由 owner 自己發出的引用回該窗口的回合界線，讓呼叫端**不必自己解 token**。無 I/O、無新狀態 |

**沒有**新增 parser、Agent loop、資料表、第二份游標、第二套流程或第二個原話 owner。訪談整理、驗證、更正、保存、續作、重抽全部留在 `caliburn_memory.extraction`，本片一行都沒改它。

### 來源接線（`ExtractionSourceAdapter`）

| B1 需要 | 接到既有 owner |
|---|---|
| `validate_reference` | `validate_window_reference`（只接受完成窗口；本輪 source 與 context 皆拒） |
| `extraction_windows` | `window_bounds` → `plan_windows` |
| `read(ref, offset)` | window → `read_window`（分頁）；context → `read_context` |
| `validate_saved_window` | 同名 |
| `require_new_source_after` | `follows` |

規劃、分頁、重驗與 admission 的權威仍在 owner；adapter 只綁 document 並把固定錯誤碼翻成套件的可更正位址錯誤。

### 用途授予（原複核指定隨接合驗的三項之一）

B1 的 extraction artifact 要驗 **source 與 context 兩個**引用，所以組裝用 `MemorySourceReader(..., window_references=True, context_references=True)`。C repair 與四個只讀工具維持 source-only 預設未改；B2 發布仍只收 window 作 `processed_source`。

## 2. OpenAI 接受條件：不是 HTTP 200 就算成功

`accepted(raw)` 用**已驗的同一組公開 SDK 欄位**判斷，沒有自己發明規則：無 refusal 區塊、且 `response_metadata["status"] == "completed"`。工作流程另外要求 `parsing_error is None` 與三個字串欄位的形狀成立。

2026-09-14 核 [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)：官方要求應用在信任結構化輸出前檢查三件事——`status` 為 `completed`、內容不是 `refusal`、符合 schema。**截斷**由同一個 `status` 表示：達到輸出上限的回覆是 `status: "incomplete"`、`incomplete_details.reason: "max_output_tokens"`，不會變成一個短的成功。這正好是上述三項，已驗邏輯不需改寫。

模型綁定另設 `truncation="disabled"`（輸入過長要明示失敗，不默默縮短來源）與 `store=False`（權威記錄是本 App 的 Saver 與 Memory，不是 provider）。B1 的角色預算是**本案實測值**：顯式 `max_output_tokens=8192`、`reasoning.effort="high"`，不是廠商預設，也不是顧問的配置。

**顧問的 Anthropic 設定完全未動**：沒有全 App provider 切換、沒有 fallback、沒有使用者選單。只有 B1 綁 OpenAI。

## 3. 相依性

`uv add langchain-openai==1.6.0`（與已驗 checkout 同一個 pin）。lock 差異是**純新增**，既有套件一個都沒有升版：

| 新增 | 版本 |
|---|---|
| `langchain-openai` | 1.6.0 |
| `regex`（transitive） | 2026.9.10 |
| `tiktoken`（transitive） | 0.14.0 |

未變：`langchain` 1.4.0、`langchain-core` 1.6.3、`langchain-anthropic` 1.7.2、`langgraph` 1.2.11、`langgraph-checkpoint` 4.2.0、`openai` 3.13.0。

**要標明的差異：**已驗 CT50 profile 跑的是 `openai==3.8.0`，本工作區是 `3.13.0`。測試的合成回覆一律經**實際安裝的** SDK `Response` schema 驗證，所以線上形狀是對現行版本核過的；但 CT49／CT50 的自然品質結論是在 3.8.0 上取得的，不自動延伸。

## 4. 實際執行

首敗為 `ModuleNotFoundError: No module named 'jd_relational.extraction_app'`。實作中有 5 個首敗是**測試自身假設錯**（`InMemoryStore.batch` 唯讀故改用真 Store 子類、長訪談窗口的結尾是該輪回覆而非員工原話、預設預算下三輪只切成一個窗口所以沒有 context、LangGraph 會在錯誤訊息後附任務名、`capture` 需要最新一輪），已修測試，**未放寬產品**。

| 範圍 | 結果 |
|---|---|
| 新增 B1 接線案例 | **13 passed** |
| App 全離線測試 | **2789 passed／257 skipped／51.63s** |
| Memory 套件全測 | **146 passed** |
| 真 PostgreSQL 18：原話來源＋C 顧問接合＋Memory 核心 | **14 passed** |

固定情境涵蓋工作單位要求的七項與四項驗證：

| 情境 | 結果 |
|---|---|
| 正常完成 | 三欄位成稿；`source_window` 讀回的**就是**該窗口自己的 `{source_reference, context_reference}` 原對 |
| 拒絕 | `refusal` 區塊 → 明示失敗，Store 內沒有任何 interview 產物 |
| 截斷 | `status: incomplete` ／ `max_output_tokens` → 明示失敗，未保存 |
| 格式錯誤 | 缺欄位的結構 → 明示失敗，未保存 |
| 不可讀格式 | 2100 字元單行先被拒，帶 runtime feedback 更正一次後才保存 |
| 重試 | 500 後重試成功 = **2 次 HTTP、1 個模型步、1 組產物**，不會變成兩個窗口 |
| 保存失敗 | 真 Store 注入一次寫入故障；`resume()` 續作**沒有再呼叫模型** |
| 已完成內容 | 窗口只涵蓋安全收尾的回合，出站 payload 帶真實員工原話 |
| 分頁讀取 | 超過單頁 3000 字元的窗口逐頁讀回完整原話，每頁都完整列出 turns |
| 來源重驗 | 同批每個規劃 pair 都在自己的固定位置重驗通過 |
| context 權限 | context 可讀（供消歧）但**不可**作為 B1 入口；本輪 source 兩者皆拒 |
| 重抽（W-13） | 讀回**原**窗口與**原** context，正常 B1 輸入位置不前進 |
| 出站請求 | `store=false`、`truncation=disabled`、`json_schema` + `strict=true`、三欄位 schema、8192、effort high |

替身只有一個：provider 的 HTTP 傳輸（`httpx.MockTransport`，回覆經實際 SDK schema 驗證）。來源 owner、Saver、Store、SDK、結構化輸出綁定全部是真的。**0 provider、付費 0**；`api_key` 是必填參數，程式不讀環境變數、不內建任何端點。

## 5. 限制與未完成

1. **沒有呼叫真模型**，沒有自然品質、真人或成本證據；真模型另需當次明示費用授權。
2. **B1 尚未被 App runtime 觸發**：`build_extraction_workflow` 可組裝，但宿主啟停、背景准入、排空與新程序續作（映射 §3.3–3.4）未接，模型 id／金鑰／配置也還沒接上本機設定。
3. **CONTEXT_ONLY 的 `turns` 是空陣列**——這是與已驗 payload 的一項**刻意差異**，需要複核確認：契約上 context 位置不帶回合界線（`_ContextPosition` 無 run bounds），且 CONTEXT_ONLY 只供消歧、不得被當成另一段待整併來源；舊 reader 對 context 範圍會投影 turns。`segments` 與 `omitted_content_types` 沒有差異。
4. `openai` SDK 版本與 CT profile 不同（3.13.0 vs 3.8.0），見 §3。
5. B2 採用、背景接合、整理通知完整單位、H4 完整旅程與自然品質（OI-09）都未開始。
6. 沒有新增資料表、第二份游標、第二個原話 owner；正式產品（`apps/api`／`apps/web`／`packages/job-analysis-contract`）未改，ADR0074／0075 Proposed、production 0060 不變。
