# CT22 Memory提示契約局部實作

> **For agentic workers:** 使用executing-plans；這是一組緊密相依的提示變更，在既有隔離worktree執行並做獨立review，不拆多個施工者。

**Goal:** 將Owner已核准CT21 A1接入真正模型請求，保留舊保護，驗證原漏存反例。
**Architecture:** 只改主顧問提示、Memory system、C/B工具說明及共享讀取停止句；模型仍自主選工具，框架仍負責執行／錯誤／保存。
**Tech Stack:** 現有LangChain／LangGraph／DeepAgents與OpenAI SDK，不升降版本。
**Spec:** [CT21完整設計](../specs/2026-09-08-ct21-memory-prompt-contract-review.md)，精確文字以其candidate JSON為準；不從本計畫另創prompt。

## Preflight／不可變更項目

- Topic：Q019-MEM-CADENCE-01／CT15-R07；2026-09-08 Owner「OK」核准A1隔離施工。
- 基準：`066c94b4`；分支`codex/analysis-only-agent`。主register位於`S:/caliburn/docs/current-decisions.md`。
- 6工具schema、4讀工具、Skills、patch格式與细節／引用保護、讀取版本權威、背景可用性、B1/B2、provider、額度及ABC架構不變；不接JD／production。
- CT19是既有語意RED：回答5日但Memory仍10日；不付費重製baseline。
- 官方依據承接CT20/21；本輪再讀OpenAI [提示精簡](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#simplify-prompts-first)，保留完成條件與路由，不宣稱官方保證選工具。
- 小額真測授權：Owner接續「OK」已核准最多12次／US$0.05、Luna／medium；包含所有前景／背景／SDK重試，不開啟舊帳本。
- 實驗沿用CT16最終合成資料庫、8192輸出及12000壓縮門檻，不改產品設定。小額帳本沿用既有短context保守預留（至少64000或完整request bytes×2，取大者，以cache-write費率＋最大output預留）；request限128000 bytes，不假定cache折扣；實際usage獨立核算。這是測試護欄，不是精確token或帳單保證。官方費率於2026-09-08再核對[Pricing](https://developers.openai.com/api/docs/pricing)。

## Task 1：完整接線、局部回歸與收尾

**Files:** 修改`experiments/analysis-agent/src/analysis_agent/{api,live_memory,memory_tools,consolidation_request}.py`；新增`tests/test_memory_prompt_contract.py`；更新README當前提示說明、同topic結果與register，不改其他既有dirty內容。
**Consumes:** CT21 candidate JSON與現行MemorySession／SkillsMiddleware／build_conversation。
**Produces:** 同一工具介面下已核准的實際system＋tool payload。

- [x] 基線：live_memory／memory_patch／consolidation_request **52 passed，10.50s**；0外部API。
- [x] 新增真正SDK wire對照：用現有MockTransport固定回傳read_file再done，完整核對system與工具定義（只正規化本輪動態導覽／版本／地址）。錯誤接線／漏移或重複system應FAIL；不拿mock當自然工具選擇證據。
- [x] 先確認新wire測試在舊版FAIL，再依candidate逐字接入四檔；測試GREEN。另補真正AnalysisService＋Store＋background配置的首次無Memory情境，兩項對照通過。
- [x] 重跑局部安全網：最終251 passed，18.51s；C成功／失敗／stale／no_memory／有限重試、來源回查、Skills、B通知均保留。本輪不重跑整套PG／scheduler測試，不宣稱其驗收完成。
- [x] 獨立review：無阻止full-Store候選的finding；no-Store非保存入口的P2限制及實際可達路徑已記於CT22§4，不新增其功能。
- [x] 保存本地commit／tag；不merge/push。實際保存點只回填主register，避免計畫自我引用commit。
- [x] 新授權後真測已執行並按停止條件結束：第一個漏存更正FAIL（1次／US$0.00242175、0工具、Memory仍10日）；新更正與已保存重述未執行。完整payload／Memory／來源已封存，不改提示重跑、不重跑長訪談。
- [x] 離線結果回寫同topic，明分接線通過與語意未測；保留CT19失敗，不把未測當通過。
- [x] 真測結果回寫：候選FAIL、不promote、帳本closed；待Owner討論下一個不同依據的局部選項，不將此plan當重跑授權。

## 自審

四個prompt位置共同產生一份模型請求，需一組交付；不存在独立schema／資料遷移。JSON是人工審查fixture，不是產品讀取配置。讀取指引仍可供唯讀reader使用，不為其新增寫入工具。所有新判準、成本增加與結果處置依已核准CT21，無額外產品決策。
