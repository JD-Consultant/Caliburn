# CT09：長訪談中斷驗收與精確編輯失敗診斷

2026-09-07 · LLM-Q019／CT09 · **PAUSED：未通過整份工作驗收**。

後續狀態：Owner 已准局部編輯器離線比較，結果與下一決策見 [CT10](2026-09-07-memory-editor-framework-comparison.md)。下列「尚未授權」是 CT09 診斷當時邊界；CT10 並未改產品或讓本驗收變成通過。

## 閱讀路由與本輪邊界

- 目的／方法：[短驗收計畫](../plans/2026-09-07-long-interview-acceptance.md)。基準 `a9d87e0a`；隔離 `codex/analysis-only-agent`，不接 JD／production。
- 事實：[封存 evidence](evidence/2026-09-07-long-interview-acceptance.json)；員工視角：[9 輪逐字稿](evidence/2026-09-07-long-interview-acceptance.transcript.md)。長 request／工具內容只放 evidence，不貼進決策入口。
- 承接：[CT08](2026-09-07-interview-partial-knowledge-repair.md)；工作資訊取捨見主工作區 [研究](../../../../docs/specs/2026-09-07-work-case-and-understanding-information-selection.md)。不重開 Memory ABC 分層。
- Owner 最新要求是說明「精確修改為何反覆失敗、上限是否過低、官方如何處理」。本段僅診斷與候選，**尚未授權改用 patch、修改讀取格式、提高產品上限或改錯誤恢復政策**。

## 1. 實際完成與未完成

合成職位：電商售後營運專員（家用小家電）；先封存 8 個工作範圍、4 個案例與更正的 oracle，不送入顧問。自然回答中逐步透露資料，包含日常工作、角色界線、低頻安全事件、月報、FAQ、新人帶教。不是只完成一項任務就算驗收。

| 指標 | 實際結果 |
|---|---|
| 正常訪談 | 9 輪主 run 全部 completed；回覆 5.23–10.81 秒 |
| 生成請求 | 48，HTTP 均 200／response completed；不等於整併成功 |
| usage 估算費用 | US$0.04872353；未碰到本次 120 次／US$0.50 測試護欄 |
| 主訪談／B1／B2 呼叫 | 15／4／29 |
| B2 四批步數 | 6 成功、8 成功、7 成功、8 失敗 |
| 目前已發布理解 | revision 3；第 7 輪起背景 blocked，後續兩輪沒有自行恢復 |
| 整份工作、fresh reader、真實 compaction | **未驗完**；不宣稱完全涵蓋、長期記憶正確或已穩定 |

主顧問能沿近期對話理解退款核准人的更正，並繼續訪談其他工作；但新月報／FAQ／帶教資訊與更正未成功發布至新 Memory。第四批 B1 詳記／候選已保存，不代表 B2 已發布。第 8、9 輪原始對話保存，但尚未進下一批背景整理。這是「聊天可繼續，Memory 更新失敗」，不能混成 PASS。

## 2. 可重現的根因，不是猜測模型理解錯

實際版本：DeepAgents 0.7.13、LangChain 1.4.0、LangGraph 1.2.11。

資料流：官方 `FilesystemMiddleware.read_file` 顯示行號 → 模型填 `edit_file.old_string` → 本案 `StagedFiles.edit` 原樣轉交官方 StateBackend → `perform_string_replacement` 用 `content.count(old_string)` 精確匹配。

例如實際來源開頭是 `- 客戶選退款後…`，閱讀結果以「行號＋兩個分隔空白＋原文」顯示。第 40 次請求的 old_string 是 `  - 客戶選退款後…\n`：多了兩個空白，原檔沒有這段逐字字串。

最後一批的原始 request 與工具結果、離線官方函式重播一致：

| 請求 | 動作與結果 |
|---|---|
| 39 | 讀取目前 knowledge |
| 40 | 帶多餘行首空白修改退款核准人，String not found |
| 41 | 改用原句內部唯一片段，不帶行首縮排，成功 |
| 42 | 帶多餘縮排取代月報／FAQ／帶教段落與引用，String not found |
| 43 | 取代原段落內部唯一文字，成功，新增內容部分行本身有兩個縮排空白 |
| 44 | 重讀相關段落；顯示分隔空白加上真正縮排，肉眼共見四個空白 |
| 45 | old_string 使用四個空白，實際只有兩個，String not found |
| 46 | 繼續嘗試縮排調整；隨後模型步數上限中止，沒有完成發布 |

第 46 次的 tool result 未出現在下一次模型輸入，不能據離線重播宣稱其實際持久化成功。離線僅證明官方精確替換會如何處理；未寫 DB、未付費。

**結論：該批 6 次 edit 中 3 次精確匹配失敗。** 這是單一失敗批次的比例，不是整體 Luna 失敗率。額外空白與工具顯示格式一致；短片段修正成功，是介面與模型複製行為不合的直接證據。沒有證據顯示這三次是網路、權限、資料庫併發、strict schema、中文編碼或工作語意衝突造成。不能把所有過往錯誤都歸為同一原因。

本案 `MEMORY_EDIT_GUIDANCE` 已教模型不要帶行號／兩個分隔空白，並要求最小修正及保留舊細節。**提示已存在卻仍重現，因此不能只追加同一提醒就稱修復。** 後段部分步數還消耗在縮排外觀，並非新增工作知識。

程式定位：`experiments/analysis-agent/src/analysis_agent/consolidation_tools.py`、`memory_tools.py`；安裝套件 `deepagents/backends/utils.py` 的 `format_content_with_line_numbers`／`perform_string_replacement`。工具錯誤有回給模型，並非漏接結果；精確找不到不是適合原參數網路重試的錯誤。

## 3. 上限是放大因素，不是唯一根因

`ConsolidationService` 預設 8 次模型步數／12 次工具呼叫；每一步可以呼叫多個工具。它不是「最多訪談 8 輪」，也不是整次測試的 120 次護欄。錯誤是 `ModelCallLimitExceededError: thread limit (8/8)`。

前三批已有 6／8／7 步完成，顯示 8 的餘裕偏小；第四批消耗在失敗與縮排後，沒有留下完成正文／導覽／最終回覆所需步數。因此可以重新校準上限，但不能推論無限重試必然成功，也不能聲稱某固定數字是大廠最佳值。

OpenAI SDK 公開循環是模型→工具→結果→模型，直到 final 或可設定的 `max_turns`；也允許設成 None。這證明上限是應用選項，不是官方指定 8。LangChain 的 model／tool call limit 也是分開的可設定 middleware。[OpenAI Agent loop](https://openai.github.io/openai-agents-python/running_agents/#the-agent-loop)、[LangChain model-call limit](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)。

本案 background_error 會進 blocked，新訊息不會自動重啟它；`max_recoveries` 用於中斷工作恢復，不等同 blocked 錯誤自動重試。這是另一個應明確處理的恢復邊界，不能靠提高總測試預算掩蓋。不得因方便將 thread limit 改為每次 resume 重置，繞過整份背景工作的預算。

## 4. 官方方案：共通原則，不同匹配細節

### 4.1 Anthropic：精確替換也是真正官方方法

官方文字編輯工具要求 old_string 精確且唯一；零／多重匹配回具體錯誤，讓模型重查、更正，修改後驗證。沒有承諾替模型自動辨識所有空白錯誤。因此現行工具不是完全自創或「已淘汰方法」，但官方存在不等於此模型／此讀取格式組合就有足夠可靠性。[官方實作與錯誤規則](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool#implement-the-text-editor-tool)。

### 4.2 OpenAI：patch 與官方套用程式

官方提供 `apply_patch`：模型產生新增／刪除／修改的 diff，應用套用後回 completed／failed，模型依錯誤重讀或縮小變更；官方建議清楚檔案上下文與小範圍 patch。指南明確允許操作 in-memory workspace，不必把 Memory 改存真實檔案。[Apply patch 指南](https://developers.openai.com/api/docs/guides/tools-apply-patch)。

指南連到的 Python Agents SDK `apply_diff` 不是純 `str.replace`：`_find_context_core` 依序 exact、rstrip、strip 匹配行序列；換行格式會正規化再還原。這提供部分空白差異容忍，但不是語意相似搜尋，亦不能宣稱對所有重複段落安全或完全不會失敗。不要自己全域 trim 原文，Markdown 縮排可能有意義。[官方參考實作](https://github.com/openai/openai-agents-python/blob/main/src/agents/apply_diff.py#L329)（2026-09-07 實讀，main 會變動）。

本環境**未安裝 openai-agents**，目前也沒把原生 apply_patch 接進現有 LangChain loop。官方指南的模型清單不足以直接證明此環境 Luna 原生工具接線可用，仍需確認相容性。官方 parser 能處理字串不代表只加一個名字就完成工具結果、虛擬 staged files、驗證及發布接線。換 parser 亦不代表得改換整個 Memory 框架。

### 4.3 本案下一個決策（OPEN，不是已核准施工）

| 選項 | 優点 | 風險／代價 |
|---|---|---|
| A：保留精確編輯，讓修改用讀取更清楚區分原文與顯示資訊 | 改動較小，可保留官方 backend；避免把 gutter 當原文 | 仍受逐字匹配限制；自訂讀取介面需維持分頁與 context 上限，不能說是兩家一致格式 |
| B：評估 OpenAI 官方 patch／parser 接既有虛擬 staged files | 有公開原生工具與 parser，可容忍部分空白差異；非自創 fuzzy matcher | 需確認 Luna／現有 loop 相容，完整接工具結果；需檢查縮排語意、重複內容及錯誤恢復 |
| C：全面改用整檔覆寫 | 官方 write_file 已有，小短檔可省操作 | 長 Memory 易重輸出、漏舊細節，與前次品質問題重疊；不建議當預設修法 |

建議優先窄查 B 的接線可行性；若成本不合理，A 是較小替代。先用原失敗片段做離線比較，再用 Luna／medium 小量驗證，避免重跑整份訪談才發現工具仍不合適。同步依完成步數留合理餘裕；**不只提高上限、不默默加無限重試、不改理解／案例／引用的內容分層**。

## 5. Closure

- Finding：CT09-E01 exact-match／display-gutter mismatch 已重現；CT09-E02 背景 8 步餘裕與 blocked 恢復邊界需決策。
- 狀態：長訪談驗收 PAUSED；工具方案 OPEN。原始訪談／詳記／usage 已封存。
- 驗證：48 筆請求、9 輪、版本序列、3 次匹配錯誤與官方函式離線重播一致；oracle hash 相符；evidence 未含 API key 或 opaque encrypted reasoning。
- 未做：沒有產品碼／提示／額度／production 改動，沒有追加付費生成；沒有宣稱修復或驗收通過。
- 下一 gate：向 Owner 白話說明根因與選项，確認局部編輯機制修法；之後才接線、小測、恢復整份工作訪談验收。
