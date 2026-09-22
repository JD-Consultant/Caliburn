# Q019-MEM-SUMMARY-01：OpenAI 詳記遇到後續更正時如何處理

> 2026-09-06 · G2 定向官方 source review；事實已核對，Caliburn 保存／回查接法仍 OPEN。沒有程式施工、沒有改保留政策、沒有付費模型測試。
> 入口：[current decisions](../current-decisions.md)；前題：[摘要路由 §2.4](2026-09-05-memory-summary-routing-and-deep-read-source-review.md#24-2026-09-06-補查詳記可否更新不等於原文不可改)；受影響設計：[Q019 Memory](2026-09-06-analysis-only-agent-memory-design.md)。只補「訪談詳記」，不重選整套 Memory。

> **最新狀態：後續接法的效果邊界已獲 Owner 同意，WORKING。**見[詳記更新與更正回查接法 §6](2026-09-06-interview-summary-correction-routing-proposal.md#6-審核界線與下一步)。同段可重抽、跨段靠目前正文與更正引用；本稿 OPEN／待審措辭保留研究當時沿革，不重開已收斂選型。工程設計／計畫與實作尚未因此完成。

## 0. 直接回答與證據界線

Owner 問：A 案例在早期訪談有一種說法，後續補充或更正後，是否留下兩份矛盾詳記？模型再打開舊詳記怎麼辦？

**OpenAI 並非一律新增詳記，也不是發現更正就全面改寫所有舊詳記：**

| 情況 | 公開做法 | 不能延伸成的保證 |
|---|---|---|
| 同一 Codex thread／rollout 後來有新內容 | 再符合抽取條件時重新抽取；同一 thread 的 Stage1 結果可被替換，之後同步詳記 | 不是每則訊息立即更新，也不是依「案例 ID」局部修補 |
| 不同 rollout 再談相同事情 | 各自抽取；整併模型按相關性與新舊證據補讀詳記，更新正文、引用及導覽；可清理重複詳記 | 沒有查到保證找齊、回寫所有舊詳記中同一案例的機制 |
| 讀到可能過時的記憶／詳記 | 先經 Memory 正文路由；提示詞要求按過時風險核實、必要時揭露不確定 | 不是讀任何舊檔都自動取得後續更正，更不是語意正確性的 deterministic 保證 |

實作、提示詞證據分見 §2–4。**「原始訪談不改」與「生成詳記永遠不能更新」是兩個不同命題。** 先前不可變分段詳記屬本案 mapping，不是 OpenAI 規定。

## 1. 版本與研究方法

先回讀摘要路由、09-04 progressive-disclosure 研究及 Q019 Memory；缺口集中在抽取更新條件、保存／同步，以及讀取時如何遇到更正。再查官方文件、固定 source 與相關測試，不重新廣泛搜尋 Memory 名詞。

- [OpenAI Sandbox Memory 說明][O0]支持 Session／Memory 分工、兩階段與 live update；細部行為以下列 source 為準。
- Codex：研究時 main `ac192cd7937b0d73edc6dffe009940ae53782dd4`，commit 時間 `2026-09-06T07:42:32Z`。
- Python Agents SDK：研究時 main `1d471a4775bf2f40179f411824da383deb4c3fca`，commit 時間 `2026-09-05T11:16:52Z`。
- Codex storage／consolidation／read prompt 與前稿固定 SHA `574a36ff99f0807a24f5b043f593122bf151908d` 的 blob 相同；新增的是 DB 更新與 SDK 接線證據，不是先宣稱舊資料過時。
- 這是官方公開實作快照，不等於已發佈穩定 SDK 契約，更不代表 ChatGPT 全部內部 Memory。TypeScript SDK 本輪只查版本與路徑，未用它推導行為。
- 下文分開標示 code fact、prompt fact、推論與本案映射。官方 scripted test 只作資料流佐證；**本輪沒有執行測試，也沒有測量模型矛盾辨識成功率**。

## 2. 同一對話：詳記可重新產生，不是只累積新副本

### 2.1 Codex 寫入鏈

**Official code fact：**

1. 背景 startup pipeline 選符合來源、年齡、閒置、數量與工作租約等條件的 rollout，不是所有新訊息立即觸發。[管線說明][C1]
2. 以 `source_updated_at`／成功 watermark 判斷是否已跟上來源；來源沒變新就跳過，變新後仍須通過其他工作條件。[申領檢查][C2]
3. Phase1 從該 rollout 載入、過濾 response items，送模型重新產生候選、詳記、slug；這條呼叫沒有把既有 summary 當必填輸入再做逐段 patch。[抽取呼叫][C3]
4. 以 `thread_id` upsert Stage1；新來源時間不早於已存結果時，替換該列 `raw_memory`、`rollout_summary`、slug。這是**同一 thread 的現行抽取結果**，不是每輪增加一個 canonical Stage1。[資料庫更新][C4]
5. Phase2 從選定 Stage1 同步 `.md` 詳記，加入 thread／來源時間／原文位置等 header，清理不在保留集合的詳記。slug 改變時檔名可能改變，不能承諾舊路徑永久有效。[同步與清理][C5]

**Inference／示意，非實測輸出：**同一對話先說「A 網站由我做前後端」，後來明確更正「後端由同事做，我只做前端」。兩段都進入下次抽取輸入時，新詳記有機會交代前後更正，取代舊抽取結果；不是一定保留兩份互斥的現行詳記。模型是否整理正確仍非 DB 可保證。

### 2.2 Python Sandbox Memory 交叉核對

**Official code fact：**同 rollout identity 的多個 run segment 追加到同一 JSONL；sandbox session 關閉時，manager 才對累積 rollout 抽取並最後整併。官方測試以兩次 run 證明：同一原文檔有兩筆 segment，close 前未抽取，抽取輸入包含兩次內容。**兩輪聊天不必產生兩份詳記。**[manager][S1]、[原文追加][S2]、[官方測試][S3]

保存時候選是 `raw_memories/<rollout_id>.md`，詳記是 `<rollout_id>_<slug>.md`。相同路徑可更新，但 slug 改變可能留下另一檔名；這個 manager 沒有 Codex 相同的同步 prune。整併 prompt 另有「同 rollout 重複詳記可保留較佳者」的可選整理。[保存接線][S1]、[可選清理][S4]

不能混成同一實作：Codex 是資格篩選＋DB Stage1 的 startup pipeline；Sandbox 是 session close pipeline。共同可學的是**詳記是衍生抽取結果，保存粒度不等同聊天輪數**，不是觸發時間或 DB 相同。

### 2.3 重抽也有限制

Codex 抽取輸入超預算會保留頭尾，預算由模型有效 context 計算；Python Sandbox 這條路徑有 150,000-token 文字上限與截斷提示。不能推論「同一無限長 thread 每次重抽，就能完整修正全部案例細節」。[Codex input][C6]、[SDK input][S5]

因此不能只因會替換，就擅自讓 Caliburn 每次重抽全部歷史；成本與中段遺漏仍需面對。原文留著不等於本次抽取模型全部讀過。

## 3. 不同詳記談同一案例：比對與修訂在哪裡發生

**Official prompt fact：**詳記要保留結論怎麼形成、使用者修正、是否已確認；可以比 durable Memory 詳細，也可保留未採用提議，但不得把未定討論寫成已確認事實。[詳記內容規則][S6]

Codex 整併模型拿到新增／修改輸入與既有正文，先定位受影響主題；重要、模糊、重複、矛盾時再開相關詳記。要求包括：

- 更新過時或相反指引，不是無區別並列兩種說法。
- 同時看 `updated_at` 與證據是否經核實；較新的**已核實**證據通常優先，不是最後一句無條件勝出。
- 無法確認矛盾時，明確保留不確定。
- 正文保留主題相關詳記引用與時間，依新鮮度、用途排序；導覽最後跟著更新。[輸入與增量規則][C7]、[引用／矛盾規則][C8]、[更新工作流][C9]

**詳記本身：**有可選 housekeeping，可清理重複／低訊號詳記，同 thread 有重疊詳記可保留較佳者；沒有找到必須「把新更正回寫每份舊詳記」的流程，也沒有按業務案例 identity 傳播修正的 Runtime 證據。[詳記整理條款][C10]

這不是說模型技術上完全不能改詳記，而是**不能把寫檔能力、可選清理或正文整併，當成全面修正詳記的保證**。Codex 下次同步仍以 DB Stage1 為來源，也不能只憑某次直接改 `.md` 推論已永久修復 producer。[同步來源][C5]

## 4. 回查舊詳記與 live update：仍有界線

**Official prompt fact：**quick pass 是小導覽 → 搜正文 → 沿正文引用讀少量相關詳記，不是跳過現況正文隨機開舊檔。提示詞要求判斷 drift risk、適當核實；未核實的舊記憶不得冒充確認過的現況。[Codex reader][C11]、[SDK reader][S7]

**Inference：**正文若已寫入 A 案例更正並引用後續詳記，模型可先看到更正，再讀歷史脈絡。但若更正未進正文／引用、尚未整併、檢索漏選，或模型只開舊詳記，公開流程不能保證它知道後續更正。尤其「只變案例細節、沒變共同工作模式」，不能只回答正文會修正。

**Official prompt fact：**Python Sandbox `live_update` 是核實當前證據後，同輪修正 `MEMORY.md` 過時指引；不是重跑 Phase1，也沒要求同步改所有 `rollout_summaries`。[live update 指示][S8]

本次 Codex read prompt 另寫「使用者要求更新時新增 ad-hoc note，不直接改 Memory 檔」；與 Sandbox live-update capability 不同，不能把一條當成所有 OpenAI 產品的同輪修補模式。[Codex 更新指示][C12]。此差異已界定，不在本題另外翻案 C 分工。

## 5. 本案影響：指出缺口，不偷偷選新機制

**Caliburn mapping：**Q019 按訪談視窗抽取不可變詳記，以有界分段避免中段來源永遠沒機會被抽取；不等同 Codex 每 thread 一份現行 Stage1。即使只有一個聊天室，跨視窗更正仍可能分散到多份詳記。

- 已成立的目的：原文保留、詳記／正文可回查、正文可修訂。
- 尚未被證明的效果：只讀早期 A 詳記時，如何取得後續已知更正，且不把所有案例細節塞進正文。
- **實體封存不等於邏輯不能更新：**舊 artifact 不原地覆寫，仍可透過新版本呈現更新後詳記；不等於目前已做了詳記版本路由。本稿沒有核准新增它。
- 沒有理由宣稱每份詳記都必須永久保留，也不能因 OpenAI 可清理就替本案刪資料；完整細節可回查的需求沒有撤回。

**研究建議，非施工決定：**先解除「OpenAI 規定詳記不能更新」的錯誤依據；下一題只比較詳記現行內容／引用如何承接更正。以已查明的重抽更新、整併引用作基準，不直接添案例資料庫，也不宣稱改 prompt 就必然解決。改保存／讀取行為前，先讓 Owner 審核效果、成本與限制。

### 5.1 Owner 後續方向：可直接模仿 OpenAI，具體接法待定

**2026-09-06 Owner：**「那我們可以多加學習參考 openai 的方式去做」，並補充「可以模仿 openai 作法」。方向 WORKING：可直接仿照已公開、查證的流程與細節，不必為保留現有 mapping 另外發明機制。先以原廠具體 producer／consumer 為基準；只有需求、成本或框架承接有明確差異時，才提出有理由的調整。不把尚未查到的能力冒稱原廠做法；具體保存與回查變更仍待設計確認。

沿本稿已核實來源，接下來應比較以下接法，而非重新研究所有 Memory：

| 接法方向 | 可學的官方依據與優勢 | 尚須處理的問題 |
|---|---|---|
| **推薦優先評估：詳記也有可重建的現行內容** | Codex 同 thread 的 Stage1 可替換、詳記可重新同步；原文仍保留。更正可以反映在詳記，不完全依賴正文解釋舊錯誤。[抽取][C3]、[更新][C4]、[同步][C5] | 不代表按案例一份、不代表全訪談每次重抽。單一長訪談的分段、更正跨段、更新後引用定位與模型成本仍待設計；不能先聲稱跨段問題已解決。 |
| **保持詳記為歷史記錄，以正文與引用交代更正** | 學習整併模型比對新舊證據與維護引用，保存端較少改動。[增量規則][C7]、[引用][C8]、[工作流][C9] | 對只改案例細節、沒進正文的情境仍有漏讀風險；不能直接當成已滿足 Owner 需求。 |

兩列是 **Caliburn 候選映射**，不是兩個原廠配置開關。推薦第一列是因其直接處理「詳記本身過時」，不是已證明性能最好或核准施工。若沿第二列可用官方現成能力達到相同效果，也應比較，不被現有程式綁死。

共同學習重點：原文與衍生詳記分開；整併時處理更正、未知和引用；讀取先走目前正文再按需深入。後兩者由 OpenAI Docs 的分層說明與本稿 source 支持，但沒有保證每次語意判斷正確。[公開說明][O0]、[整併][C8]、[讀取][C11]

**本輪 closure 補充：**已記錄 Owner 學習方向及兩個待比較候選；具體接法仍 OPEN。下一步只處理「詳記按什麼範圍更新，以及更新後怎麼找到正確內容」的效果、成本、公開框架承接；不先加案例 CRUD 或自訂更正傳播系統。

## 6. Closure

- **Finding：**補齊同 thread 重抽替換、跨 rollout 整併／可選詳記清理、read-time stale 核實與 live update 範圍；沒有證據支持「所有舊詳記自動同步更正」。
- **Status：**G2 evidence complete；本案接法 OPEN，不是模型品質驗證或 G7。
- **Why：**Owner 指出跨批次同案例矛盾；只說正文可修訂不足以回答詳記本身。
- **Sources：**§1 固定版本；重要結論旁引用 producer／DB／consumer／官方測試。
- **Affected：**本稿、摘要路由 §2.4、Q019 Memory 問題路由與 current register；只更新研究及 OPEN 提醒。
- **Reopen：**相關官方契約／producer-consumer 改變，或找到跨摘要更正傳播的直接證據；不重做所有 Memory 研究。
- **Next gate：**與 Owner 確認詳記更正／回查接法；Task3/API/UI 仍未啟動。

[O0]: https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs
[C1]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/README.md#L40-L77
[C2]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/state/src/runtime/memories.rs#L662-L727
[C3]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/src/phase1.rs#L228-L325
[C4]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/state/src/runtime/memories.rs#L853-L942
[C5]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/src/storage.rs#L22-L135
[C6]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/src/prompts.rs#L98-L126
[C7]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/templates/memories/consolidation.md#L119-L177
[C8]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/templates/memories/consolidation.md#L306-L351
[C9]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/templates/memories/consolidation.md#L782-L840
[C10]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/templates/memories/consolidation.md#L848-L850
[C11]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/ext/memories/templates/memories/read_path.md#L33-L73
[C12]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/ext/memories/templates/memories/read_path.md#L117-L123
[S1]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/manager.py#L89-L238
[S2]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/rollouts.py#L105-L152
[S3]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/tests/sandbox/test_memory.py#L1369-L1446
[S4]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts/memory_consolidation_prompt.md#L787-L789
[S5]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/phase_one.py#L19-L83
[S6]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts/rollout_extraction_prompt.md#L251-L291
[S7]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts/memory_read_prompt.md#L21-L65
[S8]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts.py#L35-L68
