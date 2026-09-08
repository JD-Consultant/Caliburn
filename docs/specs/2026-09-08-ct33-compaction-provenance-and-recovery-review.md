# CT33：壓縮來源追溯與漏存恢復——先分清測到了什麼

2026-09-08 · LLM-Q019／Q019-MEM-CADENCE-01／CT15-R07 · **G2 唯讀調查完成；下一項局部驗證待審，G8 OPEN。**

## 本輪唯一問題與邊界

Owner 在 [CT32](2026-09-08-ct32-context-factor-isolation.md) 後問「壓縮不是只壓縮原始對話嗎」，並要求繼續研究如何解決。查明舊 compaction 的生成來源、目前規則與 Memory 是否重新送達，再選最小下一步。沿用 CT25，不重做第四版同義提示；不關閉 reasoning／compaction、不改 Patch／B 排程、不添加完成判斷 Agent、不接 production。此次無模型生成、無資料庫修改；既有付費帳本保持 closed。

## 1. 從封存請求找到的事實

來源不是聊天印象，而是 [CT16 封存](evidence/2026-09-08-ct16-notification-live.json) 與 [CT32 封存](evidence/2026-09-08-ct32-context-factor-isolation.json)。兩檔 SHA256 分別為 `7a0914d09e90ad64a7f6ff5b70e35f060ffc6983022d4198227e1512a92d685f`、`4c5586e1552ebbdd0041be369b6c39e8e997b60f4ac9a1c640a4a7d73d5b21f9`。以 `requests[].number` 定位請求，不把 number 當陣列索引。

1. CT32 opaque_only（request 9）帶入的 compaction SHA256 為 `a7c6371079a083784b93acbbdc574d899272e13096f6050f21362c1d28e5233c`。它正是 **CT16 request 16 的 opaque_output**，不是本輪用新規則重新產生。
2. CT16 #16 是首次「每月10日→5日」更正：生成回應與 compaction 的同一請求，0工具、口頭答5日，發布 Memory 前後仍 revision 3／10日。之前 #14–15 的背景鏈已發布 revision 3；因此不是修補時根本沒有 Memory。完整沿革見 [CT16 結果](2026-09-08-ct16-notification-live-results.md)。
3. CT16 #16 的 system Memory 區塊當時仍寫 `Repair is optional and does not run background consolidation.`；已提供 `repair_memory` 在內的六個工具名稱，導覽有10日。這是**當時輸入的事實**，不是我們解讀加密內容的結果。CT16 封存只有工具名稱，不能用它宣稱當時完整工具 schema 與 CT25 完全相同。
4. CT32 #1（visible_only）和 #9（opaque_only）的 system 都已含 CT25 的「已核實過時→讀取→final 前修補」、聊天確認不等於保存；兩者都有 revision 3、導覽10日及同六工具，已沒有上述 optional 句子。CT32 #9 仍0工具；因此不能說現行 prompt 還寫 optional，或現在規則／導覽沒有傳送。
5. CT32 #9 沒產生新 compaction；它是在沿用上述舊 compaction 的請求中直接回答。舊 compaction 的生成請求 CT16 #16 自己也帶有更早的 compaction／reasoning。不能把整段現象簡化成「第一次壓縮就出錯」。

**Unknown：**封存只保留 opaque 的 type／hash，不解密。生成請求的輸入與輸出可追溯，不代表知道其間 compaction 編入了哪句規則、哪段回答或什麼推理；尤其不能宣稱其中一定寫著「已保存5日」。CT32 單次因素對照支持繼續調查這份延續內容，但不證明 API 壓縮有缺陷、因果唯一或普遍失敗率。

## 2. 現行資料流與官方契約核對

| 核對處 | 實際情況／來源 | 本案結論與邊界 |
|---|---|---|
| 壓縮與資料保存 | [OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction#server-side-compaction) 說明 inline compaction 延續 prior state／reasoning；與 standalone compact 的輸出處理不同 | 壓的是提供模型的互動延續，不是刪除資料庫原始訪談，也不會自行修改外部 Memory 文件。工具讀到的資料可能出現在歷史 context；不等於對外部文件做 CRUD |
| 原生回送 | [ChatOpenAI Context management](https://docs.langchain.com/oss/python/integrations/chat/openai#context-management) 支持保留 compaction，並可移除其前的舊訊息 | `provider.py` 使用 stateless Responses／responses-v1／all_turns；`context.py` 只建立 request copy。沒有發現把 standalone 規則錯套成 inline，或在此函式覆寫 canonical 訪談的證據 |
| 現行規則與導覽 | `MemorySession.before_agent` 每個新員工輸入取得當時發布 head／guide；`wrap_model_call` 重新附到本次 system，C 成功回饋依現有契約更新本輪 read head | 已核對真實 wire，而非僅看 middleware 名字。CT32 #9 的目前導覽10日與現行修補要求都有送出；**送出不等於模型必然採取動作** |
| 壓縮後補回內容 | [Claude Code 官方 hook 範例](https://code.claude.com/docs/en/hooks-guide#re-inject-context-after-compaction) 可重新注入關鍵規則、近期狀態 | 是官方可配置方法；本案已另送本輪規則與導覽，不能把再複製一次相同資料稱為已找到缺口，也不直接照搬 Claude hook 名稱 |
| 工具不呼叫 | [Anthropic troubleshooting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use#claude-calls-the-wrong-tool) 建議核對名稱、schema、例子與用途區分；[OpenAI tool routing](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#tool-routing) 不應因答案看似已知而跳過必要查閱 | 這些指引已在 CT25／30／31 核對或對照；不能無限疊同義句，也不能將 Sol 指南當成 Luna 成效保證 |

實際讀過的本地接點：[context.py](../../experiments/analysis-agent/src/analysis_agent/context.py)、[runtime.py](../../experiments/analysis-agent/src/analysis_agent/runtime.py)、[live_memory.py](../../experiments/analysis-agent/src/analysis_agent/live_memory.py)、[provider.py](../../experiments/analysis-agent/src/analysis_agent/provider.py)。本輪不重跑已在 CT32 完成的資料持久化回歸，也不宣稱重新測過全套。

補充底層差異：本機 LangChain 會將 system message 轉成 Responses input message；本機 OpenAI Agents SDK 則將 agent instructions 傳到頂層 `instructions`。這是兩個官方 adapter 的接法差異，**目前沒有直接證據證明前者導致本案失敗**。不因名稱不同就換 SDK、不宣稱 API 忽略了 system，也不順手搬動全部 context。若日後要對照，須另以相同文字、工具及 opaque 做單一接點對照。

## 3. 下一步建議：分開「第一次採用新規則」與「恢復舊漏存」

**建議先不改產品。**在同一合成訪談的隔離副本，回到 CT16 首次5日更正之前、Memory 已發布 revision 3 的一致時間點，用現行 CT25 規則接收同一句更正。保留當時真實既有 conversation、reasoning、compaction；不是清空上下文的新聊天，不重跑整場訪談，也不替模型補一句「請使用工具」。

這需要先確認原保存點能取得「當時對話＋當時 Memory」一致狀態；不能只倒退 Checkpoint 卻任意混搭 Store。如取得不到，就明示限制、另審最小重建測法，不手工偽造 opaque。此處是待審驗證方向，未建立新試驗／帳本，沒有默認追加費用。

原 CT32／CT28 漏存資料保留作**恢復回歸**。兩種情境回答不同問題：

- 新規則第一次更正就失敗：現行行動選擇本身仍不足，不應再只盯著那份「包含先前失敗時期」的舊延續。
- 第一次能修、恢復舊漏存仍失敗：需針對漏做後如何查實際狀態並恢復；不能以新起點成功抹掉舊失敗。
- 都需要成功及反例不誤寫，才往長訪談驗收走。單次成功仍不代表穩定或根因唯一。

**若仍需更強控制，沿用 [CT30§4](2026-09-08-ct30-missed-memory-write-official-controls.md#4-三個候選與建議未授權施工) 的完成檢查候選，不重新發明第四種機制：**檢查未完成的必要動作，將可核對理由交回原模型續做。[Claude prompt-based Stop hook](https://code.claude.com/docs/en/hooks#prompt-based-hooks) 公開單次模型判斷與不通過續做；[LangChain agent jumps](https://docs.langchain.com/oss/python/langchain/middleware/custom#agent-jumps) 能承接原迴圈。它不是框架內建的 Memory 漏存偵測，也不是各廠預設；會增加判斷／續做成本與誤判風險，仍須 Owner 同意及局部對照。**未使用工具≠一定應修補**，不能用0工具或版本未變直接攔所有回合。

## Closure

- 新證據：舊 compaction 的生成請求已定位；當時 optional 規則與現行 before-final 規則確實不同；現行規則／導覽已送達。
- 狀態：未證明根因、未修復；G8 OPEN。系統化除錯要求先追溯資料，因此本輪沒有再添加 prompt 或更換架構。
- 下一唯一 gate：審上述「現行規則首次更正＋舊漏存恢復」局部驗證範圍；不是重新開一輪泛查 Memory 架構。
- 停放：Patch 介面、強制 tool、完成判斷 Agent、B 時機、模型更換、system／instructions 接法對照。新證據若直接指向接線缺口，才調整優先順序。
- 紀錄分層：本頁只存增量結論與來源；完整請求留既有 evidence、CT32 留原對照結果，current register 只更新路由。不複製長逐字稿、原始加密內容或 API 設定。
- 本輪核驗：封存 hash 與 request number 交叉比對、舊／新規則及導覽出現在 wire 的斷言、本頁本地文件連結均通過；產品 src／tests 相對 CT25 無變更。這是研究依據核驗，不是新增模型成效測試。
