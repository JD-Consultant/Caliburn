# CT11：官方本機 Memory patch 試接

- Topic：LLM-Q019；2026-09-07 Owner「OK」核准 CT10 建議後進 isolated G5。
- 效力：僅 `experiments/analysis-agent`，不接 JD、production，不更換 provider 或 Memory 分層，不提高模型步數。不是全面長訪談驗收通過。
- 前置研究：[CT10 官方原碼／反例／版本](../specs/2026-09-07-memory-editor-framework-comparison.md)。不重開 matcher 研究。

## 已核准設計與邊界

模型讀取有界內容 → 直接提供包含真實上下文的 V4A diff → LangChain tool 呼叫 OpenAI Agents SDK 0.22.0 的本機 `apply_diff` → 成功才寫入既有私有 staged files → 既有格式／引用檢查與原子發布。B2 背景編輯與 C 即時修補共用套用介面；C 仍是整批發布。SDK 不執行模型請求、不使用 key，不代表 OpenRouter 原生 reasoning／compaction 全部已驗收。

依據：[OpenAI patch harness](https://developers.openai.com/api/docs/guides/tools-apply-patch#implementing-the-patch-harness)、[固定版 SDK](https://github.com/openai/openai-agents-python/blob/18de65134083ee8cbdb84ae30a34c1f30ef4cb86/src/agents/apply_diff.py)。官方負責 diff 套用；本案仍負責工具註冊、路徑授權、既有 payload 上限及發布邊界。這些接線不是宣稱 OpenAI 自動提供 Caliburn 的發布流程。

重要限制：SDK 的 whitespace fallback 是 first match，不保證唯一或語意正確。提示要求真實上下文定位、保留未改細節與引用；不另造模糊比對／私有 parser。只接受一個已存在 Memory 檔案的 diff body，path 獨立，拒絕多檔 envelope，避免 SDK 提早停止卻回報成功。背景初始化短檔仍可用既有 write_file。

## 工作與驗證

1. RED：新增真實 LangChain／StateBackend／publication 路徑測試：空白匹配、相似段落定位、錯誤回傳後修正、後一項失敗不部分發布。
2. GREEN：加入固定 SDK 依賴、共享本機 patch adapter；B2 提供 apply_memory_patch；C edits 只填 path＋diff。更新原 exact-edit 測試與提示，不藏相容轉換或全檔覆寫 fallback。
3. 回歸：離線全套測試；可用時 PostgreSQL 整合測試。確認未改來源、guide/read head、scope、stale、重試／取消恢復規則。舊待執行工具載荷不自動轉換；試接使用新 run，不清除既有資料。
4. 審核與紀錄：來源／實際指令／結果／限制留在獨立短結果，register 只路由。人工填入 patch 只能證明接線，模型效果須另做已核准額度的 Luna／medium 真測；未有新額度不呼叫模型。

## 本輪停止條件

若官方 matcher 無法在真實工具流程覆蓋 CT09 問題、需要新增匹配規則／重做 persistence，先提問，不自行擴張。離線通過也不宣稱「訪談已穩定」。

## 執行補記

Owner 已另外核准本輪 Luna／medium **最多 12 次模型請求、US$0.05**，含 B1/B2/C，不重跑長訪談；離線回歸通過才執行。採已有診斷 Ledger，每次 HTTPS 嘗試均計數、預留費用，結束關帳。為直接驗證編輯器，採明示合成 Memory 與原始問答；測試提示要求 C 修補及 B2 使用 patch，不能當作自然選工具或完整訪談品質證據。

執行收尾：上述 1–4 的接線、離線／PG 回歸與審查紀錄已完成，最終 562 passed／0 skipped；Luna 共 12 次，usage 估 US$0.00587412，帳本關閉。C 真測發布成功；B2 當時被過嚴的 terminal marker 檢查阻擋，修正後只完成原模型 patch 本機重播，**B2 真模型完整發布仍未驗收**。下一步只補這一項，須另有明確測試額度；不重跑長訪談。依據與失敗過程見 [CT11 結果](../specs/2026-09-07-official-memory-patch-trial-results.md)。
