# 完成窗口 c1c9f8f7 複核與接續界線

## 修正後窄複核：R-01／R-02 CLOSED

2026-09-13，受審提交 `3cbd3ca5`／tag `jd-window-admission-position-20260913`；[實作者結果](admission-position-results.md)。以下為最新判定，後文保留 `c1c9f8f7` 的首敗與診斷，不再作未修阻擋。

- **R-01 CLOSED**：重驗改用既有 `root_run_id`，所有規劃 pair 在追加一輪後仍可讀回原內容；planner／pair 未重新發配。
- **R-02 CLOSED**：新窗口先驗其固定 root 位於 canonical 鏈，再以新窗口固定位置核舊游標與完整終點、先後及連續性；共用 `_on_lineage`／既有 `ancestor_of`。沒有另造持久狀態、分支或恢復引擎。
- 獨立執行來源＋歷史與原兩個探針：**59 passed／6.23s**（57 既有檔案例＋2 重疊探針，不宣稱 59 種不同情境）。另以既有 native fixture 規劃三個同 root 窗口，逐對驗 `follows`，再追加第四輪重驗，兩次皆通過；這是補核正常接續，不是 B1 已接。
- 本次未重跑實作者的 App 2776／Memory 130／PostgreSQL 14；`PG18` 指 PostgreSQL 主版本，並非 18 個測試。沒有 provider、新程序、自然模型或 UI 驗收。
- **本輪未發現新的阻擋問題；停止擴測。**F-02／F-04／F-05 仍照本稿降為相應 adapter 的整合驗收，W-14 source 層既有閉合不重開。下一單位依採用映射 §6.2 接 B1，原 prompt／輸出與已驗角色配置保持，接合時一次驗原 pair、用途讀取、重抽及正常輸入位置不前進。通知仍完整接合，留後續，日常 AI 不提前啟用。

工作區處理：本輪起始看到的 18 個 tracked dirty 路徑與上一輪交付後清單一致；決策入口差異確實非格式雜訊（本輪讀到 444 新增／38 刪除），但不能由此推定是本次誤還原，也未認定全部舊紀錄正確。保留既有差異，僅更新可核實的最新入口與接續路由並精確暫存本輪 hunk；不以確認整批歷史作為 B1 前置。

## 原始複核（c1c9f8f7，保留首敗）

2026-09-13；JD-R002／OI-01、OI-02。受審 HEAD `c1c9f8f7`，tag `jd-window-cursor-lineage-20260913`。本稿是獨立複核，不是產品修正；下述測試皆為合成資料、原生 InMemorySaver、零 provider。

## 結論

**保留此修正；F-03 已閉合，F-01 的舊游標側已修，但不能宣稱整個 admission lineage 已閉合。**另發現上一片留下的正常多窗口重驗錯誤。先在同一 source owner 做兩項窄修，再接下一完整 H4 工作單位；不重選框架、不新增表、第二份游標或通用驗證引擎。

本稿取代[上輪審查](../2026-09-13-jd-window-source-implementation-review.md)對 F-02／F-04／F-05 的缺陷分級及「未驗 B1 就不准接 B1」門檻；原稿保留為歷史，不能照該循環門檻施工。

## 仍須修正的兩項

### R-01／P2：正常規劃的非末尾窗口無法重新驗證

位置：`experiments/jd-relational-app/src/jd_relational/conversation_sources.py:797`，`validate_saved_window`。

`plan_windows` 把同批窗口固定在共同 root，並已刻意區分 `root_run_id`（讀回該 root 的身分）與 `last_run_id`（這個窗口的最後回合）。但重驗用 `position.last_run_id` 去讀共同 root。非末尾窗口兩者不同，`read_window` 原本可讀，後續 `_pinned` 卻回 `source_not_available`。這是正常公開規劃產物就能觸發的既有漏，不是 c1c9f8f7 新增，也不需要等 B1 才能修。

反例沿既有三輪訪談，`max_chars=20/context_chars=10` 產生多窗口，逐一 `read_window` 再 `validate_saved_window`；第一個就失敗。原測試只選 `planned[-1]`，恰好避開這個差異。已驗 B1 的 `reextract` 確實會先呼叫 `validate_saved_window`，因此接合後會阻擋前面窗口的詳記重抽。

最小修法：依 token 既有的 `root_run_id` 在原固定位置讀取；保留預算及用途檢查，不改 planner 為每個窗口另取 root、不重新發配原 pair。驗收遍歷所有公開規劃的 pair，並加入後續回合後核仍讀回原 pair／原文字。B1 的輸入位置不前進另外留給實際 adapter 驗收。

### R-02／P2：follows 仍未檢查新窗口自己的固定位置

位置：同檔 `:817–825`，`follows`。

這次 `_cursor_boundary(previous, observed, turns)` 已檢查舊游標，但 `observed` 是最新 head，`reference` 只解碼並使用 `new.first`。新窗口自己的 root、完整範圍及與舊游標的固定位置關係仍未核對。契約 §7.2 要求的是舊游標與**新窗口固定位置**的祖先關係，不能只證明舊游標在 latest 上。

反例完全使用公開發配：從第二輪終局產生 A 分支，在 A 以 `capture_window` 發配第二輪窗口；再從相同終局產生 B 兄弟分支作目前 head。两分支訊息相同，舊游標是第一輪共同祖先。原生 parent 鏈證明 A 不是 B 的祖先，`read_window(candidate)` 仍可讀其保存內容；但 `follows(candidate, previous)` 沒有拒絕，首敗為 `DID NOT RAISE`。**可歷史讀取不等於可作目前新批次的輸入。**這是同一個 F-01 尚未閉合的另一端，不是要重寫已修的舊游標驗證。

最小修法：在既有 source owner／AiRunHistory 內，以新窗口自己的固定 root 驗其範圍與所屬鏈，再比較舊游標到該位置的連續順序；若 admission 另檢目前 head，也不能替代兩引用之間的核對。不新增 lineage 表、通用分支管理或 latest fallback。回歸須保留同 root、正常祖先及同批連續窗口能通過，兄弟分支拒絕；歷史重抽仍走獨立重抽，不套新 admission 規則。

## 本次確認可接受

- 三個舊游標反例及既有正向案例通過；`ancestor_of` 使用公開 parent links，與 `find` 共用類別／查找界線。這是現有資料責任內的有限檢查，沒有另造持久權威。
- 超過 `MAX_PARENT_LOOKUPS` 與缺鏈案例皆明示 `original_run_lookup_required`。**F-03／W-14 的 source 層要求已完成**，不因 B1 尚未接而再要求此案重做；長訪談可操作性仍沿 OI-05，不在本片重寫。
- 實作者不先塞半套整理通知的決定正確。通知、結果分類、關閉／停止恢復須為同一完整單位；純通知不借 JD operation 或 C publication。
- 本次沒有改 JD 欄位、十三張關聯表、共同業務保存、Memory publication／原話責任，也未接回舊 Plate 編輯器。

## 修正上輪審查，避免多餘設計

| 舊項目 | 本次定性與接續要求 |
|---|---|
| F-02／W-13 | 撤回 P1 分級。它是 B1 尚未接的整合驗收項，不能拿它阻止 B1 施工。接上已驗 `reextract/resume_reextraction` 後，驗原窗口／原 pair 與正常 B1 輸入位置不前進；不現在仿造一套 B1。上面 R-01 則是已實作 source 層的實質錯誤，兩者分開。 |
| F-04／pair | 撤回「source 層必須證明 pair 曾一起發配」作為獨立缺陷的結論。`4f94fbfb` 的 `reextract` 由 `artifacts.extraction_window(summary_path)` 取得原 pair；現有 `MemoryArtifacts.source_window` 讀 App 寫入的不可變 metadata。契約要求沿原 pair 續作，不等於要求新配對 token／登記表／通用驗證引擎。B1 接合須驗兩份詳記各讀自己的 pair、不接受模型指定替換；若新 adapter 真暴露任意配對入口，再針對實際入口補拒絕案例。 |
| F-05／reader grant | 撤回獨立 P2 缺陷分級，改為已知 B1／B2 接線驗收。用途感知讀取隨實際 consumer 接；B1 extraction artifact 需 source＋context，publication 的 processed_source 不能是 context；不可把所有 B2 消費者一概當成只需 window。C／本輪四讀工具預設限制保留。 |

上輪「不能進 B1／B2」與「B1 接上後才能補 W-13」互相矛盾，是審查造成的不合理施工門檻，本次撤除。映射 §6 原順序是 source→B1→B2→背景→顧問／通知；通知可作獨立完整單位先做，但這是施工排序，不是大廠要求，也不是 B1 的必要前置。日常 AI 仍須等完整旅程通過才可啟用。

## 文件與官方證據核對

- [9/12 關聯式保存](../../2026-09-12-jd-relational-schema-and-write-contract.md)、[Agent 工具契約](../../2026-09-12-jd-relational-agent-tool-contract.md)：App 承擔引用、版本及真實保存結果；JD current 是關聯 rows，Memory／原話不雙寫。
- [9/13 完成窗口契約 §3／7／9](../../2026-09-13-jd-interview-window-source-contract.md)、[採用映射 §3–6](../../2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)：固定 pair、完整回合、新 admission 與既有重抽分開；採用已驗顧問，不重新設計其 prompt／工作規則。
- [9/13 C 完成核心](../../2026-09-13-jd-memory-repair-core-slice.md)、[App 當輪來源](../../2026-09-13-jd-consultant-source-integration-slice.md)、[接續計畫 H4](../../../plans/2026-09-13-jd-app-continuation-handoff.md)：本次不能倒退 C 的原結果查回、把 C source 當 B1 窗口或新增第二 owner。
- 2026-09-13 重查 [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) 與 [time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)：公開 `checkpoint_id` 可指定保存位置，`parent_config` 是前一 checkpoint；`update_state` 從指定位置產生分支，不是刪除／回滾原歷史。本地 lock 為 `langgraph==1.2.11`、`langgraph-checkpoint==4.2.0`，已發布 API、MIT，以上用同版本 native fixture 核對。官方提供原語，**沒有替本案規定 token 欄位或 admission 演算法**；這些是依本案契約的有限整合，不稱跨廠共識。
- OpenAI／Anthropic 的 App 執行工具與結果責任沿上述 9/12–9/13 已研究契約；本片未改模型契約，無需重選工具或再廣搜相同問題。

## 實際執行與交接

| 本次獨立執行 | 結果 |
|---|---|
| `test_interview_window_source.py`＋`test_ai_history.py` | **55 passed／9.51s** |
| [兩個新增複核反例](review-c1c9f8f7-probes.py) | **2 failed／7.07s**，期待正確行為，首敗保留；不是產品修正通過 |

實作者的 2774／130／真 PG18 是其報告，本次沒有重跑或冒稱獨立驗證。沒有自然模型、真 PG、新 Windows 程序或 UI 測試。兩個新增反例是本次收斂結果，不表示其餘未接 H4 已完整審過。

重現：在 `experiments/jd-relational-app`，設 `PYTHONUTF8=1`、`PYTHONPATH=src;tests`，執行 `uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q -p no:cacheprovider ../../docs/specs/evidence/jd-interview-window-source/review-c1c9f8f7-probes.py --tb=short`。首敗為 R-01 `source_not_available`／R-02 `DID NOT RAISE ConversationSourceError`。

下一單位只修 R-01／R-02，將探針轉入既有來源測試並窄複核；然後可按既有路由做完整通知接合或 B1 採用。W-13／reader／原 pair 的整合證據在相應 adapter 一次補齊，不再拆出沒有產品效果的中間架構。
