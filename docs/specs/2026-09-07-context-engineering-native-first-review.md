# Q019／CT-02：原生優先的 Context 管理接續審閱

> 2026-09-07 · **Owner 已核准 CT-02 接法與隔離窄修（G7）；產品正常訪談尚待驗收。**
> 入口：[current decisions](../current-decisions.md)。本頁只持有 Context 接法取捨，不重寫 Memory ABC、訪談分析方法或 Provider 真測紀錄。

**實作接續：**已完成核准的native/exact窄修，547項離線／PG通過，真服務入口三輪樣本成功。12次小額額度已用完；獨立Memory回查及真壓縮仍未驗成，不能把本頁設計核准當作全部效果通過。只看[最新短結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-native-context-normal-interview-results.md)取得用量、證據與剩餘問題；以下待核准文字是原研究沿革。

## 1. 本輪範圍與重開依據

**接續核准：**Owner「同意，然後優化到可以正常訪談」，並更正是「正常訪談」而非擴大長訪談壓測。以下原始研究的「待核准」為沿革；推薦 CT-02 已核准，只改隔離版。真測另核准最多12次模型請求、US$0.10費用預留，達界線停止，不沿用先前已結束的額度。施工／實測結果由[窄修計畫](../../.worktrees/analysis-only-agent/docs/plans/2026-09-07-native-context-normal-interview.md)及其結果路由持有。

**底層補核：**Deep Agents 0.7.13 `FilesystemMiddleware._create_read_file_tool` 本身會呼叫 `_truncate_paginated_read`，使用設定的4000 token近似值作16000字元限制，按完整來源行重算續讀offset；即使未註冊middleware hooks也有這個tool內限制。grep亦有工具層格式化截量。保留官方工具，不因F4的待核項誤加第二套裁切。這仍不是完整request的精確token保證；單一極長來源行可能只能回大小警告，不能宣稱任意檔案已可完整續讀。

- **Topic：**LLM-Q019／CT-02；接續 CT-01 與 MP-01。
- **目的：**管理長訪談的有效 Context、推理延續、成本及故障，不讓輔助計數接口成為每次訪談的必要依賴。
- **有效約束：**隔離只分析版；保留原生 reasoning、canonical 訪談原文、ABC Memory 與既有工具／呼叫限制。不接 JD／production，不重新比較框架。
- **重開原因：**實測 `/responses/input_tokens` 404 阻塞產品；Owner 詢問為何必須精確計數，並同意研究 OpenAI／Anthropic／框架的 Context Engineering。這是重審 CT-01 的接法，不是否定 Context 預算。
- **唯一決策題：**是否將「每次生成前遠端精確計數」改為選用輔助，以原生壓縮、可控資料量、實際 usage 與安全失敗管理 Context？具體切換仍待核准。
- **已讀路由：**[Provider 契約與真測入口](2026-09-07-analysis-provider-capability-review.md)、[CT-01 實作結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-context-budget-and-analysis-skills-results.md)、[既有原文／預算研究](2026-09-06-context-window-retention-and-budget-wiring-review.md)、[新版 Runtime 設計](2026-09-06-analysis-only-agent-runtime-design.md)。不讀被 Owner 排除的 08-12 產品長稿。

## 2. 官方事實，不把 API 名稱當效果保證

| 來源（本輪查閱） | 官方提供／要求 | 不可推導 |
|---|---|---|
| [OpenAI server-side compaction](https://developers.openai.com/api/docs/guides/compaction#server-side-compaction) | `context_management`／`compact_threshold` 按 rendered tokens 觸發；回傳 opaque compaction item，延續狀態與推理；可配 `store:false` | 不必另外呼叫 standalone compact；也沒有保證任意超大輸入都能自動救回 |
| [OpenAI standalone compact](https://developers.openai.com/api/docs/guides/compaction#standalone-compact-endpoint) | 呼叫 `/responses/compact` 的輸入本來就須在 context window 內；返回的完整 window 原樣作為後續輸入 | 不能只挑其中 summary；不能把「已超上限再 compact」當必定成功的通用補救 |
| [OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls) | 依適用模型保留／重送相容原生 items，核對 effective context | 文字摘要不是原生推理；也不保證永不重分析／永不忘記；不能任意跨模型搬 opaque items |
| [Anthropic compaction](https://platform.claude.com/docs/en/build-with-claude/compaction)、[context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing#client-side-compaction-sdk) | 現行文件優先建議 server-side compaction；SDK `compaction_control` 已有棄用／移除說明 | 不能複製舊 SDK 摘要 recipe 當最新預設；Claude 的內容格式、thinking 規則及門檻不等於 OpenAI |
| [OpenAI count](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count)、[Anthropic token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting) | 兩家有計數能力；Anthropic 明示是估計，可能與實際生成用量略異 | **沒有從上述契約得到「所有應用每次生成前必須 count」的要求**；計數也不能預知尚未產生的回答／推理／新 compaction |
| [LangChain Context Engineering](https://docs.langchain.com/oss/python/langchain/context-engineering) | `wrap_model_call`／`request.override` 可暫時組裝本次輸入；另有持久 state 更新 | request view 不等於原文資料庫；SummarizationMiddleware 替換目前 state 的舊訊息，不表示所有歷史 checkpoint 必然刪除，也不自動等於完整原文保存策略 |
| [ChatOpenAI context management](https://docs.langchain.com/oss/python/integrations/chat/openai#context-management) | 公開 binding 承接原生 `context_management` 及 compaction content blocks | 不必換整個框架；gateway 接受同名參數仍須另驗實際能力 |

**共通目的／非共同配方：**有界上下文、必要內容按需取得、長對話延續、可觀察用量。OpenAI／Anthropic 提供原生壓縮能力，但本頁不宣稱兩家內部採同一算法、數字或 LangChain。具體組合是依官方能力提出的本案建議，不冒稱業界唯一最佳解。

## 3. 對照實作後的四個重點

基準：隔離 worktree `analysis-only-agent`，HEAD `82ac2266058cfd2ff708ac83e937b24179f7b1cb`；本輪沒有修改 src/tests。已核對 lock：LangChain 1.4.0、langchain-core 1.6.2、langchain-openai 1.6.0、LangGraph 1.2.11、Deep Agents 0.7.13、OpenAI SDK 3.8.0。這是**實際安裝版本**，不是聲稱全部都是今日最新版本。

1. **CT-02-F1／阻塞，已確認。**[budget.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/budget.py) 對最終 SDK body 做遠端 count；[api.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/api.py) 將它設為 A／B1／B2 每次生成的必要 hook。因此多一次 HTTP 往返及失敗點；是本案保守取捨，不是 LangChain 或 OpenAI 強制。不得把取消 count 就說成 gateway 原生壓縮已修復。
2. **CT-02-F2／替代計數器限制，已確認。**本地 `langchain_openai/chat_models/base.py:2289–2388` 的 `get_num_tokens_from_messages` 明示忽略 tool schemas；`langchain_core/messages/utils.py:2244–2420` 的 `count_tokens_approximately(..., tools=...)` 可算工具，但仍是字元近似，部分未知 content 用 `repr` 長度。encrypted item 字串長度不等於服務端 rendered tokens；英文四字元近似也不能當中文上界。usage scaling 有 1–1.25 限制，不使它變成精確計數。舊研究中「公開計數方法有 tools 參數」不足以证明完整承接，須區分這兩個函式。
3. **CT-02-F3／原文與模型視圖，已有正確分離，保留。**[context.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/context.py)／[runtime.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/runtime.py) 暫時選取 inline compaction 起點之後的內容，不寫回替換 canonical messages。不能把這個規則套到 standalone compact 的完整返回值。B1 經 [sources.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/sources.py)／[extraction.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/extraction.py) 選完整結束回合；預設來源窗口 6000 字元、脈絡 1500，超大完整回合明確失敗，不截掉中間。字元界線是 I/O 規模控制，不是 token 精確保證。
4. **CT-02-F4／整體預算尚不能宣稱完成。**A 有導覽與按需讀取；B1 有來源分窗；但「回覆有分頁」不等於整個 request 已有界。仍須把固定規則、實際 tool schemas、已載入 Skill、導覽、工具回覆、近期訊息及原生 items 一起檢查。既有 `memory_tools.py` 只取 FilesystemMiddleware 的 tools，不能把 middleware 的 eviction 設定當作 hooks 已接線。下一窄修須核對實際輸出大小，不盲加另一套全域刪訊息機制。

## 4. 建議接法與框架責任（待核准）

**推薦：原生優先＋輸入規模控制＋實際用量；精確 count 不再是每次生成的必要前置。**不是移除預算，也不是換成本地近似後宣稱同等精確。

| 層 | 如何接 | 邊界 |
|---|---|---|
| A 訪談 Context | LangChain middleware 組固定規則、小型 Memory 導覽、原生延續內容／近期訊息及本輪輸入；已讀且相關的資料可沿用 | 不重複加入本輪訊息；不強迫每一步重跑 ls→grep→read；不把所有 Memory／Skill 常駐 |
| 原生推理／長對話 | 保留 ChatOpenAI Responses binding、原生 items、inline compaction；完整保存輸出，再產生下一次 request view | 模型及 endpoint 要實際支援；保留 tool call/result 配對。不加每回合第二次文字摘要來替代原生推理 |
| 詳細資料與 Skills | 沿用 Store/backend 讀取及 Deep Agents SkillsMiddleware；用公開 read 工具的分頁／長度參數提供後續讀取位置 | 不靜默砍來源。若實際工具限制不足，先查公開接點，再做局部限制；不預設需要另一個 Agent |
| B1／B2 | B1 用選定的完整原文窗口＋必要前文＋小型 output schema；B2 用候選資料、目前 Memory 與按需詳記／原文 | 不拿 A 的 compaction 替代 B1 原文；B1 不經主顧問 middleware，不能只驗 A 就宣稱三條路徑均涵蓋 |
| 用量／失敗 | 利用 AIMessage usage metadata／框架 callbacks，保留既有輸出、呼叫次數、timeout、錯誤及恢復邊界 | 精確 counter 改為明確選用的診斷／預檢；不默默把失敗 count 改報成功；原生能力缺失仍是缺口 |

**門檻與超量：**按目標模型已確認的 window 設較早 compaction 門檻，留給新輸入、工具結果、輸出／推理的空間；沒有兩家共用的固定百分比可直接照抄。對外接收的單次超大輸入也須有明確處理界線。近似計數可協助觀測，但不能將 opaque 字元或上一輪 usage 當本輪精確總數。真正 overflow 時保留原文、回報可恢復錯誤並結束該次分析，不在相同超大 payload 上無限重試、截掉當前員工內容或假裝成功。無 count 的方案接受「不能對每個 request 作精確事前不超窗保證」的取捨，靠上述限制降低風險，並以實際 endpoint 驗收；若這個取捨不可接受，保留原 CT-01。

**快取與費用：**固定規則／工具穩定排列，動態資料放後面，有利前綴重用；不為快取故意送過時 Memory。快取不增加 context window，也不是長期 Memory。[OpenAI 現行 prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) 依模型有不同快取模式與 write/read 計費，GPT-5.6+ 的寫入有成本，因此本輪不直接套舊 `24h` recipe、不保證每次省錢、不擅加新 cache 參數。實際用量優先沿用 [LangChain usage metadata／callback](https://docs.langchain.com/oss/python/langchain/models#token-usage)；若日後接 Claude，要核對 compaction 的 `usage.iterations`，不能只記頂層欄位漏掉整理費用。沒有在本輪新增 Claude 實作或計费系統。

**提示精簡依據：**Anthropic [2026-07-24 Context Engineering 說明](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models)支持清楚工具介面、按需 Skills、避免相互牴觸／過密規則；其特定 Claude Code prompt 精簡結果不是 Luna 也可刪同樣比例的證據。本輪只採這個審閱方向，不整份重写分析／Memory prompt。

### 選項比較

- **維持 CT-01：**保留每次遠端 count 和精確輸入檢查；代價是額外網路往返、子接口依賴，且仍不能保證語意完整或預知生成成本。
- **推薦 CT-02：**以上原生優先接法；減少計數阻塞與往返，保留推理／原文，接受非每次精確事前 admission 的取捨。**待 Owner 核准，未替換現行實作。**
- **改用通用文字 SummarizationMiddleware：**可另研究跨 provider 接法，但不等於原生推理延續，且需重核原文保存；本輪不推薦、不默默 fallback。

## 5. Closure 與下一個 gate

- **結論：**官方資料足以選擇接法，不需繼續廣搜相同概念。沒有證據支持「每次精確 count 是必須的共識」。也沒有證據支持僅靠 framework 近似值即可精確保護所有原生內容。
- **狀態：**CT-02 是提議；CT-01 程式尚未變更，MP-01／正常訪談仍 OPEN。本輪付費呼叫 0；沒有重新跑程式測試，既有測試數字留在各結果頁，不冒用為本輪驗證。
- **下一步：**Owner 核准接法後，寫／執行隔離窄修：調整 mandatory counter 接線、核對 A/B1/B2 完整 request、限制實際工具回覆，維持原生 replay／原文可回查及框架錯誤處理。新付費測試需單獨明訂上限；先前 12 次額度已結束。
- **最低驗證：**小輸入不多一次計數；中文／tools／Skill 不漏檢；原生 opaque 完整 replay；超長輸入／工具回覆明確處理且不刪來源；實際 compaction 後仍可回查原文；B1 不讀有損摘要；A/B1/B2 用量有紀錄。離線先做，真實 endpoint 才能判斷原生能力與正常訪談，不宣稱本輪已跑通。
- **重開條件：**實測原生壓縮不適用、受控輸入仍頻繁 overflow、缺必要 token／usage 契約，或 Owner 不接受上述事前保證取捨。沒有這些反證不再重討論 Memory ABC。
