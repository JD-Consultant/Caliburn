# H4-R1 第一步：固定 target 到有界批次

2026-09-14；JD-R002／OI-01、OI-02。實作[H4 計畫 §4 R1 第1點](../../../plans/2026-09-14-jd-h4-runtime-integration.md)與[映射 §3.6](../../2026-09-13-jd-consultant-b1-b2-adoption-mapping.md#36-固定目標到有界批次2026-09-14-接續設計)，閉合[整體審查](whole-flow-review.md) HF-02。基準 `f160be97` 加上本輪未提交的 HF-07。0 provider、沒有新增資料表、沒有新 parser／游標／配對引擎。

## 範圍與依據

只補 source owner 的兩個公開接點，B1 核心、prompt、預算與 `ExtractionWorkflow` 未改；`extraction_app.py` 未改。

| 接點 | 語意 |
|---|---|
| `unprocessed_source(document_id, after_reference=None, through_reference=None)` | 原行為不變。給固定 target 時改在該 target 自己的位置讀，範圍止於 target 本身的結尾 |
| `plan_saved_batch(target_reference, document_id, *, after_reference=None, max_chars, context_chars, max_windows)` | 回 `{"source_reference": str \| None, "covers_whole_range": bool}`。批次由 owner 以 target 的同一 root 發成**單一** window ref |

`plan_saved_windows()` 原本內嵌的「在引用自己的位置讀回並驗證範圍」抽成 `_pinned_range()`，由兩個接點共用；行為不變，不是第二套驗證。舊 `plan_batch()` 保留作既有規劃介面。

**caller 不解 token、不拼 first／last、不回 latest head。**批次的 `source_reference` 直接就是 B1 `start()` 吃的那一個引用；`covers_whole_range` 只表示規劃覆蓋，不表示已保存或已發布。

## 反例先行

六個反例先紅（`TypeError: takes from 2 to 3 positional arguments` 與 `AttributeError: 'ConversationSourceService' object has no attribute 'plan_saved_batch'`），再實作轉綠：

| 案例 | 釘住的行為 |
|---|---|
| `..._fixed_target_is_never_widened_by_later_speech` | 追加原話後，有 target 的答案止於 target；無 target 的答案才跟著 head |
| `..._bounded_batch_hands_b1_one_reference_and_keeps_the_tail` | 批次是單一 window ref，回頭規劃剛好等於前綴；尾端回合不在批次內 |
| `..._published_cursor_alone_moves_the_next_batch_to_the_tail` | 不需新通知，游標推進即接尾端；尾端發布後回 `{None, True}` |
| `..._target_already_covered_by_a_later_cursor_is_reported_covered` | 游標較晚且確實涵蓋 target → 明確「已涵蓋」，不是規劃失敗 |
| `..._batch_over_the_whole_target_reuses_that_very_reference` | 未動過的整段 target 原樣返回同一引用，B1 不會看到新 input identity |
| `..._target_pinned_to_an_abandoned_branch_is_refused_not_replanned` | 合法簽章的旁支 target 仍拒絕，不改用目前 canonical 分支重規劃 |

第七個案例 `..._later_cursor_that_stops_short_of_the_target_is_refused_not_covered` **一寫就通過**，故另做變異確認鑑別力（見下）：游標雖然較晚發出但其發布範圍未達 target 結尾時，必須 `invalid_ref`，不得回「已涵蓋」而把中間回合埋掉。

## 變異檢查

兩次都由本次實作者執行，改動前後以 `git hash-object` 核對還原（兩次皆回到 `9e30fc96…`）：

| 變異 | 結果 |
|---|---|
| `_pinned_range` 不截在 target 結尾（`turns[:last+1]` → `turns`） | `..._bounded_batch_hands_b1_one_reference_and_keeps_the_tail` 轉紅 |
| `_target_start` 拿掉覆蓋證明（`position.last not in order or order.index(position.last) > covered` → `False`） | `..._later_cursor_that_stops_short_of_the_target_is_refused_not_covered` 轉紅 |

第一個變異**沒有**打到「target 不被加寬」那條案例，因為該案例實際釘住的是**釘住位置**（target 的 snapshot 本來就不含之後的回合），截斷則是批次 ref 這種「root 比自身範圍長」的情形才生效。兩條性質各有殺得掉變異的案例，不合併宣稱。

## 實際執行

```powershell
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache `
  pytest -c pyproject.toml -q -p no:cacheprovider [範圍] --basetemp=S:/caliburn/.research-tmp/...
```

| 範圍 | 結果 |
|---|---|
| `tests/test_interview_window_source.py` | **50 passed／5.97s** |
| 受影響組（窗口來源＋B1 adapter＋來源＋聊天歷史＋Memory 套件） | **308 passed／11.12s** |
| App 全離線測試 | **2812 passed／257 skipped／42.18s** |

首敗（實作後）只有一個，且是**測試自身**的假設錯：斷言批次不含 `問`×10，但批次合法涵蓋第一個 plain 回合。已改成斷言批次回合是 target 回合的真前綴，沒有放寬產品。

## 限制與未完成

1. 這是 R1 的**第一步**，不是 R1 完成。真 PostgreSQL 的 B1 保存／恢復、`PostgresSaver`／`PostgresStore` 資源重建、故障注入與 HTTP 次數斷言**尚未執行**。
2. 全部為 InMemory 固定 fixture，**0 provider**。既有 C／source 的 14 條真 PG 案例不算 B1 已驗。
3. 背景准入狀態的持久落點仍未決（映射 §3.3）；本片沒有建表，也沒有第二份游標。
4. 游標較晚但未涵蓋 target 時本片選擇**明示拒絕**而非規劃剩餘範圍。這在「同文件只能有一筆未交接完批次」的前提下只會由 caller 誤用造成；拒絕不會靜默跳過回合。若日後證明需要在該情形續作，須另立反例，不在此擴張。
5. 「新範圍是否可被准入」仍只由 `follows()` 決定；批次規劃只把 target 自己的起點當下限，不重複一套 admission 規則。
