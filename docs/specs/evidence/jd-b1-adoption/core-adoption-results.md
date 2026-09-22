# B1 採用（核心）：已驗抽取流程進入正常套件

2026-09-13；JD-R002／OI-01、OI-02。依[採用映射 §6.2](../../2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)，基準 `a0320f35`／tag `jd-window-admission-position-20260913`。0 provider、沒有新增資料表、沒有第二份游標、沒有第二個原話 owner。

**本片只做核心採用**：把已驗 B1 從固定來源搬進 `caliburn_memory.extraction`，並定出它對來源 owner 的實際需求介面。**App 接線（真 `ConversationSourceService` adapter、顧問 runtime、真 provider）不在本片**，沿 C 的 core→app 兩片節奏。

## 1. 採用方式：逐位元先落地，再只開兩個縫

`extraction.py` 先以 `git show 4f94fbfb:...` **原檔落地**（source sha256 `06dd3e8c…`），再只改必要處。可核對的事實：

- **INSTRUCTIONS 一字未改**，區塊 sha256 `83b14376…`，與來源相同。
- `ExtractionOutput` 三個欄位、欄位描述與 `readable_artifact` 驗證器未改。
- 窗口迴圈、`validate`／`prepare_correction`／`correct`／`save` 五個節點、遞迴上限算式、`corrections_used` 先扣再送、`start`／`resume`／`reextract`／`resume_reextraction`／`reextraction_config` 的續作與重抽規則未改。

### 縫一：不可簽章的舊 parser 不搬

`start()` 原本直接呼叫舊 `parse_reference(reference, document_id)`。改為 `reader.validate_reference(reference)`，走既有 source owner 的簽章驗證。契約已明示不搬無簽章 parser。

### 縫二：provider 組裝留在呼叫端（**新發現，需記錄**）

已驗 B1 綁 `ChatOpenAI`：`with_structured_output(..., method="json_schema", strict=True, include_raw=True, max_output_tokens=...)`，接受條件讀 `raw.additional_kwargs["refusal"]`、`content_blocks` 的 refusal 區塊與 `raw.response_metadata["status"] == "completed"`。

**新 App 全線是 Anthropic**（`ConfirmedChatAnthropic`／langchain-anthropic 1.7.2／anthropic 1.5.0），[runtime 切片](../../2026-09-13-jd-ai-runtime-and-tools-slice.md)明載「本輪真 Agent／SDK 接合只有 Anthropic，沒有新增 OpenAI runtime」。本機 `langchain_anthropic` 1.7.2 的 `with_structured_output` 有 `include_raw` 與 `method="json_schema"`，**沒有** `strict=` 參數；終局與拒絕證據在 Anthropic 是 `stop_reason`／`stop_details`，不是 `response_metadata["status"]`。

採用映射把 host／組裝／角色配置歸 App（§2 最後一列），所以本片的處理是：套件收下**已配置好的** structured runnable 與一個 `accepted(raw)` 埠，套件本身不出預設。`max_output_tokens` 隨 provider 組裝一起移到呼叫端。其餘拒絕處理邏輯（拒絕／parsing_error／三字串形狀任一不成立即失敗，不得變成空成功）原樣保留在套件內。

**這是必須明說的限制：prompt 與流程是已驗的，provider 接受條件在本 stack 上尚未驗。**CT49／CT50 是 OpenAI 上的驗收，不自動延伸到 Anthropic；真 provider 行為屬 App 接線片與 OI-09，不在本片宣稱。

## 2. 來源 owner 的實際需求介面

B1 對來源只需要五件事，寫成 `ExtractionSourceReader`（沿既有 `SourceReader`，同檔）：

| 方法 | 用途 | 新 App 對應 |
|---|---|---|
| `validate_reference` | 無 I/O 的簽章／scope 檢查 | `validate_window_reference` |
| `extraction_windows` | 規劃完整回合的 `{source_reference, context_reference}` 對 | `plan_windows` |
| `read(reference, offset)` | 分頁投影：`segments`／`turns`／`omitted_content_types`／`next_offset` | `read_window`／`read_context` |
| `validate_saved_window` | 重驗已保存的原對，不放寬不重規劃 | 同名 |
| `require_new_source_after` | 依原話順序的 admission | `follows` |

套件仍不保存原話、不存第二份游標；規劃、分頁與 admission 的權威都在 owner。

## 3. 實際執行

首敗為 `ModuleNotFoundError: No module named 'caliburn_memory.extraction'`，即缺模組本身。

| 範圍 | 結果 |
|---|---|
| 新增 B1 核心案例 | **16 passed** |
| Memory 套件全測 | **146 passed／14.15s**（既有 130 ＋ 新 16） |
| App 全離線測試 | **2776 passed／257 skipped／125s**（未因新模組改變） |

實作中有 4 個首敗是**測試自身假設錯**（`ExtractionFiles` 欄位是 `summary_path`／`candidates_path`），已修測試，未放寬產品。

案例涵蓋：三欄位成稿與來源 metadata、prompt 兩段分離（`CONTEXT_ONLY`／`NEW_SOURCE`）、每個窗口只抽一次、中途失敗續作不重跑第一個窗口、非法來源在呼叫模型前停、超過 `max_windows` 在呼叫模型前停、空 `raw_memory` 是成功、拒絕／`parsing_error`／形狀不符都不得變成空成功、格式不可讀先更正再保存、更正額度用盡即失敗、較早或重疊來源被拒、重送同一來源回原工作不再呼叫模型、重抽讀回原保存窗口且不推進正常 B1 位置。

雙替身只有兩個：provider 呼叫（回同一 `{raw, parsed, parsing_error}` LangChain 契約）與來源 owner。**artifacts 用真 Store backend**，發布、排程、整併與 JD 工具一律未涉入。

## 4. 仍然開著的（B1 App 接線片）

- 真 `ConversationSourceService` adapter：把上表五個方法接到 `plan_windows`／`read_window`／`read_context`／`validate_saved_window`／`follows`，並處理 window 與 context 兩種 ref 的讀取形狀差異（`read_context` 目前不回 `turns`／`next_offset`）。
- **W-13**（重抽讀回原窗口、正常 B1 輸入位置不前進）在真 adapter 上的證據；本片只有套件層雙替身版本。
- **原 pair 不可變**與 **reader 用途授予**：B1 的 extraction artifact 需同時驗 source 與 context，因此接線時要用 `MemorySourceReader(..., window_references=True, context_references=True)`；這正是複核指定隨 adapter 一次驗的兩項。
- **Anthropic 的 `accepted` 實作與真 SDK 固定回覆驗收**（含 `stop_reason`／終局證據），以及角色配置（effort／顯式 8192）落在 App。
- B2 採用、背景接合、整理通知完整單位、H4 完整旅程與自然品質（OI-09）都未開始。

## 5. 界線

1. 本片只做 B1 核心採用，**不代表 B1 已在新 App 可用**，也不代表 H4 有進展。
2. prompt／輸出欄位／角色語意未改；CT49／CT50 的驗收是 OpenAI 上的結果，**不延伸為 Anthropic 上的品質或接受條件保證**。
3. 沒有新增資料表、第二份游標、第二個原話 owner；C repair、四個只讀工具與 B2 發布路徑未改。
4. 0 provider、付費 0、日常 AI 未啟用；正式產品（`apps/api`／`apps/web`／`packages/job-analysis-contract`）未改，ADR0074／0075 Proposed、production 0060 不變。
