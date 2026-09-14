# Q019-APP-01：失敗處理的跨廠商核對

> 2026-09-06 · **研究完成，Owner 已同意接線修訂原則；准隔離實作及零付費驗證，不代表新接線已通過測試。**
> 起因：Owner 要求先研究共同做法，避免重演先前高失敗率。只核對 Q019 應用接線，不重開 Memory 五產物、模型選擇或 JD 功能。
> 決策入口：[current-decisions](../current-decisions.md)；設計 owner：[應用接線](2026-09-06-analysis-only-agent-application-wiring-design.md)；執行 gate：[計畫草案](../plans/2026-09-06-analysis-only-agent-application-wiring.md)。

## 1. 結論與證據界線

共同方向是 **先減少工具／契約錯誤，再依錯誤種類恢復；有界停止但不偽裝成功**。不是每種錯誤都重送，也不是員工一律只能手動恢復一次。

本稿的「共同」只指以下已列來源中重複出現的原則，不代表所有廠商、所有產品或最佳效果已被證明。廠商 SDK 公開行為也不等於 Codex／Claude 產品的全部內部流程。

- **撤回未核准提案：**「人工恢復最多一次」沒有找到跨廠商依據，不作第一版既定限制。
- **保留但需校準：**6 model steps／8 tool calls 是既有工程初值，不是已證明足夠的產品預算；先檢查正常深入讀取、一次修正與最後回答是否放得下。
- **不改目標：**reasoning 延續、持久 Memory、原文可回查仍保留；不因錯誤而刪歷史、停用 strict 或悄悄換模型。
- **框架直接承接機制：**SDK transport retry、LangChain tool error／limit、LangGraph checkpoint／fault tolerance。應用只設定適用錯誤、預算、已保存結果的處理與對外狀態，不另寫重試引擎。

## 2. 先前為何失敗：不是都能靠重試修好

| 本地紀錄中實際看到的事 | 能下的結論 | 這次避免方式 |
|---|---|---|
| provider 拒絕不符合 strict 要求的 schema | 是送出契約問題，不是暫時網路問題 | 送出前檢查实际 schema；原參數反覆重送無用 |
| 模型不知道候選資源可用欄位／路徑；提高工具上限後仍失敗 | 工具能力說明與實際資料契約沒有接好 | 系統已知資訊由系統提供；必要格式放在對應工具／可讀資源，不要叫模型猜 |
| 第 8 步完成檢查，卻沒有第 9 步產生回答的額度 | 上限本身能製造失敗 | 正常路徑必須包含最後回答，不只計工具操作 |
| 下一次放寬步數後遇到 reasoning＋output 額度不足 | 步數、單次輸出與總費用是不同預算 | 不把提高其中一種預算當成其他問題也已解決 |
| verifier 只記 exception class，沒有精確錯誤 | 無法確認最後是哪條驗證失敗 | 記錯誤種類、階段、必要的安全診斷，不只記「分析失敗」 |
| compaction 後重讀 Skill 被舊一次性限制拒絕 | 有限制與按需重讀需求不相容；不能直接證明它就是最後 verifier 的根因 | 不把成功讀過一次解讀成永遠不需重讀 |

以上是歷史診斷，不恢復舊 JD／Evidence／defer 政策，也不推論新 Q019 已有相同錯誤。原始證據：[08-21 live smoke §§1–3](2026-08-21-virtual-jd-workspace-live-smoke.md)、[08-23 strict/tools/context audit](2026-08-23-luna-structured-tools-and-context-official-audit.md)。工具介面原則另與 [OpenAI function best practices](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions) 核對：清楚描述、減少模型需猜的參數、系統已知的值不交模型填。

新 Q019 也已有一個相關經驗：ToolNode 可把參數驗證失敗轉為 error ToolMessage，而非向外丟 exception。只在最外層 catch 會漏算；先前已修復，不能另寫一套重複處理。[第七切片結果](2026-09-06-analysis-only-agent-live-memory-results.md)

## 3. 各家實際公開做法與差異

| 層次 | OpenAI | Anthropic | 框架與共同結論 |
|---|---|---|---|
| 暫時服務／網路錯誤 | 官方 SDK 有有界 retry；指引要求 backoff、Retry-After、總時間界線，避免巢狀重試 | 官方 SDK 對適用錯誤自動 retry；錯誤碼區分配置、額度與暫時故障 | 自動處理可恢復的傳輸失敗；不要全部丟给員工手動按重試。[O1][A1] |
| 模型工具參數不對 | 先改善工具定義及 schema；工具結果再進後續模型呼叫 | 回對應 tool_result／is_error，說明錯在哪及可做什麼 | 交回模型改參數，與「相同參數自動重送」不同。[O2][A2][L1] |
| 額度停止 | Agents SDK 有 MaxTurnsExceeded／受控 error handler | Agent SDK 有 result subtype 區分成功、turn／budget limit | 需要明確未完成結果；沒有共同的 6 步、8 工具、一次人工恢復標準。[O3][A3] |
| 狀態延續 | Session 與 RunState 有各自用途，跨重啟 durable orchestration 有另列整合 | session 可 resume，但不能由名稱推成每種工具都 exactly-once | LangGraph 恢復 checkpoint；不是回到任意舊 checkpoint replay，也不保證外部寫入只發生一次。[O3][L2] |

**不能混淆細節：**Anthropic Agent SDK 文件的 `max_turns` 計 tool-use 往返，OpenAI Agents SDK 的 turn 是模型呼叫；LangChain model/tool limit 又各自計數。直接把一家範例數字搬到另一家沒有意義。[A3][O3][L1]

### 3.1 本輪核對的官方來源

每個代號只對應公開說明；日期均為本輪查閱日 2026-09-06。

- **[O1] [OpenAI rate limits：retrying with exponential backoff](https://developers.openai.com/api/docs/guides/rate-limits#retrying-with-exponential-backoff)**：重試時間／次數、Retry-After、SDK 與外層重試不能無意疊乘。不是每個 429 都能立即重試，額度／帳務問題需另外處理。
- **[O2] [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)**：工具說明與 schema 的錯誤預防；不要求模型填已知資料。
- **[O3] [OpenAI Agents SDK：errors and recovery](https://openai.github.io/openai-agents-python/running_agents/#errors-and-recovery)**：受控 fallback 不等於重新呼叫模型；可選是否把代填結果寫入歷史。SDK 另列 durable execution 整合，不能把 Session 自動視作完整耐久工作引擎。
- **[A1] [Claude API errors](https://platform.claude.com/docs/en/api/errors)**：typed errors、request ID、SDK retry，以及 streaming 在 HTTP 200 後仍可失敗。
- **[A2] [Claude handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error)**：錯誤工具結果需配對、可操作說明及 strict。頁面敘述的模型修正 2–3 次不拿來当本產品必然成功或硬次數保證。
- **[A3] [Claude Agent SDK loop／turns and budget](https://code.claude.com/docs/en/agent-sdk/agent-loop#turns-and-budget)**：限制、技術 result、失敗與成功分開；官方例子可在提高限制後延續，不是固定一次手動恢復。
- **[L1] [LangChain prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)**：ToolErrorMiddleware／ToolRetryMiddleware／ModelRetryMiddleware／call limits。可用不代表全都要開；ToolError 只轉錯誤回饋，本身不重送。
- **[L2] [LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)**：失敗恢復、pending writes、replay 與 durability。恢復／replay 範圍必須分清。
- **[L3] [LangGraph fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)**：retry_on、timeout、error_handler、NodeError。官方已有錯誤收尾接口，不用自製替代；同步 worker 的實際停止仍須核實。
- **[L4] [LangGraph thinking in LangGraph：errors](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)**：暫時失敗、模型可修正、需要人提供資訊、未知程式問題分開。這是框架的分類設計，不強制把一般訪談問題變 interrupt。

## 4. 更底層核對：官方預設不能隨意疊加

本輪讀隔離環境 `openai==3.8.0`、`langchain==1.4.0`、`langchain-openai==1.6.0`、`langgraph==1.2.11` 原始碼，未升級版本。

1. OpenAI `_base_client.py`／`_constants.py`：SDK 預設 2 次 retry；Retry-After 最長接受 120 秒，超過時不提前重送；408／409／429／5xx 等規則另受 server header 影響。一般 SDK timeout 也不等於應用整輪 deadline。這是**此版本**的行為，不是所有 SDK 相同。
2. `ChatOpenAI` adapter 會把部分 OpenAI exceptions 轉為 LangChain model error；LangChain retry middleware 讀 `ModelError.is_retryable`。LangGraph graph-node 的 `default_retry_on` 是另一個判斷器，不可假定三者同義。
3. **極小離線判斷器檢查**：用人工構造的 response／exception，直接問 LangGraph 預設 predicate，輸出 `BadRequestError True`、`AuthenticationError True`、`RateLimitError True`。沒有 HTTP 請求、模型／PG呼叫或 graph 執行。只證明「未轉換的 SDK 例外不能安全套通用 graph retry」，**不證明現行 ChatOpenAI 接線正在重試金鑰錯誤**。
4. 現行 `provider.py` 沒有明訂 max_retries；外層施工若再套一次 model retry 或把整個 Agent node 包在寬泛 RetryPolicy，可能疊乘。建議讓 provider SDK 單独持有模型 transport retry；LangGraph 只對另外確認安全的節點配置明確 retry_on。

原始碼核對位置皆在隔離 package `.venv/Lib/site-packages/`：`openai/_base_client.py`、`openai/_constants.py`、`langchain_openai/chat_models/base.py`、`langchain/agents/middleware/_retry.py`、`langgraph/_internal/_retry.py`。private 函式僅用於研究真實行为，**產品不得 import private API**。

## 5. 接線修訂建議：按原因處理，不再統一叫「分析失敗」

| 實際情況 | 推薦處理 | 不做什麼 |
|---|---|---|
| 暫時網路／適用限流 | 官方 SDK 在時間與次數內自動 retry；耗盡則記中斷 | 不讓員工承擔每一次暫時錯誤；不疊三層 retry |
| 工具參數、路徑或已知可修正輸入錯誤 | 框架配對 error ToolMessage，提供安全且精確的可修正資訊 | 不把金鑰、stack trace、全部對話傳回模型；不重送相同壞參數 |
| schema／模型參數不支援、金鑰／帳務、程式 bug | 保存本輪狀態並清楚報失敗；先修根因 | 不讓 LLM 猜配置，不靠換模型或加 retry 掩蓋 |
| 限額、incomplete、streaming 中斷 | 區分正常回答與未完成／部分結果；限額不自動補滿 | 不把人工 fallback 當成顧問成功分析或員工工作資訊 |
| Memory 寫入結果不明 | 依既有 operation／receipt 查實際結果，再決定是否恢復 | 不編造失敗再重寫；不回滾已確定發布的 Memory |
| 需要恢復同一工作 | 讀真實 checkpoint、原因是否可恢復與剩餘預算，再提供恢復 | 不重送同一員工訊息；不每次重啟取得全新額度 |

前四列是 [O1–O3]／[A1–A3]／[L1–L4] 支持的原則及本案對應；最後兩列的精確 operation／receipt 接線是**既有本案發布契約**，不是宣稱 OpenAI／Anthropic 使用相同資料表。[發布切片結果](2026-09-06-analysis-only-agent-memory-publication-results.md)

工程上選已有 `ToolErrorMiddleware`／ToolNode 回饋處理已知可修正错误；未確定發布與未知例外必須向外保留，不用 catch-all 把所有錯誤變成「請再試一次」。收尾可用公開 `error_handler`，但也不能把仍可恢復的 child 草率導向成功 END；根／子流程整合需驗證。[L1][L3]

**額度校準反例（推導，不是 live 測量）：**若一次回應只調一個工具，某輪需要搜尋 Memory、讀正文、讀詳記、讀原文、C 修補，則已需 5 次工具往返＋最後回答；若另需一次搜尋擴展或參數修正，就超過 6 個模型呼叫。這正是按需深入的正常可能性，不能先當成 runaway。先用離線腳本證明正常路徑可完成，再在獨立小額驗收校準效率；本輪不決定新數字、不增加付費測試。

**人工恢復不是越少越好：**先移除「最多一次」建議。保留有界執行與耐久技術紀錄；配置未修、額度未變或寫入未對帳時，重按沒有意義。可恢復錯誤則延續原進度。是否增加預算屬另外明確操作／配置，不由按鈕暗中補額度；具體 UX 待應用設計審核，現在不增恢復配額系統。

## 6. 最小驗收與下一步

研究不是再開大型 eval。接線獲准後，只在原計畫加入可重現的故障案例：

1. 一次暫時錯誤後成功；400／401 不在未修原因下外層盲重試；記清 SDK attempts 與 Agent steps。
2. 工具輸入有誤→模型看到配對安全錯誤→修正；沒有把同一錯誤交兩層重算。
3. 正常深入讀取＋必要修正＋最終回答有額度；上限、截斷、HTTP 200 後錯誤不標成功。
4. 原話已保存但回覆遺失、C 已發布但回執返回中斷：恢復沒有重收訊息或重寫 Memory。
5. 結束的失敗可如實顯示、聊天不永久鎖住；尚未停止的 worker 不假稱已解鎖可併發寫。

結果至少記框架／SDK版本、階段、typed error、request／run／tool-call identity（有才記）、嘗試次數、耗時、已知 usage 及結果是否確定；usage 未知不是 0。記錄不包含 key，不展示 opaque reasoning。這是診斷 metadata，不新增模型填寫欄位。

**本輪完成範圍：**官方資料與本地歷史核對、SDK 原始碼核對、離線 predicate 檢查、文件修訂。沒有改隔離程式、沒跑新 PG 回歸／真模型，不把之前 120 passed 當作這次接線已驗證。下一個 gate 仍是一次審核修訂後接線，而不是逐錯誤重新討論 Memory。
