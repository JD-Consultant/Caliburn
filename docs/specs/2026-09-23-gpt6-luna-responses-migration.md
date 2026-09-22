# GPT-6 Luna／OpenRouter Responses 最小遷移設計

- 日期：2026-09-23
- Topic：正式新 JD App 的 A／B1／B2 模型傳輸
- Stage：Owner 已選遷移方向；本稿是施工前審核，**尚未切換 production、尚未送付費請求**
- 現行狀態與後續結果以 [`current-decisions.md`](../current-decisions.md) 為準；既有 `docs/specs/2026-09-17-openrouter-role-model-factory.md` 與 `docs/specs/2026-09-16-openrouter-continuation-compaction-design.md` 保留當時設計及驗收歷史。

## 目的與不變量

Owner 選擇 GPT-6 Luna，並要求 A／B1／B2 繼續有推理及 App 工具能力。仍用**單一 OpenRouter key、OpenAI-only route、禁止 fallback**；A／B1／B2、顧問 Prompt／Skills、Working State、Memory、JD Domain／receipt、PostgreSQL Saver／Store 與 App-side continuation compaction 的權責不變。Responses 是替換模型**傳輸格式**，不是改用 OpenAI 直連 credential，也不是重開原生 compaction 或第二套 Memory。

## 已核對的事實與限制

1. [OpenAI GPT-6 Luna 模型頁](https://developers.openai.com/api/docs/models/gpt-6-luna)（查閱 2026-09-23）列出 `reasoning.effort=high` 與 Responses 工具呼叫；Chat Completions 的函式呼叫僅在 `reasoning_effort=none` 支援。因此不能在正式 `ChatOpenRouter` 上只替換 model slug，仍宣稱原有 `high＋JD／Memory tools` 成立。
2. [OpenRouter Responses API](https://openrouter.ai/docs/api/api-reference/responses/create-responses)（查閱 2026-09-23）有 `/api/v1/responses`、`reasoning`、`tools`、`provider`、`store` 等公開欄位；這是 API 契約，不是 Caliburn 的 GPT-6 Luna＋OpenAI provider＋high＋工具服務端實測。先前 OpenRouter／GPT-5.6 inline **native compaction** 未產生 item 的結果只約束 native compaction，不推論本次一般 Responses 工具呼叫必然失敗或通過。
3. 鎖定的 `langchain-openai==1.6.2` 已有 `ChatOpenAI(use_responses_api=True, output_version="responses/v1", store=False)` 客戶端接縫；`tests/test_compaction_adapter_contract.py` 的離線正向候選以 `base_url` 指向 OpenRouter，實際經過 request serialization、工具配對及 Saver 往返，2026-09-23 重跑 **4 passed**。固定 `MockTransport` 只能證明客戶端，不能當成服務端相容證據。
4. 現行 `openrouter_model.py` 是 Chat Completions 的 `ReceiptChatOpenRouter`，除請求與回覆轉換外還負責 route／status 證據及固定 prompt cache breakpoint。`consultant_context.py` 的 A 組裝明確檢查該類型及 route；`role_models.py` 把同一正式模型注入 A／B1／B2。因此不可能只改一個常數就安全完成。
5. [OpenRouter Prompt Caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching)（查閱 2026-09-23）說明 Responses 不暴露 `input` item 內的逐 block cache breakpoint；既有 Chat request-only `cache_control` 不能直接照搬。先沿供應商支援的自動／隱式快取，不為遷移建立 cache service 或改變動態 JD／Memory context 順序。
6. [OpenAI reasoning 指南](https://developers.openai.com/api/docs/guides/reasoning)（查閱 2026-09-23）把 reasoning item 視為可延續的 opaque context；`reasoning.context=all_turns` 的文字說明與範例目前明確提及 GPT-5.6，不能自行假定 GPT-6／OpenRouter 在本路徑完全相同。先保持 App-side summary 與近期工具配對，單獨驗證是否取得、保存及重送 GPT-6 可用的 encrypted reasoning；不把 opaque reasoning 當產品 Memory 或來源。

## 最小施工候選

| 接點 | 最小變更 | 不變 |
|---|---|---|
| 模型傳輸 | 在現有正式 role-model factory 的邊界，使用 OpenRouter `base_url` 的 Responses 客戶端；明確 `openai/gpt-6-luna`、high、`store=false`、單次工具呼叫、零隱藏重試、OpenAI-only／no fallback、既有 A／B1／B2 輸出及 timeout profile。只在鎖定客戶端確實丟失必要 route／terminal 證據時補窄 adapter。 | 單一 credential、三角色的 Agent graph／工具、Runtime scope 與保存權責 |
| A 組裝 guard | 讓原本只接受 `ReceiptChatOpenRouter` 的正式檢查辨識**已驗證的 Responses profile**；仍拒絕不明模型、server-side conversation、偷偷重試或平行工具。 | 64／63 額度、安全收尾、JD notice／tool middleware |
| 上下文與恢復 | 沿用現有 `ContinuationCompactionMiddleware`、canonical Saver 與 request-only view；近期 Responses reasoning／function items 能否跨工具與重開往返，用既有 client 契約擴成正式組裝回歸。舊 Chat checkpoint 只在 request view 做受控兼容評估，不改寫原始對話或偷偷宣稱舊 opaque reasoning 可跨模型家族沿用。 | A／B1／B2 的摘要選材、Memory／來源、C 與 publication 規則 |
| P3 有界 trial | **沿用同一 test-only ledger／HTTP gate**，更新 endpoint、Responses wire 驗證、GPT-6 價格與最壞費用預留，核對 Responses 回應的實際 provider／model／tier／cost 可否被同一帳本可靠讀取；維持已核准的 12 員工 POST、180 真外送與 US$1.00 上限。 | 不增 production 計費系統、重試、fallback、第二套 receipt |

舊 `openai/gpt-5.6-luna`／Chat 接法及既有證據在新路徑通過前保持原狀。正式切換時不長期雙跑兩套 provider runtime；歷史研究與測試保留。若舊 checkpoint 的 provider-specific item 不能在新 request 安全使用，先提出具體反例與最小投影方案，**不刪原話、不重做已提交的 JD 操作**。

## 依序驗收及停止線

1. **零付費 wire：**對正式 A／B1／B2 組裝抓實際 `/api/v1/responses` body；核對 high＋function tools、`store=false`、route、非串流、輸出額度、無 fallback／隱藏重試；工具 call ID／output、strict schema、拒絕／截斷／final 分類及必要的 opaque item 往返。若客戶端無法無損表達，先停在 transport 層，不碰 Domain。
2. **零付費整合：**同一 App 的 A tool loop、B1／B2 background、真 PostgreSQL Saver／Store、重開續作、App-side compaction 與舊 checkpoint 邊界受影響回歸。已完成的 5.6 Luna 品質證據保留但不冒充 GPT-6 驗收。
3. **P3 費用閘門：**以 GPT-6 正式價格及 Responses 實際回應形狀重算／測試完整保守預留。若 `usage.cost`／provider 等必要事實不能在同一 HTTP response 確認，或路由有不能鎖住的隱性切換，**不得沿舊閘門送付費試驗**；先回報取捨，不把未知費用當零。
4. **有界服務端 smoke → 自然 trial → Browser：**只在前三關成立後，用同一已核准上限先驗 GPT-6 Luna／Responses／OpenAI provider 的高推理工具往返及 final，再做自然 C-W 訪談和真 Browser JD／來源／撤回／重開驗收。任何 4xx、截斷、工具不配對、錯 provider／tier、費用不明立即停止；不降成 `reasoning=none`、不切 direct OpenAI key、不自動回退 5.6，也不借 native compaction 測試製造假通過。

**判斷：**這應是單一 App 的**有限傳輸遷移**，不是重做產品架構；但它涉及模型組裝 guard、Responses item／route 證據、快取與 P3 支出閘門，不能按「只改模型名」估工或驗收。正式 diff 及付費測試必須以各 gate 的結果為準。
