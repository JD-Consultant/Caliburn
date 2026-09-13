# 完成窗口引用：用途隔離與 B2 發布驗證

2026-09-13；JD-R002／OI-01、OI-02。[契約](../../2026-09-13-jd-interview-window-source-contract.md) §2／§3.1 與[契約審查 F2／F4](../2026-09-13-jd-window-source-contract-review.md)的第一片有限實作。基準 `b133a5b4`／tag `jd-window-source-contract-review-20260913`。0 provider、沒有新增資料表、沒有改 JD 格式。

## 為什麼先做這一片

審查 F2 指出的是**整合斷點**，不是風格問題：`PublicationStore._validate` 對 `kind="consolidation"` 會走 `artifacts.validate_source(processed_source)` → `SourceReader.validate_reference`，而 App 目前的 reader 只認 `purpose="source"`。因此在補上用途感知之前，B2 的完成結果**永遠無法發布**。這條路徑是純驗證、不讀內容，可以獨立閉合。

## 這一片做了什麼

| 項目 | 內容 |
|---|---|
| 用途隔離 | `conversation_sources` 新增 `_WindowPosition`（`purpose="window"`，`last` 不綁 run_id，namespace 固定 root 鏈）與獨立 salt／prefix 的簽章 domain。共用同一 codec 類別、持久 key、dataset 與演算法，**不共用 salt**；兩種 token 互不驗證 |
| 轉折點防護 | `first` 必須等於 `first_run_id`：窗口一定起於回合邊界。若日後 run identity 不再是 HumanMessage id，這裡會明確失敗，不會靜默接受半個回合 |
| 用途感知 adapter | `MemorySourceReader` 新增 `window_references: bool = False`。只有背景抽取／整併路徑會授予；C repair 與當輪四個只讀工具維持預設 source-only，兩個 production 建構點未改 |
| 發布接縫 | 授予後 `kind="consolidation"` 可用完成窗口作 `processed_source` 並發布；未授予的 reader 同一請求被拒 |

## 明確**沒有**做的（下一片）

- **窗口內容讀取**：`MemorySourceReader.read` 與 `read_window` 的分頁投影（`segments`／`turns`／`omitted_content_types`／`next_offset`）尚未實作。目前授予 window 的 reader 能驗證但不能讀窗口內容。發布路徑不讀來源內容，所以本片自洽；B1／B2 的引用回查會用到，屬下一片。
- **窗口 planner**：逐輪安全終局、連續安全範圍、source/context pair、`pending_windows`／`unprocessed_source`／覆蓋比較與 lineage 證明。
- **公開發配路徑**：本片刻意不提供 `capture_window` 之類的公開發配 API。安全終局只有 planner 能確立，先給一個不檢查終局的發配器會製造不安全窗口；測試以 codec 內部發配，與既有 source 負面測試同做法。
- W-01–W-14 只完成與用途隔離相關的部分（W-07 與 W-08 的 purpose 分支）；其餘仍待 planner。

## 實際驗證

首敗：`tests/test_interview_window_source.py` 在實作前 **1 error during collection**，`ImportError: cannot import name '_WindowPosition'`。

| 範圍 | 結果 |
|---|---|
| 本片新案例 | **8 passed／7.15s** |
| App 全離線測試 | **2748 passed／257 skipped／60.39s** |
| Memory 套件全測（App 環境執行） | **130 passed／5.75s** |
| 真 PG：C 接合＋Memory 核心＋原話來源 | **14 passed／15.53s** |

八個案例涵蓋：窗口引用不可當當輪來源、當輪來源不可當窗口、兩個簽章 domain 互不可驗、跨 key／dataset／document 三個反例、reader 未授予時拒絕／授予時接受、以及未授予 reader 的 consolidation `prepare` 被拒而授予後可發布且 `processed_source` 正確保存。

## 界線

1. 這是契約的第一片，**不是 H4、B1／B2 或完成窗口能力已接通**。
2. 授予 window 的 reader 目前**驗證得了、讀不了**窗口內容；這是刻意的分片邊界，不是已完成的讀取能力。
3. 所有證據都是離線與固定 fixture，沒有 provider 呼叫，日常 AI 未啟用。
4. 沒有新增資料表、沒有第二份游標、沒有第二個原話 owner。
