# CT51：8,192／16,384 生成上限局部對照

> For agentic workers: use executing-plans and verification-before-completion. This is experiment configuration, not a product implementation or new architecture.

**Goal:** 回答 Owner「16,384 試試看？」；比較已驗收 8,192 與 16,384，不能把容量提高等同更聰明。
**Architecture:** 沿 CT50 真 FastAPI／LangGraph／SDK／PG 入口；由 CT49 closed DB 各建一個新複本。相同來源、high、提示、工具、16模型／15工具、native compaction12,000，只改 `Q019_MAX_OUTPUT_TOKENS`。API/default/source不改。
**Tech stack:** 現有隔離 analysis-agent 及既有 CT15／CT37 觀測器；觀測器只擴充核准的測試 output bound，不更動產品保護。
**Spec:** [CT50](../specs/2026-09-09-ct50-tested-profile-results.md)、[CT49](../specs/2026-09-09-ct49-fixed-long-interview-results.md)。

## Preflight／單一問題

- Topic LLM-Q019／CT51，G5。Owner 2026-09-09同意試16,384，未要求直接採用。
- Blocking question：同模型high下，增加單次生成餘裕是否改善品質／完成度，代價是否值得？
- 不碰production/JD、Memory架構、提示、既有資料、key、retry、compaction政策；舊CT49/50帳本不重開。
- 原始／詳記／工作理解的資料意義及引用規則不變；新案例與共通工作不得混同，未提舊事不代表刪除。

## 官方事實／本案選擇

- [OpenAI reasoning: controlling costs / allocating space](https://developers.openai.com/api/docs/guides/reasoning#allocating-space-for-reasoning)：生成上限含reasoning和可見輸出；耗盡會incomplete／max_output_tokens，可在沒有可見答案前發生。官方建議開始探索時預留25K，再依實測調整；不是每個部署必須25K。8K／16K是本案局部對照，不是官方品質保證。
- [Luna model](https://developers.openai.com/api/docs/models/gpt-5.6-luna)：支持high；不換型號。
- [定價](https://developers.openai.com/api/docs/pricing)，本輪核對 standard／短context input .20、cached .02、cache-write .25、output1.20 USD/百萬tokens。按usage估算，不冒稱帳單。

## 測法與檔案

- Create `.test-tmp/ct51_service.py`, `run_ct51.ps1`, `ct51/continuation.txt`, `ct51/recall.txt`：重用真服務driver、ledger，兩組只改生成上限。每組一次有足量新資訊的自然續談，等待實際背景idle/blocked；不得把driver的recorded当背景完成。若未自然通知，不偽造通知；結果標未覆蓋B。
- Create `docs/specs/2026-09-09-ct51-output-budget-results.md` 和分離JSON證據；register只放結果與路由，避免堆長文。
- 同一合成前端工程師新增「松嶼展示型網站」快取案例（非付款／報名），並補充雙週報表遇假日提前一工作日、日常分流不變。詳記保留實際判斷、排除錯誤、工具、责任、驗收及適用限制；理解歸納共通前端工作，不生成JD。
- 回查用同一query、現有只讀Memory工具、新預設16/15、空近期context。它的instructions與主顧問不同，分開報告；不能以reader代表真訪談。
- 評閱：松嶼未有交易功能；正確快取證據及修復；雲岸／青禾不混案；雙週及假日條件完整且所有專案／每日分流保留；無額外核准權／固定SLA；引用原文吻合。對比全量before/after，查未變有效內容和引用。

## 工作／退出

- [x] 固定source hash/HEAD、查旧帳本closed，兩DB開場相等；不外傳key／opaque reasoning。
- [x] 離線驗證ledger接受8K/16K且拒绝錯誤endpoint/model/effort/bound、closed/請求數/費用超限；真接線既有測試通過。只擴測試護欄，不加產品機制。
- [x] 48次合計／US$0.30預留，包含A/B1/B2/reader及SDK重試。按組順序執行，不跨進程同時寫帳本。到限停止、不自動擴充、不將失敗重寫成通過。實際35次／US$0.05009506。
- [x] 比較completed/incomplete/error、實際reasoning/output tokens、工具錯誤/呼叫、延遲、usage費用、語意；來源引用逐段對照canonical、reader不得改Memory、原CT49DB/帳本不變。
- [x] 記錄所有成功／失敗／未覆蓋範圍，決定保留8K或採16K作可逆已測配置。單一pair不是統計品質證明；若無截斷或明確品質差異，不聲稱16K更聰明。此輪無production改動，無merge/push。

結果：[CT51結果／證據／下一gate](../specs/2026-09-09-ct51-output-budget-results.md)。兩組均完成；8K維持，16K可用但未採用。Docker與test helper初始化失敗保留，無產品修改。
