# CT-02：正常訪談入口修復與小額驗收

2026-09-07 · **正常訪談三輪樣本通過；獨立 Memory 回查未完成。** 隔離程式提交：`e3b93aa7`。

入口：[current decisions](../../../../docs/current-decisions.md) → [核准研究](../../../../docs/specs/2026-09-07-context-engineering-native-first-review.md) → [施工計畫](../plans/2026-09-07-native-context-normal-interview.md)。
本頁只持有本輪修復／實測結果，不重寫 ABC Memory 設計。細部輸入、回覆、工具呼叫、usage、腳本與指紋見[合成測試證據](evidence/2026-09-07-native-context-normal-interview.json)。

## 1. 改了什麼，沒有改什麼

原本每個 A／B1／B2 生成前都必須成功呼叫另一個遠端 token 計數接口；先前 gateway 的該接口 404，導致尚未開始訪談就被擋下。Owner 已核准 CT-02 改為原生優先，而不是以猜測 token 數冒充精確計數。

- 新增 `Q019_CONTEXT_BUDGET_MODE=native|exact`，預設 `native`：每次最終請求仍驗證模型、輸出上限、`truncation=disabled` 和指定 endpoint，但不呼叫遠端 count；额外 create 參數交由官方 SDK／provider 契約處理。
- `exact` 明確選用時保留原完整計數、容量比較及失敗行為，404 不偷偷 fallback。非法 mode 在開 DB/client 前拒絕。
- 原生 `reasoning={effort:medium, context:all_turns}`、inline compaction、有界讀取、原始對話、框架錯誤型別與 usage 均保留。沒有移除容量配置，也沒有宣稱 native 是事前精確總量保證。
- A 仍9-model／8-tool；不加上限、不新增摘要 Agent、計費系統、第二套訊息儲存或Memory schema。本輪沒有改 prompt／Skill／Memory 排程與 publication。
- 只修改隔離分析版，未接 production／JD／Web UI；未 merge／push。

依据：[OpenAI server-side compaction](https://developers.openai.com/api/docs/guides/compaction#server-side-compaction) 提供原生壓縮；[input-token counter](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count) 是可用接口，文件未要求每次生成前必呼叫；[LangChain Context Engineering](https://docs.langchain.com/oss/python/langchain/context-engineering) 區分 request context 與持久 state。**這個模式開關是已核准的本案接線選擇，不宣稱所有大廠都有同名機制。**

## 2. 離線／PostgreSQL 驗證

主審完整 **547 passed／0 skipped，70.45s**，含真實專用 PostgreSQL；只有既有 Starlette TestClient deprecation warning。模型 HTTP 全為合成，這部分零付費。compileall、offline lock（83 packages）、diff check 通過。

- TDD：新增 native 介面／行為測試先14 failed；完成接線後綠燈。另修正測試的 user message `type=message` 期待，不更動框架輸出。
- A 的規則、guide、Skill／tool result、opaque 延續與 canonical 原文，native／exact 皆跑真序列化路徑；B1 strict schema、B2 工具錯誤與後續讀取同樣兩模式檢查。
- 真 API factory 的 default／native／exact 三種配置與資源關閉均以真 PG＋合成 HTTP 驗證。
- Native provider overflow 無外層重試；A 安全結束，原話保存、可送新訊息。這不保證下一個同樣過大的請求會成功。
- 已有 `test_official_model_visible_pagination_preserves_every_long_line` 檢查官方分頁工具的長中文、續讀與全部行保留；因此取消重複測試，不另寫裁切器。

獨立 review 未發現 Critical／Important；非阻擋 CT02-R01 已修正文案：native provider overflow 的 status／code 均為 `configuration_error`；exact 本地容量拒絕的 code 才是 `context_budget_exceeded`。審查者另外補驗76 passed（14 deselected），不是替代主審的全套驗證。

完成後另作唯讀 evidence review：核對12筆請求、兩段共用額度、usage費用、secret／opaque排除與報告邊界，沒有可採取行動的不一致；未為review追加API。

## 3. 真實訪談：三輪全部回答完成

使用本地已授權且 ignored 的設定，**OpenAI 官方直連、gpt-5.6-luna、medium**；真 `create_app()` 預設 factory、官方 Saver／Store、專用新 DB `q019_native_3756a4a160`。沒有改用舊 OpenRouter adapter；本輪不代表 OpenRouter 的原生壓縮已驗證。

| 員工輸入 | 實際觀察 |
|---|---|
| 接案前端工程師；A 餐廳點餐網站、單次付款、退款先說店長核准 | 按需讀工作範圍 Skill，詢問具體交付標準／確認人；2次模型請求完成 |
| 更正 A 為營運經理核准，自己只排查前端；補 B 健身房訂閱網站、財務處理扣款失敗 | 採納更正、不混合兩案；按需讀案例比較／成果 Skill，追問上線標準；3次請求完成 |
| 要求簡短回顧共同工作與 A／B 分工 | 正確回答共通前端開發與串接、A營運經理、B財務，未編造持續維護責任；1次請求完成 |

三次 run 均 `completed`，沒有錯誤碼、incomplete 或計數 HTTP。可見對話中每段員工原話各一次；後續請求帶回先前 opaque item 的完整 SHA256 相同，不把隱藏推理輸出給員工。這證明 adapter 保留／重送，不宣稱能檢視或保證模型內部如何使用。原生延續依據：[OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)。

這三輪背景狀態維持 idle，沒有通知或 Memory head。因此**近期案例回顧不是長期 Memory 的驗收**；也未觸發32K壓縮門檻，沒有真 compaction 產物，不宣稱長訪談全驗成。

## 4. 獨立 Memory 回查：資料路由可到達，最終答案仍 OPEN

再使用同一帳本的剩餘6次，重用[先前實際生成的詳記／正文／導覽](evidence/2026-09-07-b1-attribution-calibration.json)，只重建合成來源與引用地址，不重跑 B1／B2、不改已生成內容。fresh context 只給 guide、讀取工具及問題，不先塞原訪談；模型沿用 factory 的原生接線。Fixture使用 InMemory Saver／Store；**不是產品關閉重開後的持久記憶測試**。

實際順序：搜尋「青禾」→「拾光」→「備份」→「驗收」→列出一個已知詳記目錄→呼叫 `read_file` 讀詳記。第13次模型請求在送出前被同一帳本擋下；沒有最終回答。最後一次 read_file 的結果沒有出現在已送出的模型輸入，也沒有另外保存，因此不能把它寫成已完成詳記理解或原文回查。

**下一個局部問題：**這題跨多個主題，模型逐詞 grep 後又 ls 已知目錄，步數偏多。後續可研究／校準「已知路徑直接有界讀取；廣泛回顧不要逐個關鍵詞搜尋；資料足夠就回答」。這是依本次軌跡提出的候選優化，尚未實作／驗成，不要求增加模型額度、去掉限制或全量塞 Memory。普通訪談修復不因此重新打開框架選型。

**Owner補充後的官方複核（本轮未改提示）：**完整回看[既有OpenAI深查稿](../../../../docs/specs/2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)，並重查[Codex目前read-path prompt](https://github.com/openai/codex/blob/main/codex-rs/ext/memories/templates/memories/read_path.md)的quick-pass段落：從導覽取相關詞、搜尋正文、沿已指出的摘要路徑深讀，避免廣掃；4–6是理想搜尋步數，不是保證包含最終回答的模型請求數。因此不能只因本次6次未答就宣称不符合大廠做法。[Anthropic工具工程指引](https://www.anthropic.com/engineering/writing-tools-for-agents)主張先查完整tool軌跡與回應資訊，再判斷是否應改善描述、分頁或工具；不是先增加工具／額度。該文2025-09-11發布，屬仍公開的工程原則，**不冒稱2026新API規格**。

框架也不能照Shell名稱猜功能：[Deep Agents官方reference](https://reference.langchain.com/python/deepagents/middleware/filesystem)與已安裝0.7.13 `GrepSchema`／工具說明明確是literal search、不是regex；不可直接改成 `A|B` 就期待批次命中。當前正文只有1095字、導覽218字，官方 `read_file` 已有有界分頁，是後續可比較的既有能力；是否更有效尚待小額驗證。本輪唯一確定的未完成原因是第13次被預算擋下；未觀察到HTTP失敗、資料遺失或Memory內容幻覺。**先查官方與框架，再提出有依據的局部變更；沒有新增自訂搜尋器或覆寫既有Memory設計。**

## 5. 費用與精確界線

Owner本輪核准 **最多12次／US$0.10費用預留**，A／獨立reader／SDK重試共同計數；已用12次，不再加call。臨時帳本先離線驗證第13次與費用預留越界可阻擋，不是新增產品計費平台。

| 項目 | 數值 |
|---|---:|
| 正常訪談 A | 6次；估算 US$0.00420973 |
| 獨立回查 | 6次；估算 US$0.00221299 |
| 合計 | **12次；估算 US$0.00642272** |
| 累計 input／output | 34,620／1,262 tokens |
| input中的 cached／cache-write | 15,341／14,914 tokens |
| output中的 reasoning | 498 tokens（已含output，不重算） |

依[官方 Standard pricing](https://developers.openai.com/api/docs/pricing)：Luna每百萬 input $0.20、cached $0.02、cache-write $0.25、output $1.20；12次 response 都回 `service_tier=default` 且遠低於長context價檻。費用由實際usage換算，**不是帳單實扣聲明**；call數不是訊息輪數。每筆預留以保守輸入估計＋輸出上限，未聲稱 token 精算或一般產品硬美元保證。可見有快取命中，但未改額外快取參數；[官方 prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) 的快取不等於擴大context。

**交付邊界：**正常三輪樣本與機制回歸通過；獨立完整回查、真長訪談壓縮、背景整理＋回查整體品質仍分別 OPEN。新probe DB保留供回看，服務／workers／clients已隨factory關閉。沒有刪除舊資料、重啟Docker或碰production。
