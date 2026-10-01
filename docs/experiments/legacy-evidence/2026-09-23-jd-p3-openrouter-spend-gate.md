# P3 OpenRouter／Luna 零付費支出閘門驗證

日期：2026-09-23
狀態：**零付費 gate PASS；P3 自然 trial 尚未授權、尚未執行。**

> 後續狀態見[P3 測試入口與隔離 PG 預檢](2026-09-23-jd-p3-trial-entry-offline.md)。下方 §5 保留本閘門完成當時的待辦，不應反推後續接線仍不存在；自然真模型與真 Browser 仍未執行。

## 1. 這次關閉的是什麼

P3 的單一 C-W 自然縱切仍採既定三個上限：最多 12 個員工回合、180 次 provider request、US$1.00。這次只關閉其中 provider request 與美元 admission 的離線技術前置，不執行模型、不讀 credential、不改 production runtime，也不把測試 helper 變成第二套產品 budget 系統。

2026-09-10 的[舊前置研究](../../specs/2026-09-10-jd-natural-trial-budget-preflight.md)描述已退役的 OpenAI Responses／native compaction runtime，作為迭代歷史保留。依 [ADR0077](../../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)，本次實際適用範圍改為唯一正式新 App 的 OpenRouter Chat Completions、OpenAI-only Luna、A／B1／B2 共用 transport，以及 App-side continuation compaction；不沿用舊 binding 的 request 欄位或計費假設。

## 2. 官方事實與本案取捨

查閱日均為 2026-09-23：

- [OpenAI GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)列出 1,050,000 context 與 128,000 最大輸出；[OpenAI pricing](https://developers.openai.com/api/docs/pricing)列出 Standard／長 context input、cached input、cache write 與 output 計價。這是費率與容量事實，不代表每次請求實際會用滿。
- [OpenRouter Luna](https://openrouter.ai/openai/gpt-5.6-luna)列出 Standard OpenAI route；[service tiers](https://openrouter.ai/docs/guides/features/service-tiers)說明 Flex／Fast 必須明示請求，實際 tier 應由回應證據確認。Caliburn P3 不請求 tier，且只接受回應 `default` 或未回傳 tier。
- [OpenRouter Chat Completions](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion)與[usage accounting](https://openrouter.ai/docs/guides/best-practices/prompt-caching)提供 response usage／cost。Caliburn 仍不把本地字元或 token 估算冒稱 provider 帳單；成功回應必須取得實際 `usage.cost` 才能釋放預留。

同日再次唯讀核對[OpenAI Luna 模型頁](https://developers.openai.com/api/docs/models/gpt-5.6-luna)與[OpenRouter 的 Luna 版本頁](https://openrouter.ai/openai/gpt-5.6-luna-20260709)：兩者仍列 1,050,000 context、US$0.20／1M input、US$1.20／1M output；OpenAI 仍列超過 272K input 時整次 input 2 倍、output 1.5 倍，cache write 為未快取 input 的 1.25 倍。[OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)仍有 `only` 與 `allow_fallbacks` 限制。這支持下述**目前鎖定路徑**的 US$0.50／US$1.80 預留推導，並非供應商未來價格保證；正式付費送出當日仍需重查，實際費用仍以回應 `usage.cost` 為準。未送任何 provider request。

Caliburn 的保守映射是：每次送出前不猜實際 prompt token，而是按該角色可能的完整上限預留。Standard 長 context cache-write 上界採 US$0.50／1M input，長 context output 採 US$1.80／1M：

```text
A：1,050,000 × 0.50 / 1M + 8,192 × 1.80 / 1M
 = US$0.5397456

B1／B2：1,050,000 × 0.50 / 1M + 32,768 × 1.80 / 1M
 = US$0.5839824
```

這比實際短 request 成本保守，但能在沒有 Chat Completions 精確 preflight tokenizer 的情況下，對目前鎖定 model／route／context／output contract 建立送出前上界。若 provider 費率、context、模型、tier或輸出上限改變，這個推導立即失效，必須先停下重算，不能沿用舊數字。

## 3. 實作界線

測試支援位於：

- `experiments/jd-relational-app/tests/support/p3_spend_gate.py`
- `experiments/jd-relational-app/tests/test_p3_spend_gate.py`

它只包住 P3 執行者交給正式 A／B1／B2 model factory 的 caller-owned sync／async HTTP clients：

1. 驗證 endpoint、`openai/gpt-5.6-luna`、OpenAI-only provider、無 fallback、`high`、A 8192 或 B1／B2 32768、`parallel_tool_calls=false`、metadata header，並拒絕 Flex／Fast、plugins、web search、streaming 及其他模型。
2. 全批共用同一 durable ledger 與鎖；一次最多一個 provider request 在途。這是 P3 驗收的保守執行限制，不改 production 的正常背景並行設計。
3. 在 network 前先持久化 attempt、request 名額與完整最壞費用 reserve；`已結算 + 未知保留 + 下一次 reserve > US$1.00` 或即將超過 180 次時拒絕送出。
4. HTTP 200 後只在 actual model、provider、service tier 與 `usage.cost` 都可核對時，以實際 cost 結算並釋放 reserve。
5. timeout、transport error、非 200、invalid／missing cost、route/tier/model mismatch、帳本寫入失敗或程序在 request 未結算時重開，全部 fail closed；reserve 留作未知支出，後續 request 停止，不能把未知當 0。
6. ledger 只保存 trial、attempt、model、max output、reserve、actual cost 與 outcome；不保存 prompt、工具內容、credential、header 或 reasoning。

**2026-09-23 successor：**後續 P3 入口審核發現 httpx 可逐次覆寫 constructor 的 `follow_redirects=False`。同步／非同步先紅後綠；test-only guarded clients 現在於外送前拒絕明示 `follow_redirects=True`，其餘一律強制不跟隨，防止單一 admission 隱含多筆 provider request。受影響集合含隔離 PostgreSQL **59 passed**；首次反例與限制見[P3 測試入口](2026-09-23-jd-p3-trial-entry-offline.md#2026-09-23-p3-逐次外送的重新導向覆寫邊界)。正式產品 client 不變，P3 仍未授權、未執行。

正式 Domain、Runtime、Memory、Working State、receipt、provider factory與 retry policy沒有修改。OpenRouter SDK retry 仍是既有 `0`；httpx 使用預設不重試 transport。未新增 service、DB table、queue、Agent、通用 provider abstraction 或 production budget authority。

## 4. 離線證據

執行：

```text
uv run --frozen pytest tests/test_p3_spend_gate.py -q -p no:cacheprovider
```

結果：**26 passed／0 failed；0 provider request／US$0。**

覆蓋：

- A 與 B1／B2 的完整 reservation 算式；
- request contract 在 network 前拒絕；
- sync／async client 共用單一 gate；
- 第二個並行 request 必須等第一個完成；
- 180 request 與 US$1 cap；
- missing／invalid cost、非 200、錯 provider／model／tier；
- transport unknown 與未結算重開；
- duplicate response 不重複扣款或釋放；
- ledger 寫入失敗立即停止；
- 未授權狀態拒絕；
- 真正的 production `create_role_models` 所組 A／B1／B2 serialized wire 全部通過同一 gate，實際觀察 output limits 為 8192／32768／32768。

一般 Windows sandbox 無法讀取 pytest 自建暫存 ACL；同一命令只把 `--basetemp` 指向 repo 內隔離路徑並在允許建立／讀取該目錄的受控環境重跑。沒有為此修改測試語意或 production。

## 5. 尚未關閉的 gate

本結果**不等於 P3 READY 或 PASS**。仍須：

1. 以可提交的 exact revision 凍結 commit、Python／pnpm locks、Prompt、Skills、tool schema、C-W package hashes及正式模型設定；目前工作樹仍有待整合修改，不能把 HEAD 冒稱實際待測內容。
2. 把既有 C-W 自然操作者接到正式 App browser／HTTP 入口，另在 test driver 計最多 12 個實際員工聊天回合；這不是 spend gate 的責任。
3. 離線證明該 driver 建立的所有 A／B1／B2 clients 都是上述 guarded clients，且 close／restart 後不會以普通啟動繞過同一 trial ledger。
4. 建立逐輪／逐 request／JD receipt／Memory publication／來源／restart 的消毒 evidence 輸出；不記內部 reasoning 原文。
5. 將 exact 執行包、最大 180 requests、US$1.00 及單一公開合成 C-W 再交 Owner 作一次付費授權。未授權前不得送任何請求。

若凍結版本出現模型、價格、tier、context/output、重試、client owner 或並行方式差異，停止並重新審核本 gate；不能只改測試常數讓它通過。
