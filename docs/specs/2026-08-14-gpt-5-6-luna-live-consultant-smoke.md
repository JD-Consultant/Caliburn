# GPT-5.6 Luna 真實 API 顧問訪談 smoke 與修復紀錄

- 日期：2026-08-14
- 狀態：**進行中**。第一輪真實 API、員工校準與文件審核已完成；第二輪具體事件已實際送出並暴露兩個 wire mapping 缺口，程式與回歸測試已修正。相同輸入的最終付費重跑仍待重新注入暫存 OpenRouter key。
- 性質：付費 smoke／contract conformance／產品流程驗證，**不是正式品質 eval**。依 owner 決定，正式 eval 延至產品核心完成後。
- 範圍：current 顧問 runtime；不接 RAG／Reference，不生成能力級別或 A。

## 1. 本輪要回答什麼

這輪不是要證明模型「品質已達 production」，而是用真實 provider 回答下列窄問題：

1. LangChain／LangGraph runtime 能否真的經 OpenRouter 呼叫 GPT-5.6 Luna，並留下 requested／actual route、usage、cost 與 latency 證據。
2. 同一位顧問能否從員工完整描述建立暫定工作地圖、選出明確焦點、保留 Gap，並提出至多一個主要問題。
3. 模型建議是否只進入待審變更；員工接受、修改後接受、拒絕之前，核准文件是否完全不變。
4. 第二輪能否記得前一輪員工原話與已核准文件，沿既有焦點深入，而不是重新開始。
5. Task／Duty／O／P／K／S Skills 是否按證據組合使用；證據不足時能否不硬填 OPKS。

## 2. 官方依據與 profile 判斷

OpenAI 的 GPT-5.6 model guidance 說明：Luna 是成本敏感、高流量 tier；`reasoning.effort` 支援 `none／low／medium／high／xhigh／max`。官方建議以 `medium` 作平衡起點，把 `max` 留給最難、品質優先的工作，並在代表性工作負載上比較品質、延遲與成本，而不是假定最高 effort 一定最好。

OpenRouter 預設不回傳實際路由細節；正式介面是送出 `X-OpenRouter-Metadata: enabled`，再從 `openrouter_metadata.endpoints.available[]` 找出 `selected=true` 的 provider／model。固定 provider 時同時使用 provider allowlist 並停用 fallback。

本輪 profile：

| 項目 | 設定 |
|---|---|
| requested model | `openai/gpt-5.6-luna` |
| provider | `OpenAI` only |
| fallback | disabled |
| structured output | provider-native Pydantic／JSON Schema |
| 互動候選 | `reasoning_effort=medium`、`max_output_tokens=8192` |
| 深度候選 | `max` 保留給日後有代表性品質比較的非即時工作 |

單次診斷結果不能當成模型選型 eval，但足以排除不適合互動訪談的配置：

| effort／output budget | 實測觀察 |
|---|---|
| max／4096 | output budget 全部耗在 reasoning，沒有可提交 final output |
| max／16384 | 第二次 model call 用滿 16384 output tokens，其中 15902 reasoning；約 113 秒，`finish_reason=length`，成本約 USD 0.01030 |
| high／8192 | 第二次 model call 用滿 8192 reasoning tokens；約 72 秒，`finish_reason=length`，成本約 USD 0.00578 |
| medium／8192 | 完成 provider-native structured final；兩次 call 約 4.8＋31.3 秒，總成本約 USD 0.00450 |

另一個完整 medium 診斷文件成功 run 的總 wall time 約 32.1 秒、總成本 USD 0.00340079，實際 selected provider 為 OpenAI。結論只限於本 smoke：**medium／8192 是目前較可靠的互動基線；max 並未帶來可用 final output。**

## 3. 測試訪談腳本

以下都是合成測試內容，不是真實員工資料。

### 3.1 第一輪：工作範圍盤點

> 我是電子製造公司的採購專員。平常收到研發或生產的採購需求後，我會先確認品項規格、數量與交期，向三到五家供應商詢價，比較價格、付款條件和交期，必要時議價，再在 ERP 建採購單並追蹤到料。供應商延遲時，我會先確認原因、找替代交期或替代料，再把風險通知需求單位。最終驗收由品保負責，我只追蹤到貨與缺件。每月底我也整理未結採購單和交期異常清單給主管。

### 3.2 理解校準

> 以上工作範圍與責任邊界理解正確；最終驗收確實由品保負責。

### 3.3 第二輪：沿既有焦點深入具體事件

> 最近一批控制板連接器，供應商因上游缺料通知無法按原交期交貨。我先查 ERP 的現有庫存與生產需求日，請原供應商評估提前部分交貨，也同步詢問另一家合格供應商的可供日期與價格。若要改用替代料，我只能整理規格差異與風險交給研發確認；若價格或緊急採購條件改變，需由主管核准。我把可選方案、缺料風險與預估交期通知需求單位，依他們確認的方案更新 ERP 交期並持續追蹤。對我而言，需求單位已確認處理方案、ERP 已更新，而且材料到貨、缺件解除，就算我的追蹤工作完成；到貨後的最終驗收仍由品保負責。

第二輪刻意涵蓋本人判斷、研發／主管／需求單位／品保責任、可觀察完成標準與 OPKS 線索，用來驗證記憶、Focus 延續、Task 邊界與 OPKS linkage。

## 4. 第一輪實際結果

### 4.1 顧問行為

- 沒有把訪談做成固定 wizard；先整理工作範圍，再把「供應商延遲或替代料的具體案例」選為當前焦點。
- 明確保留「最終驗收由品保負責」的責任邊界。
- 建立五個 Task 候選、三個 Duty 候選、職稱與工作描述的待審變更。
- 因完成標準與 K／S 證據不足，白話說明本輪先不建立 OPKS，而不是為填表補造內容。
- 問題聚焦一個具體案例：發生什麼、本人做了哪些關鍵判斷、如何知道事情已解決。
- 本次 sample 載入九個方法 Skill；這代表模型認為完整初始盤點同時需要 work discovery、story、Task／Duty、O／P／K／S 與 completion red-team，不代表每輪固定載入九個。

### 4.2 員工 authority 驗證

第一輪產生 10 個待審 action。模擬員工執行：

- 拒絕 1 個過早建立、較像 Task 的 Duty；拒絕後核准文件未出現該 Duty。
- 把「延遲處理」Task 修改得更清楚後接受：

  > 協調供應商延遲處理，確認原因與可行替代交期或替代料，並將風險通知需求單位。

- 接受其餘 8 個 action。

結果是 `accepted=8／edit_accepted=1／rejected=1／pending=0`。正式文件最後有職稱、工作描述、2 個 Duty 與 5 個 Task；Task 暫時未歸 Duty，因此 readiness 明確顯示 `TASK_DUTY_MISSING`，但資料沒有被偷偷補配。

這證明模型輸出只是可審草稿；員工 decision command 才進入唯一核准文件 authority。

## 5. 實測發現與修復

| 發現 | 根因 | 修復 | 驗證 |
|---|---|---|---|
| provider 拒絕原始 Pydantic schema | `$ref` sibling description 等 shape 不符合實際 strict structured-output 接受面 | 由 LangChain／Pydantic schema 轉換流程正規化後再交 ProviderStrategy | focused schema tests＋真實 provider 已接受 |
| 模型編造 UUID、假 quote offset、混用 question sentinel、一次 ADD 多實體 | rich application contract 直接暴露給 provider 時認知負擔過高 | compact required-only wire、短明確契約、deterministic verifier；新 ID／排序由 application 配置；一個 ADD 一個實體 | mapper／verification tests＋第一輪 live success |
| `job_title` 用 ADD／whole entity、集合 ADD 用 value 等無歧義別名 | strict enum 仍有可組合但語意唯一的表達 | pure mapper 只 canonicalize 可判定的 top-level／collection alias；有歧義仍 fail closed | 新增回歸測試，29 mapper tests 全綠 |
| 回應原本無法證明實際 provider | OpenRouter metadata 預設關閉 | 送官方 `X-OpenRouter-Metadata: enabled`；permissive decode，取 selected endpoint；缺 route fail closed | live receipt 顯示 selected OpenAI |
| 同來源多個 ADD target key 碰撞；Duty／Task 共用全域排序 | target key 缺 payload identity；排序 allocator 未按 collection 分區 | canonical payload hash 加入 ADD target key；Duty／Task／各 OPKS axis 使用 collection-local order | 第一輪重跑後 Duty 0..2、Task 0..4 且 target key 唯一 |
| 新 OPKS 的 `display_order=-1` 被當非法最終值 | mapper 沒辨識 application-owned OPKS ADD sentinel | 單一 OPKS ADD 先映成文字，由 document-review seam 配置該 OPKS axis 的順序與 stable ID | mapper 回歸測試全綠 |
| OPKS item-level linkage 與 change-level linkage 不同而失敗 | strict flat wire 為 MERGE／SPLIT replacement 保留 item linkage slot；單一 ADD 又重複表達 linkage，形成假雙權威 | 單一 ADD 明定 change-level linkage 是唯一權威；item slot 只作 strict-schema 占位並被忽略；MERGE／SPLIT 仍逐 replacement 驗證 | 先紅後綠；146 consultant tests passed、26 skipped |
| API 重啟後先連到未遷移預設 DB | 重啟命令漏帶 disposable DB URL | 重啟時明確帶 `caliburn_reviewed` URL；未發出模型請求、未改產品 code | snapshot 再次可讀 |
| 再次重啟後缺 OpenRouter key | key 只在已停止行程的暫時 environment，repo／`.env`／User env 均未保存 | 不從 log 或 shell history挖取憑證；等待 owner 重新注入後，重送同 run／同 source | **待完成** |

安全原則：production failure log 只留安全 error type，不記原始 provider／mapper detail；診斷 detail 只在本機暫時加入，定位後已撤回。

## 6. 第二輪目前狀態

- 第二輪 immutable employee source 已保存；失敗 run 沒有建立待審變更，也沒有改動第一輪核准文件。
- 模型已實際跑到 OPKS mapping，證明它沒有只重做第一輪工作盤點；但在修正後的相同輸入 live retry 尚未完成前，不能宣稱「兩輪記憶與 OPKS 效果已通過」。
- 最終重跑必須檢查：
  1. 顧問是否沿「供應商延遲／替代料案例」深化，而非重新起頭。
  2. 是否引用既有延遲處理 Task `c1dcd779-9153-54c5-93a7-7e16f7f9ccc3`。
  3. O／P 是否各自只連一個 Task；K／S 是否有有效員工 quote anchor。
  4. 待審內容在員工決定前是否完全不進核准文件。
  5. response 是否只問一個下一步問題，Gap／Focus／Progress 是否隨新證據重算。

## 7. Disposable evidence IDs

這些 ID 只供本機追蹤，測試完成後會刪除整份 disposable 文件：

- 最終兩輪文件：`f12e8784-2b40-50ac-9a56-2899d380cd74`
- 第一輪 run：`569637b4-738a-516e-9265-7f2a188cb6cc`
- 第二輪 run：`4478d28f-60b2-50a4-b243-131bd5345f84`
- 第二輪 source：`84a72874-2cd9-5dbc-ba71-a4cccc13a08d`
- 完整 medium 診斷文件：`69f5ee68-879b-5983-a25c-1a2ac8269f5e`
- 完整 medium 診斷 run：`a43e3595-770b-51ba-a951-0c5d54171f6c`

另有失敗診斷文件 `8ce7c5b6-7ebe-591f-a3fe-6c48e19efc70`、`db8d80c9-3302-51c3-83f5-db477df3098c`。只刪這些明列 ID，不清理其他使用者文件。

## 8. 重跑與收尾條件

1. 由 owner 在目前測試 shell 或未追蹤的本機 `.env` 注入 `OPENROUTER_API_KEY`；不得寫入 Git。
2. 用 `DEBUG=false` 與 disposable `caliburn_reviewed` DB 重啟 `run_live.py`。
3. 對第二輪既有 failed run 呼叫 retry；不得新增一份內容相同的 employee source。
4. 檢查第 6 節五個條件，並對第二輪待審變更至少各走一次合適的 accept／edit-accept／reject（若輸出品質確實需要）。
5. 更新本報告為最終結果；刪除第 7 節明列的 disposable 文件與本機 `.live-final-*.log`。
6. 跑 consultant tests、API／Web／contract／monorepo final gates；不把本 smoke 當正式 eval。

## 9. 第一方來源

- [OpenAI Model guidance：GPT-5.6 family、reasoning effort 與 profile 選擇](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI GPT-5.6 Luna model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- [OpenRouter Router Metadata](https://openrouter.ai/docs/guides/features/router-metadata)
- [OpenRouter Provider Routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter Reasoning Tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
