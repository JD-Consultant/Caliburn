# CT11：官方 Memory patch 試接結果

- Topic：LLM-Q019，isolated G5／G7；2026-09-07。
- 結論：**官方本機 SDK 已接入 B2／C；C 真測完成，B2 真測尚未完成發布驗收。**不代表 CT09 長訪談驗收通過。
- 範圍：[核准短計畫](../plans/2026-09-07-official-memory-patch-trial.md)；底層與取捨沿用 [CT10 固定來源／反例](2026-09-07-memory-editor-framework-comparison.md)，不重選框架／Memory 分層。
- 詳細模型輸入、輸出、費用、合成資料、腳本與本機重播：[封存 evidence](evidence/2026-09-07-official-memory-patch-trial.json)。不把逐字記錄複製到 register。

## 1. 接了什麼，沒有接什麼

| 路徑 | 模型填寫 | 真正負責執行 |
|---|---|---|
| B2 背景局部修改 | `apply_memory_patch(file_path, diff)` | LangChain tool → 共用 adapter → OpenAI `apply_diff` → DeepAgents StateBackend 暫存 |
| C 即時修補 | `repair_memory(edits=[{path, diff}, ...])` | 既有 LangGraph repair workflow → 同一 adapter → 整批檢查／發布 |
| 短檔初始化／全文已知的替換 | 原 `write_file` | 原官方 StateBackend，不冒充 patch |

模型直接提供含上下文的 V4A diff，不再由我們把 old/new 片段猜成 patch。B2 不再暴露 exact `edit_file`；C 不再要求 old_text/new_text。讀取仍用官方有界 `read_file`／`grep`，不去剝除行號改寫原文、不新增無界 raw reader。

新增固定 `openai-agents==0.22.0` 與依賴；**只呼叫本機純函式，不使用 Agents Runner、OpenAI hosted tool、API client 或 key**。LangChain 的模型 binding、reasoning／compaction 與 API 設定未改。因此編輯器本身不綁 OpenAI key；本次真測使用既有 OpenAI 直連，不等於證明 OpenRouter 的整套原生延續功能可用。

官方明說 app 需實作 patch harness，並提供成功／失敗供模型續作：[OpenAI apply patch](https://developers.openai.com/api/docs/guides/tools-apply-patch#implementing-the-patch-harness)。本機函式與 matcher 依 [SDK 固定版原碼](https://github.com/openai/openai-agents-python/blob/18de65134083ee8cbdb84ae30a34c1f30ef4cb86/src/agents/apply_diff.py)。本案工具名稱、兩檔範圍、既有 12000 字元／C 1–8 個 patch 上限及既有發布流程是**應用接線與已核准邊界**，不是宣稱各家都有這些數字或 schema。

## 2. 錯誤與安全邊界

- `apply_diff` 完整成功才寫 staged file；解析錯誤以 LangChain `ToolException`／C 原有 `invalid_edit` 回傳檔案與錯誤，再讀取修正。storage／infrastructure exception 不在共用 adapter 中假裝成模型格式錯誤。
- scope、Memory 檔案白名單、引用／格式檢查、C stale refresh、取消與 receipt 對帳、CAS 發布不變。C 中間一個 patch 失敗不部分發布。
- SDK first-match 與 whitespace fallback **不是唯一匹配或語意正確保證**。使用真實 context 區分重複段落；未新增自製 fuzzy matching／私有 parser。已核准的 CT10 反例仍成立。
- 防止 SDK 在多檔 delimiter 提前結束而忽略其後內容：接線只接單一檔案 diff body，拒絕整份多檔 envelope 及結尾之後的其他命令。**合法尾端支援 `*** End Patch`、`*** End of File`，以及 End of File 接 End Patch**；檢查時忽略最後換行，不修改交給 SDK 的 diff。
- 不清除舊資料，不提供 old/new 自動翻譯。這次是隔離工具契約切換；舊版尚在執行的載荷不作自動相容承諾，使用新 run 驗證，不能把舊 pending snapshot 當本輪成功恢復證據。

## 3. 真實測試：失敗也保留

Owner 額度為總共 12 次／US$0.05；實際 **12 次 Luna／medium，usage 估 US$0.00587412**，已關帳。使用既有 Ledger，每次 HTTPS 嘗試計數／保守預留，沒有開更多額度。

1. **第一次 3 次、US$0.00102683：測試器失敗。**臨時 SQLite 沒用跨工具執行緒共用連線，發生 OperationalError／thread 限制。改用既有離線 fixture 已採用的 StaticPool＋`check_same_thread=False`，沒修改產品。不是 patch 匹配失敗，也不當成功。
2. **第二次只用剩餘 9 次、US$0.00484729。**C 4 次（grep→read→repair→final）完成 revision 2，財務主管改為財務處長；其他退款分工、一般退換貨、月報、FAQ、A/B 案例與舊引用保留。
3. B1 1 次，抽取新更正與「每月第一個工作日」；B2 4 次（read knowledge→read guide→read 新詳記→patch）。B2 產生的 diff 含正確局部修改與詳記引用，但以 `*** End Patch` 結尾。**當時我們的 wrapper 比 SDK 更嚴格，拒絕了合法結尾**；下一模型步被總額度阻止，未完成發布。GUIDE 已在 context 卻再讀一遍也有小量冗餘，本輪不另加機制處理。
4. 依 SDK `_parse_update_diff`／`END_PATCH` 真實契約修正 wrapper，不是放寬匹配或忽略錯誤：允許官方合法尾端組合，仍拒絕後接指令。先增加失敗測試，再修到通過。將上述**模型實際 diff 原封不動**透過產品 adapter＋官方 StateBackend 本機重播成功：月報新增、C 更正保留，案例尾段與未受影響職責完全一致。

這是合成 Memory seed＋針對性測試提示，C 明示要修補、B2 明示要用 patch；**不能據此聲稱自然訪談選工具、一般錯誤率或成本已改善**。本機重播未呼叫模型、未驗證本次 B2 的 final／publication，不把它冒充線上完成。

## 4. 回歸與 review

- RED：最初兩項新 B2／C 接線測試皆失敗；加 SDK 後兩項通過。真測後另新增 terminal End Patch 測試，舊 wrapper 失敗、修正後通過。
- 第一輪大量 setup errors 是 Windows 暫存目錄權限；另一次新 basetemp 缺父目錄；改用已存在隔離父目錄及適當執行權限，未修改產品規則。PG 首次讀錯測試帳號遭拒，改採容器實際帳號預檢連線成功，未重設密碼／Docker。
- 接線初版 **558 passed／0 skipped（含 PG，146.75s）**。最終版 **562 passed／0 skipped（含 PG，119.40s）**，只有既有 Starlette deprecation warning；`compileall -q src tests`、`uv lock --check --offline`（97 packages）亦通過。命令在 `experiments/analysis-agent` 執行：`python -m pytest -q --tb=short --basetemp <隔離測試目錄>`；PG 指向已核對 purpose label 的本機專用 `q019_agent_test`，帳密僅由既有容器設定置入環境、不輸出。
- 獨立 reviewer 的 CT11-R01：PG guide patch fixture 與真實整行不符，已修正實際測試載荷，保留恢復斷言。CT11-R02：delimiter 反例原本就無法匹配原文，已改成確實可匹配的首個 hunk，並斷言拒絕原因與未發布，避免假綠燈。
- 最後三種尾端組合的增量審查無新增 Critical／Important／Minor finding。EOF＋End Patch 組合也先重現失敗再修正；反例仍確認尾隨操作不得被靜默忽略。
- 封存 evidence 的 `product_sha256` 是真實 diff 本機重播當時的版本，不是最後擴充 EOF＋End Patch 尾端檢查後的檔案雜湊；封存資料不覆寫。最終版由上述 562 項回歸（含同一真實 diff 重播 fixture）驗證。

## 5. 下一個唯一 gate

**只補 B2 真模型的 patch→回饋→完成→發布收尾驗證**，需新明確測試額度；不是再跑整套長訪談。完成後才能回到 CT09 長訪談。此次工具接線不升格為 production authority、不 merge/push、不宣稱整份工作理解已達標。
