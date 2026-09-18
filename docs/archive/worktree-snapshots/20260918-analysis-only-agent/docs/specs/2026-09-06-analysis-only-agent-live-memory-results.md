# Q019 第七切片結果：C 即時修補與 A 受控刷新

> 2026-09-06 · 隔離實作／驗證紀錄；非 production、非自然模型品質結論。
> 設計入口：[Memory §5–6](2026-09-06-analysis-only-agent-memory-design.md)、[Runtime §2](2026-09-06-analysis-only-agent-runtime-design.md)。
> 執行範圍：[第七切片計畫](../plans/2026-09-06-analysis-only-agent-live-memory-slice.md)。本稿記實測與限制，不重寫 Memory 選型研究。

## 1. 交付與資料流

主顧問 A 現在可使用 `repair_memory(edits)`。C 是工具內的無模型子圖，不是第三位 Agent，也不每輪固定執行。新增 1 個模型可見工具；搭配既有 `ls／grep／read_file／read_conversation` 共 5 個。模型只填 edits 裡的 `path／old_text／new_text`，不填 UUID、版本、operation、來源 ID、Skill 或中文 quote offset。

1. A 新輸入先由官方 checkpoint 保存。middleware 取得一次已發布 head、導覽與本輪已保存問答引用；同輸入的恢復不重置。
2. 初始導覽／來源引用作為本輪固定 prefix。公開 read tools 每次由 middleware 綁到 state 保存的讀取版本；背景後來發布不會暗換它。
3. A 按需讀相關正文、詳記或原文，再提出精確 edits。已有正文與導覽載入官方 StateBackend 的私有 staging。
4. 逐節點套用 edits，避免假設同一 node 裡的 queued state writes 已立即可讀。任一項錯誤都不發布部分修改。
5. 全部通過格式／引用存在檢查後，保存 immutable artifacts → checkpoint publish request → 既有版本檢查／回執發布。
6. 成功或 stale 由官方 Command 同時更新 read head 及 ToolMessage；回覆包含新 head、導覽、相關位置。成功另回已套用的修改與來源引用。
7. 初始 prefix 不改；後续模型透過工具結果知道導覽已被哪一版取代。來源游標仍由 B 推進，C 不假裝已完成背景抽取。

沒有任何 published Memory 時，仍可讀已有詳記；不存在的正文明確報錯。C 回 no_memory，不建立假正文／假導覽。下一個新訪談才重新載入 head；stale／C成功亦是明確的切版時點。

## 2. 框架負責什麼，哪些是本案接線

| 能力 | 實際使用 | 依據／界線 |
|---|---|---|
| 工具參數、runtime 隱藏、結果回模型 | LangChain tool、ToolRuntime、ToolMessage | [官方 tools](https://docs.langchain.com/oss/python/langchain/tools)。模型參數驗證沿框架，不重造工具 runner。 |
| 同步更新讀版及工具回覆 | Command(update=…) | 同上。Command 不等於替 Store 自動提供跨檔交易。 |
| 固定／受控變更讀取版本 | AgentMiddleware before_agent／wrap_model_call／wrap_tool_call、公開 ToolCallRequest.override | [官方 custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)。每次綁固定 readonly backend，沒有依可變 state 偷換 Store namespace。 |
| 精確 old/new 套用 | StateBackend.edit、FilesystemState | [官方 backends](https://docs.langchain.com/oss/python/deepagents/backends)。不存在或多次命中原文即報錯，不 fuzzy replace、不 replace_all。 |
| 子步驟保存、工具恢復 | per-invocation StateGraph 子圖繼承 A 的 Saver | [Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)、[Durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)。不是額外員工 thread，也沒有額外 LLM。 |
| 正文／導覽一起發布、舊請求對帳 | 沿第四切片 SQLAlchemy versioning＋短 PG transaction／receipt | [發布結果](2026-09-06-analysis-only-agent-memory-publication-results.md)、[SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/versioning.html)。這個跨元件 composition 是已核准 mapping，不宣稱 OpenAI 內部同 schema。 |
| 本輪問答回查 | canonical checkpoint 的 capture_input／read | 原文不另存一份。新 capture_input 接受 run 內已保存輸入；B1 的 completed-window capture 規則沒有放寬。 |

核對版本沿 lock：LangChain1.4.0、LangGraph1.2.11、DeepAgents0.7.13、langchain-openai1.6.0；本段未升級依賴。新官方 backends 文件已不建議舊 mutable backend factory／ctx.state 接法，故使用公開 tool middleware，而非照歷史範例拼裝。

## 3. 實作中發現與修正

**C-01：參數錯誤不一定拋到外層。** 最初包 ValidationError 的方式漏計失敗次數。安裝版 ToolNode 的公開執行路徑先驗證參數，再轉成 status=error ToolMessage。因此改用框架已回傳的錯誤訊息，提供有界欄位提示並納入同一失敗上限；不重写 schema parser。回歸測試先失敗，修正後通過。

**C-02：不能把提交成功等同已通知主顧問。** publish request 已耐久保存後，提交回覆丟失會留在 pending tools；重建全部 clients，恢復相同 operation，取得 receipt，再產生一次工具回覆。若已存在後續發布，區分「本次實際生效版本」與「目前讀取版本」，不倒退 head。

**C-03：本輪來源不是完成訪談窗口。** C 所在 run 尚未完成；不可放寬 B1 來源門檻。新增窄的 capture_input，只定位已保存的最新 HumanMessage 與前一個可見顧問問題。回查仍保留 role，opaque reasoning 不顯示、不轉成筆記。

## 4. 已實測／未實測

已實測（外部 HTTP 為合成回覆，其餘用真 framework）：

- 正文／導覽同批成功、相依 edits 按順序可見；批內後項失敗時沒有部分發布。
- old_text 不存在／多重命中／空字串、未知或禁止路徑、無效原文與詳記引用、數量／大小上限。
- 錯誤含修正提示、是否還可重試；格式錯誤亦納入失敗計數，新輸入才重置。
- 背景先發布 → C stale → 明示新版 → 重讀後重提；不能無聲覆蓋背景新增的其他內容。
- 同 run 固定 guide；新 run 載新版；工具結果明示更換而非重寫初始 system prefix。
- 無 head 不造假 Memory；跨文件入口在模型／Memory 動作前拒絕。
- 不正常的平行 tool response 在任何 tool 執行前停止。
- C receipt 可回讀「前一顧問問題＋本輪員工更正」，不推進 B processed_source。
- 真正 PG 重建 provider HTTP client、Saver、Store、ORM：保存前、發布前、提交後回覆丟失、提交後已有後續版本四種情境。無重複發布、失敗計數保留、既有 C request ID 不換；恢复後 read tools 看到對應新版。

驗證數字與 review closure 於本稿最後更新；付費模型呼叫 **0**。合成回覆不能證明模型會正確選擇修補時機、自然記憶品質、訪談缺口判断或長期成本。

## 5. 範圍與下一步

初始工程限制為每次 C 1–8 edits，old/new 合計至多 12,000 字；每個 A 輸入最多兩次可修正 C 失敗。不是大廠統一值，也不是 A 整體 token／工具／費用上限。C 成功後，A 自己仍可能有後續模型呼叫。

儲存／提交不明錯誤維持 pending，不給模型猜測成功。這段只有 graph 的恢復接線，不提供完整 UI 的 retry／cancel／replan。C 不初始化 Memory、不全量重新整理、不判定員工語意真偽、不要求每次修改附新 quote。

未交付：應用排程／重啟重排／單文件 run admission、完整使用量與錯誤介面、Skills 產品接線、只分析 UI、小額真模型訪談品質測試。後续先收斂接線與驗收計畫，不展開 JD、不重開已完成的 Memory 選型。

## 6. 驗證與保存點

- 初始缺模組 RED：8 failed；接線後8 passed。
- 完整邊界測試20 passed；PG中斷恢復4 passed。
- 全套專用PG：120 passed／0 skipped，17.01s；包含前六切片回歸。compileall、uv lock --check --offline、diff check 通過。
- 首次非提權 lock check 因 uv 使用者快取存取遭沙箱拒絕；取得讀快取權限後通過，沒有改依賴／鎖檔。
- 獨立 reviewer Ampere：未發現 Critical／Important 阻塞，可建立 isolated savepoint；自行重跑 live20 passed／diff check，PG120採本輪主實作者證據，未宣稱獨立再跑PG。
- 保存點使用本地 tag `q019-live-memory-v1`；實際commit與下一步由主checkout [register §0](../current-decisions.md#0-最新任務llm-q019從零設計只分析的第一版)記錄。只提交此段10個檔案，不merge／push，不修改production。
