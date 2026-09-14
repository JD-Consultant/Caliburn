# Q019 第五切片：訪談抽取與耐久交接結果

> 2026-09-06 · 隔離實作；修復後全套 **71 passed／0 skipped**。獨立 review B1-R01／R02 已重現、修復並限定複核關閉；本地保存點見[決策入口](S:/caliburn/docs/current-decisions.md)。
> [計畫](../plans/2026-09-06-analysis-only-agent-extraction-slice.md) · [有效 Memory 設計 §2.2](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-design.md)

## 1. 本段完成什麼

已保存的完整訪談 → 有界問答視窗 → B1 三欄抽取 → checkpoint → 詳記／候選 Store artifacts。

- 模型只填 `rollout_summary`（詳記）、`raw_memory`（候選）、`rollout_slug`（短名稱）；Runtime 產生真正地址、來源引用及工作路由。不填 UUID／逐字位置／Skill ID。
- 來源為已完成 Human→AI 回合；讀完選定範圍的所有可見文字分頁，不只留頭尾。顧問問題與員工陳述保留角色；opaque reasoning 不送 B1。
- 每個新回合恰好進一個新來源視窗；可帶前一完整回合作背景，另標 CONTEXT_ONLY，不冒充新內容。詳記 header 同時保留新來源與可選背景引用。
- 空候選可以成功；拒答、截斷、錯格式、來源未完成不能假裝「沒有新資訊」。
- 模型結果先 checkpoint。Store 寫入失敗後恢復 save，不必重跑已耐久保存的抽取；先前成功視窗與地址保留。
- 本段不更新目前工作理解、不發布版本、不推進 B2 已整併游標。B1 本身不是背景排程器、完整 Memory 或 JD 編輯器。

## 2. 用哪些成熟元件，哪些是本案接線

| 責任 | 實際元件與邊界 |
|---|---|
| 原生格式輸出 | ChatOpenAI.with_structured_output，json_schema／strict／include_raw；Pydantic 三字串及應用格式檢查 |
| 節點與恢復 | LangGraph StateGraph extract→save，官方 Saver／sync durability；不是自寫模型重試迴圈 |
| 原始訪談 | 原 canonical Checkpointer；ConversationReader 用公開 get_state 讀固定 snapshot，不增第二份聊天倉庫 |
| 詳記與候選 | 既有 Deep Agents StoreBackend＋LangGraph Store；runtime header、來源路由、immutable artifact policy 是本案接線 |
| B1 工作 | 文件固定的技術 checkpoint，僅 refs／視窗／進度／已產生地址／當前抽取結果；不是第二聊天室 |

抽取 instructions、完整回合切分、字數限額、來源先後檢查是**本案 mapping**，不宣稱 OpenAI／Anthropic 內部採相同程式或 schema。框架提供保存／恢復，不自動定義何謂完整訪談、有效新範圍或職務抽取品質。

官方依據（本輪只補接線缺口，不重做 Memory 原理研究）：

1. [LangChain models／structured output](https://docs.langchain.com/oss/python/langchain/models#structured-output)：獨立模型直接結構化抽取、保留 parsed 與 raw。另核對鎖定 langchain-openai1.6.0 的公開 with_structured_output 實作：kwargs 需傳入此方法的內部 model binding；不能假設外層 RunnableMap.bind 會傳到模型。實際 wire 測試驗上限。
2. [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)：格式約束、refusal／incomplete 的分別；strict 不是語意真實保證。來源模型完成狀態亦不可只用 graph END 代替。
3. [LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)、[Graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api)：節點間保存與恢復。外部 API 成功但結果尚未 checkpoint 時，恢復仍可能重新呼叫，不承諾 API exactly-once。
4. [Deep Agents backend](https://docs.langchain.com/oss/python/deepagents/backends)：沿用公開 write／download 接點；Store 寫入與 Saver 不在同一資料庫交易。
5. 五產物／引用 producer-consumer 理由沿用 [Q019 Memory](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-memory-design.md#1-保存責任與五個概念) 及其 OpenAI 研究路由；沒有再造第六種導覽。

## 3. 測試、故障與處理

模型 HTTP 全為合成回覆；框架、adapter、serializer、Store／Saver 是真實元件。**付費 API 0、不讀產品 .env、沒有改 production。**

- 基線 42 passed／7 PG skipped；上一切片真 PG 結果是49，不把 skip 當通過。
- 新功能最初6項確認缺 extraction module 而失敗。基本接線後逐步補邊界。
- 本段單元／in-memory 契約共20項；完整回查加 B1 合計39 passed。驗三欄 JSON schema、實際 output limit、來源角色、無 A reasoning、分段、空候選、原文未動、部分完成後恢復等。
- 新增真 PostgreSQL2項：保存前中斷／summary 已寫但 candidates 未寫；關閉並重建 DB connection、Graph、HTTP client 後，直接接著 save，禁止任何重複模型呼叫；來源仍可回讀。這是連線重建及人工失敗注入，不是 kill process／斷電實驗。
- 修復前全套66 passed in12.18s；独立審核新增5個反例後，修復後全套 **71 passed in12.57s／0 skipped**。包含先前原生 continuity、原文回查、真正 PG 並行發布／回執測試。
- compileall、uv lock --check --offline、diff check 通過；73 packages、無新增依賴或版本調整。

本輪問題沒有用多加 Agent 或重試來掩蓋：

| 問題 | 重現與修正 |
|---|---|
| output limit 沒到 provider | wire 缺 max_output_tokens；改用公開 with_structured_output kwargs，測試確認實際 HTTP payload 有4096 |
| 壞文字格式反覆重放 save | 超長行先被 checkpoint，save永遠重試同一壞內容；改在 Pydantic validator 用既有 artifact 格式檢查，錯誤停 extract，不當模型成功 |
| 不合法來源使工作永久 pending | 來源規劃放進已啟動 graph；改 read-only preflight，驗過 refs 才啟動 durable job |
| B1-R01／P2：graph END 不代表回覆完整 | 真 Agent＋合成 incomplete 回覆重現；另測缺 status。2 failed→修復：来源末尾 Responses status 必須明確 completed，測試 fixture亦明確標記 |
| B1-R02／P2：X→Y→X 又呼叫模型 | 同 snapshot／跨 append checkpoint／重疊範圍3 failed→修復：最近同ref回已存結果；更舊或重疊的新請求明確拒絕，不默默重抽，不建立另一份結果倉庫 |

R02 依 canonical message 實際順序，不能用 UUID 大小或時間猜。前次終點找不到也停止。新範圍是否連續涵蓋全部待處理來源，仍由之後 B 整體工作選取驗證；本規則只攔舊／重疊輸入。**沒有強制重抽 API、沒有任意歷史結果查詢**，不能把它寫成已有這些能力。

Reviewer 初審親跑 B1＋回查34項並另查5,418字跨頁原文；修復後限定複核39 passed in3.89s。另驗前回合incomplete／缺metadata但最後回合completed仍拒絕；舊範圍／重疊／前次終點缺失拒絕後checkpoint不變，合法前文重疊與最近同ref快取仍成立。B1-R01／R02 CLOSED，無新阻塞。未跑 PG，不將主代理71項完整 PG 回歸算為其獨立執行。

測試清理僅專用 `q019_agent_test`／localhost55433 的隨機 test document、B1 workflow 與 artifacts；沒有 drop 庫／表或刪現有訪談。

## 4. 限制與下一段

- 目前僅文字訪談。工具／媒體／opaque block 在 canonical 保留並回報省略種類，不宣稱 B1 已理解非文字內容。
- 初值：每視窗6,000可見字、可選前文1,500字、單次輸出4,096 tokens、每批最多16視窗；可配置，不是大廠共識最佳數字。字數不是完整 request token 計量，output limit 也可能含 reasoning 消耗。
- 完整單回合太大或整批超限先停止，不偷偷截短。前文只能提供有限消歧；不能保證每視窗語意自足。實際長輸入處理體驗留後續，不假稱已無限訪談。
- 同文件一次一個 B1 job 由 caller 協調，尚無背景排程／多 process admission／取消。失敗保存可留下未引用 artifact（部分寫入測試確有1份），不對 A 發布；無 GC。
- 模型輸出已 checkpoint 才能避免重呼；失敗 extract 的顯式 resume 可能再次呼叫，沒有自訂無限修正。尚無付費成本／抽取忠實度證據。
- 本段只備妥 B1 交接；**下一段 B2：按需補讀詳記 → 整併正文與小型導覽 → 接既有發布／過期版本恢復**，之後才 C 局部修補、A受控刷新、排程、UI與小額真模型驗證。不重開既定五產物／來源 owner／框架名稱議題。
