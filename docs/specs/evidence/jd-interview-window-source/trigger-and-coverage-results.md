# 完成窗口：整理通知採用、觸發清單與連續安全範圍

2026-09-13；JD-R002／OI-01、OI-02。接續[分頁讀取](window-read-results.md)，實作[契約](../../2026-09-13-jd-interview-window-source-contract.md) §6／§7.1 與 §7.2 的游標比較。基準 `cc179ab1`／tag `jd-window-read-20260913`。0 provider、沒有新增資料表、沒有第二份游標。

## 採用，不是重寫

整理通知依[採用映射 §3.5](../../2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)取自已驗來源 `4f94fbfb` 的 `consolidation_request.py`，落點 `caliburn_memory/requests.py`，**與固定來源逐位元相同**（`6965d106…`，只改模組名，無 `analysis_agent` 依賴）。模型可見的工具描述是已驗文字，採用時**一字未改**。`adoption.json` 已登記。

工具本身是純通知：無參數、回 `content + artifact{kind}`，不執行 B、不寫 Memory、不宣稱整理完成。

## 觸發與範圍是兩件事

這是契約審查 F1 點名的界線，實作照此分開：

| 方法 | 回答什麼 |
|---|---|
| `pending_windows(document_id, after_reference=None)` | **只**回「哪一輪明示要求排程」的觸發清單 |
| `unprocessed_source(document_id, after_reference=None)` | dispatcher 實際可處理的**連續安全範圍**；範圍內沒有通知的安全回合照樣納入 |

範圍止於第一個未安全收尾的回合，因此**後面的通知不會跳過缺口先被列為目標**。

## 游標只比較，不另存

`after_reference` 只接受 publication head 自己的 `purpose="window"` 引用。當輪 `purpose="source"` 引用被拒；游標終點若不在本 lineage 的固定對話上，**停止 admission**——不重設游標、也不解讀成「還沒處理過」。本 port 不保存第二份游標，也不寫 publication。

## 一項實測發現

W-12 的「同一 call id 出現兩次」**無法經 App 的保存路徑產生**：`AiRunCheckpoints.close` 的既有不變量就會拒絕重複的 `tool_call_id`（`invalid_closure`）。這比辨識層的歧義規則更強。測試如實改成兩段：可保存的壞形狀（孤立 call、純文字、`status="error"`）走真實保存路徑；歧義形狀直接對辨識函式斷言，並記錄它在保存層已不可達。

## 實際驗證

首敗：9 個新案例全紅（`pending_windows`／`unprocessed_source` 不存在）。另有一個測試構造首敗（重複 ToolMessage 共用 message id）暴露了上述保存層不變量，已改測試而非放寬產品。

| 範圍 | 結果 |
|---|---|
| 本檔案案例（累計） | **22 passed／4.31s** |
| App 全離線測試 | **2762 passed／257 skipped／47.05s** |
| Memory 套件全測 | **130 passed／4.28s** |
| 真 PG：C 接合＋原話來源＋Memory 核心＋AI runtime | **18 passed／12.42s** |

## 固定情境進度

| 已涵蓋 | 尚未涵蓋 |
|---|---|
| W-01、W-02、W-03、W-04、W-05、W-07、W-08、W-11、W-12 | W-06、W-09、W-10、W-13、W-14 |

## 明確**沒有**做的（下一片）

- **工具尚未註冊給顧問。**辨識規則已可用，但 `request_memory_consolidation` 還沒加進 `build_consultant_tools()`，所以顧問目前**發不出**通知。註冊會改動模型可見工具清單與既有 `expected_tool_count` 斷言，屬[映射 §6 第5項](../../2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)的顧問接合。
- **窗口切分與 `context_reference` pair**（§3.3／§7.3）：`max_chars`／`context_chars` 預算、消歧前置問題、`max_windows` 超限保留尾端、重抽回原窗口。`capture_window` 目前一次發配整段安全範圍，**沒有按預算切分**（W-06、W-13）。
- **B1 admission 的 `follows`**（§7.2 不回退且連續，W-09／W-10）：目前只有游標比較，沒有獨立的 admission 檢查。
- **W-14**：>256 祖先／缺鏈由既有 `original_run_lookup_required` 明確保留並向上傳遞，仍未建立案例。

## 界線

1. 這是契約的第三片，**不是 H4、B1／B2 或完成窗口能力已接通**。
2. 顧問還不能發出整理通知（見上）；觸發清單目前只能辨識測試或未來接線後產生的請求。
3. 全部為離線與固定 fixture，沒有 provider 呼叫；日常 AI 未啟用。
4. 沒有新增資料表、第二份游標或第二個原話 owner；C repair 與四個只讀工具未改。
