# CT39：抽取提示與分角色 effort 接線

> 執行：沿既有隔離 worktree、TDD 與獨立唯讀 review；不接 production。

**Goal:** 採用已有真測支持的 CT37 提示＋B1 high；A／B2 medium，避免把印象改寫成肯定。
**Architecture:** composition root 建立兩個官方 ChatOpenAI binding，共用原 HTTP／budget；將抽取模型注入既有背景 dispatcher。流程、Saver／Store、重試與排程不變。
**Tech Stack:** 現有 LangChain／LangGraph／OpenAI SDK，不升依賴。
**Spec:** [CT38結果與限制](../specs/2026-09-08-ct38-high-extraction-medium-consolidation-results.md) §1、3、5；Owner 2026-09-09「交給你決定」授權本局部選擇，非全角色 high。

## Preflight

- Topic：LLM-Q019；G3 已授權，G7 局部接入／整體 G8 OPEN。
- Blocking question：無新的產品選擇；需驗證設定抵達實際請求而非只改變物件外觀。
- 已讀：current register／decision-process、CT37／CT38來源與候選。原品質失敗保留。
- 不做：第三版 prompt、語意驗證器／judge、Memory 分層重寫、舊資料自動修復、C 零工具漏存、JD／production。

## 官方事實與本案選擇

2026-09-09 重讀：[OpenAI effort 指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#reasoning-effort)建議有 baseline、先檢查提示缺漏，再依測試決定提高 effort，非全面 max；[Anthropic hallucination 指引](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations#basic-hallucination-minimization-strategies)建議允許不確定及以來源為準；[LangChain ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai#reasoning-output)直接支援 `reasoning` 設定。**特定繁中提示與 B1 high／B2 medium 是 CT37／CT38 支持的本案選擇，不是官方保證最佳。** GPT-5.6 指引以 Sol 為主，Luna 效果依既有真測。

## Task 1：接入已驗候選，不改流程

檔案：`provider.py`（effort 參數）、`api.py`（雙 binding）、`service.py`／`scheduling.py`（傳遞抽取模型）、`extraction.py`（僅替換已封存的兩段提示）；均在 `experiments/analysis-agent/src/analysis_agent/`。測試於該 app 的 `tests/test_extraction_role.py`。

- [x] RED：先寫真 SDK／graph、僅假 HTTP 的測試：背景抽取 high，主顧問／B2 medium；同 output cap、all_turns、store=false；新提示等於封存候選。再驗原本未另注入模型的呼叫仍沿用原 model。
- [x] 實作 provider `reasoning_effort: str = 'medium'`，傳入 `reasoning={'effort': reasoning_effort, 'context': 'all_turns'}`。API 同一 transport 建立 high 抽取 binding 並管理生命週期；`enable_background(extraction_model=None)` 傳 dispatcher，未提供時 fallback 原 model。
- [x] 提示只採 CT38 實際 candidate：兩欄及標題保留誰說的、回答範圍及確定程度；保留部分回答與短反例。與封存 prompt 雜湊核對，不堆第三版。
- [x] GREEN：新接線測試＋既有 extraction／feedback／scheduling／service／API／provider recovery 回歸；擴至可用離線 suite，區分 PostgreSQL skip。
- [x] 記錄本輪實際驗證及限制、更新 README 與 current register，唯讀 review 完成；僅本輪檔案建立本地保存點，不 push／merge。

不為已取得的語意證據重跑整套付費對照：本輪先 0 付費，CT38 真測來源不冒充本輪結果。若接線呈現新的供應商契約問題才另開最小驗證；完整正常訪談仍是下一驗收段落。
