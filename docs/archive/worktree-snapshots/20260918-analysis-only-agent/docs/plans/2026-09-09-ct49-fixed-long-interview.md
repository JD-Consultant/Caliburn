# CT49：新版固定長訪談驗收

> **For agentic workers:** 使用 superpowers:executing-plans 逐段執行及 verification-before-completion；沿 Owner 委任，不再為局部驗收重問。

**Goal:** 從空白完成整份接案前端職位的訪談、三層記憶、更正、補充撤銷與原話回查；不做 JD。
**Architecture:** 既有真 FastAPI、PG Saver/Store、A/B1/B2及自然通知，獨立新DB，固定 `309eaf21` src雜湊。沿CT45已核對driver/ledger，不mock模型／工具／正常背景。
**Tech Stack:** 原隔離 analysis-agent 的 LangChain/LangGraph/DeepAgents、OpenAI Responses，Luna。
**Spec:** [CT46–48結果與來源](../specs/2026-09-09-ct46-48-edit-routing-and-budget-results.md)、[完整職位驗收範圍](2026-09-09-ct45-fixed-long-interview.md)及Owner active goal。

## Preflight／邊界

- Topic LLM-Q019，G8 OPEN。唯一問題：固定新版本是否完成整份工作訪談且資料與引用正確；無未決產品選擇。
- A/B1/B2 high、8192輸出、all_turns與native compaction12000；A12模型/11工具、B2 16/15。不是medium4096預設驗收。
- 新180次／US$0.75實驗護欄，全部SDK嘗試／背景／回查計費；只送合成問答及其生成Memory到既有官方Responses端點，不送真員工資料、秘密或研究檔案。原CT45–48closed不重開。
- 官方[GPT-5.6指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)本輪重新開啟，已重導model-specific guidance。沿明確結果、約束、代表性測試，固定版本避免混用；[LangChain限制](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)不規定本案精確數字。
- 無新prompt/產品變更；若發現重要失敗保留原結果，局部診斷另記。不得將框架語法PASS或模型說完成當語意PASS。

## 任務與可觀察驗收

- [x] 建立 `.test-tmp/ct49_service.py`／`run_ct49.ps1`、新帳本／DB；src hash及空白問答確認，初始化不得呼叫模型。
- [x] 真服務逐輪問答：按模型實際問題回答，不注入理想分析；涵蓋需求估算、兩個相似網站、開發/串接/測試、發布、維護、週報、交接、低頻升級、責任界線。中途含糊→查證更正，後段新補充與撤銷、無新增重述。
- [x] 逐段審每次詳記/候選/正文/導覽及引用；仍有效內容不能因新資料沒重述而丟失。CT48引用label與案例段落Minor繼續檢查。
- [x] 真服務重啟後完整問答相等；全部詳記與原文source/context分頁相等。另用空近期context的既有只讀reader驗案例差異與原句，不把19/18診斷讀者預算當A產品12/11通過。
- [x] 封存逐輪問答、三層完整產物、已消毒provider/tool trace、usage費用與原失敗；短報告及獨立review完成。結果見[CT49](../specs/2026-09-09-ct49-fixed-long-interview-results.md)。本地保存點與CT50收尾，不push/merge。

Pass：有代表性全職位涵蓋、修正正確、低頻與仍有效細節可查回、無重要混案/錯引/漏項。沒有宣稱數學100%完美或跨職位成功率；未通過就G8 OPEN，不改標準。
