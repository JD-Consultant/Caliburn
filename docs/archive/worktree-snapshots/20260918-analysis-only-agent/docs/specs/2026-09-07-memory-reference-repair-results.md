# Q019：Memory 引用／更正來源修復結果

> 2026-09-07 · `Q019-MEM-REF-REPAIR-01` · 隔離分支 `codex/analysis-only-agent`
> 起點 `f246f43c`；只修既定 Memory 契約，不接 production／UI／JD。結果仍不代表真模型品質驗收。

## 1. 決策入口與範圍

Owner 已要求修復前輪審核問題，並參考 OpenAI／Anthropic。依[本段計畫](../plans/2026-09-07-memory-reference-repairs.md)施工；設計入口仍為主 checkout 的 [current register](../../../../docs/current-decisions.md)，不是此分支較舊的 register。

先回看[原審核](../../../../docs/specs/2026-09-06-analysis-only-context-memory-readiness-audit.md)及[Memory 設計](../../../../docs/specs/2026-09-06-analysis-only-agent-memory-design.md)，不重選 A／B／C 或重新設計五產物。OpenAI 記憶引用的依據沿[已研究的 producer→consumer 流程](../../../../docs/specs/2026-09-05-memory-summary-routing-and-deep-read-source-review.md)；沒有缺口就不重做同一研究。

| 原 finding | 修正 | 局部驗證 |
|---|---|---|
| BG-01：有效詳記路徑被 Markdown 強調污染 | 以 CommonMark token 辨識呈現及實際目標，保存文字不改寫 | 正常裸地址、強調、code、inline／reference-style link 可發布及回查 |
| BG-02：B／C 的原文引用驗證不一致，壞前綴可漏驗 | B2 validate、C validate、save、發布前共用同一驗證入口 | 空目標、損壞編碼、無效 checkpoint／訊息範圍、跨文件及不存在詳記都拒絕；head 不變 |
| MR-02：前輪只有工具時，C 更正來源漏前文 | 沿 canonical conversation 找最近可見顧問文字，保留安全封閉的中間回答 | 真正根圖兩輪反例、前置AI、多技術回合、無舊問句、未封口及續頁均覆蓋 |

這是**引用可讀性和來源定位修復**，不是自動判定 Memory 內容真偽、不是讓系統代替 LLM 做工作分析。

## 2. 官方原則、框架能力、應用接法分開

| 可查的公開依據 | 實際採用 | 不宣稱的事 |
|---|---|---|
| [OpenAI tool results](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)：工具可回文字／JSON／錯誤碼及成功失敗 | 保留工具回饋；錯誤說明壞引用、原因、回讀並複製既有地址的下一步 | 不需要額外 validation agent；並非所有錯誤都可無限重試 |
| [Anthropic tool error handling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error)：具指示性的錯誤、正確 call/result 配對 | 透過現有 LangChain 工具結果及有界修正機制；不手拼另一家 wire | 不聲稱 Anthropic 使用本案 Store、引用格式或 validator |
| [CommonMark token stream](https://markdown-it-py.readthedocs.io/en/latest/using.html#the-token-stream) | markdown-it-py 4.2.0 讀 link attributes、text／code、reference definitions，包括 duplicate definitions | 不自己解析 Markdown 強調文法，不渲染 HTML、不改原文 |
| [Markdown 官方 linkify extra](https://markdown-it-py.readthedocs.io/en/latest/using.html#linkify)、[LinkifyIt.match](https://linkify-it-py.readthedocs.io/en/latest/#match-text) | linkify-it-py 2.2.0 的整段 URI 範圍，排除外部網址內恰好像本地路徑的片段 | 不是網路抓取，也不靠逐字增加 URL 正則黑名單 |
| [LangChain Tool Runtime](https://docs.langchain.com/oss/python/langchain/tools)、[LangGraph state retrieval](https://docs.langchain.com/oss/python/langgraph/persistence) | 應用自動注入同文件 `ConversationReader`；使用既有 `get_state`／range／read | 不要求模型填 reader、版本、UUID、時間或額外 Skill／Evidence 欄位 |

底層 adapter 仍按 lock 使用 LangChain 1.4.0、langchain-openai 1.6.0、LangGraph 1.2.11／checkpoint 4.2.0、Deep Agents 0.7.13、OpenAI SDK 3.8.0。新增只限 Markdown／URI 解析依賴及其鎖檔；不為「最新」盲目升級無關套件。

具體受控地址、可讀範圍與何時拒絕，仍是本案已准的薄接線，**不是大廠提供完全相同實作的證明**。判斷與理由見上表，不用「共識」代替實際 API 證據。

## 3. 修正後的實際行為

### 3.1 引用驗證

`references.controlled_references()` 只找 `/interviews/…` 與 `conversation:…`。正常散文句末標點與 exact link／code 值分開：後者不會把 `P。` 悄悄修成 `P`。一般外部 URI 不當成本地資料，URI 後另一個獨立的受控引用仍驗證。

`MemoryArtifacts._validate_links()` 對詳記沿現有 backend read；對原文沿同一 `ConversationReader` 檢查文件、checkpoint 及訊息範圍。只驗已出現的引用，不強制每次寫入新引用、逐句引用或完整對話。模型不生成新來源地址，只複製 Runtime／read tools 已提供的位置。

真正應用 `_context()` 將 canonical reader 注入 `MemoryArtifacts`，再接到 compiled root；重開服務也如此。Artifact-only 建構可省 reader，但內容出現原文引用就明確失敗，不能跳過驗證。這是接線前提，不是模型靠重試可修復的配置問題。

B2 使用 `validate_memory` 時，壞引用回模型，能在原有預算內修正；即使模型沒有先用 validate，最後收集／保存／發布前也不能繞過。若已結束的 B2 最終仍無效，照既有契約停止，**沒有新增自動重新生成整份 Memory 的循環**。C 亦使用同一 validator，不再維護另一份 raw-reference regex。

相鄰一致性修正：C 失敗已有 JSON outcome，現在也正確設定 [`ToolMessage.status`](https://reference.langchain.com/python/langchain-core/messages/tool/ToolMessage/status)。`invalid_edit／stale／no_memory／repair_limit` 為 error，成功為 success。獨立 adapter 探針確認目前 Responses 的 `function_call_output` 對兩種 status 序列化相同；**不能聲稱原先模型看不到失敗**。兩次可修正失敗上限、resume 計數與 JSON 不變，沒有增加重試層。

### 3.2 更正來源

```text
顧問：「是由主管核准嗎？」
員工 h1：「不是主管，是處長。」 → 本輪只有工具，安全結束
員工 h2：「對，剛剛說的是 A 案。」 → C 修補
回查 C 來源：顧問原句 → h1 → h2
```

沿 `_groups`／`_turn_status` 確認跨越的回合安全封閉，再沿 `_visible` 找最近顧問文字；尚未封閉則明確拒絕，不能悄悄只留最後短答。沒有先前顧問文字時，保留安全連續的員工內容，不捏造問題。工具與 runtime notice 不冒充員工原話；opaque reasoning 不外露。

來源仍是既有 checkpoint／訊息範圍引用，read 仍每頁3,000字並給續頁位置；不複製原始對話，不摘要中間回答。這不是語意指涉解析器，也沒有改 A 的模型 Context 選取／compaction；更遠的任意關聯原文搜尋仍是另一個未完成議題。

## 4. 紅綠驗證、review 及限制

| 驗證 | 結果與意義 |
|---|---|
| 原引用反例入測 | 27 failed／17 passed；不是用測試全綠掩蓋缺陷 |
| review 補例入測 | 重複定義／外部URI／exact literal：6 failed／2 passed；再補URI子路徑及中文尾標點：6 failed／8 passed |
| 最終引用子集 | 132 passed（22.42s）：B2 回錯→模型改正→發布、C拒絕不部分發布、跳過validate也不能繞過；測試模型回覆為合成 |
| MR-02 原反例 | compiled root 的2輪C receipt測試先失敗；額外來源邊界9 failed／2 passed，修後全過 |
| MR-02＋既有C／B1／lifecycle | 101 passed（16.40s）；來源單元及真正 Agent 接線，不只純字串比較 |
| 第一輪全套 | 363 passed／0 skipped（103.24s），含專用真PG；後續review補例後需以下最終重跑 |
| 最終全套 | **370 passed／0 skipped（103.66s）**，含專用真PG；compileall、offline lock check、diff check通過 |
| 獨立 review | MR-02：48項測試，無 Critical／Important／Minor；引用：兩個 Important 均經修正及15個離線探針 CLOSED；不是 reviewer 代替主審跑全套 |

新 PG 服務測試從真正接線建立引用，關閉並重建模型／Saver／Store／ORM client 後，驗證目前 Memory、讀詳記及原文，再確認不存在 checkpoint 被拒，且讀取不呼叫模型。全套使用既有 `127.0.0.1:55433/q019_agent_test`、只清理各測試自行建立的資料。沒有重啟／重設 Docker、沒有改正式資料。

初次全套遇 pytest 自建暫存目錄權限：264 passed／25 skipped／53 setup errors（另1 deselected），不是產品模型失敗。改用明確工作區測試暫存目錄及獲准權限後可跑；不修改產品來繞過。保留一項既有上游 Starlette TestClient deprecation warning，不因此修改框架私有API。

驗證後已清理本輪四個明確建立的 pytest 暫存目錄；只有可重建的合成測試資料，沒有刪除使用者文件。專用 PostgreSQL 容器／schema 保留，下次可沿相同測試重驗。

本輪**付費模型呼叫0**、沒有新增常態模型步驟／token欄位。測試能證明確定性的引用、回饋與持久化接線，不能證明自然模型記憶完整率、長訪談推理品質或實際費用下降；這些仍需後續小額 Luna／medium 訪談與 Prompt 優化。

## 5. 下一個 gate

局部三項 finding 已通過最終重跑及獨立review，可封口；不代表原 audit 的所有能力完成。尚有：

- SK-01：按需分析 Skills／方法內容尚未接線。
- CT-01：規則＋tool schema＋導覽＋對話／工具結果＋輸出餘裕的完整 request budget。
- MR-03：grep 被上限截斷時，提示需符合實際能力；目前是**每次搜尋總共**最多4個命中，不是每檔4個（依已鎖 Deep Agents `GrepResult`／backend 實作核對原 audit 用語）。
- 舊原文沒有已知引用／詳記入口時的可達性，以及真模型延續／記憶品質與成本。

不重開已定A/B/C，不增加其他資料層。依原審核逐段補剩餘能力；涉及新工具／語意政策時先研究並提出，未批准前不擅自接 production。
