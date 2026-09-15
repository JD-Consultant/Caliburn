# OpenRouter Responses inline compaction 真實 smoke

日期：2026-09-15
範圍：只驗 `ChatOpenAI Responses` 指向 OpenRouter 的服務端相容性候選；不是正式接線、Memory 重設計或顧問品質驗收。

## 結論

**`CLIENT-PASS` 保留；服務端 smoke 結果為 `UNVERIFIED`；正式改線維持暫停。**

實際請求已正確送到 OpenRouter `/api/v1/responses`，由 OpenAI route 的 `openai/gpt-5.6-luna-20260709` 完成並回 HTTP 200。服務端回報 23,725 input tokens，已高於請求中的 `compact_threshold=12000`，但 output 沒有任何 `compaction` item。因此這次無法進入「Saver 保存 → 重建 graph → 下一輪只帶 opaque item → 工具配對」的後半段，也不能把 HTTP 成功冒稱 compaction 支援。

這只說明**這次模型、route、日期與參數組合沒有產生必要 item**。它不是「OpenRouter 永久不支援」的普遍結論，也不否定同一客戶端在離線有效 Responses fixture 上能完整往返。

## 已授權與實際護欄

| 項目 | 實際值 |
|---|---:|
| 外送上限 | 最多 4 次，達標或失去可驗性即停止 |
| 實際外送 | **1 次** |
| 總預算 | **US$0.03** |
| 實際 provider 回報費用 | **US$0.00556460** |
| SDK 自動重試 | **0** |
| route | `only/order = OpenAI`、`allow_fallbacks=false`、`require_parameters=true` |
| provider storage | `store=false` |
| 資料 | 固定合成內容；沒有正式 JD、Memory、對話或使用者資料 |
| credential | 唯讀使用 Owner 指出的既有 App `.env`；值未輸出、未複製、未保存到證據 |

每次送出前的預檢從實際序列化 JSON 計算。輸入採 UTF-8 bytes 作 BPE token 的保守上界，輸出固定 1,024 tokens；第一請求的保留額為 US$0.01357600，低於總預算。回應後以 provider 回傳 cost 入帳，沒有假設快取折扣或把未知費用算成零。

## 單次請求證據

| 欄位 | 結果 |
|---|---|
| endpoint | `POST /api/v1/responses` |
| HTTP | `200` |
| request model | `openai/gpt-5.6-luna` |
| actual model | `openai/gpt-5.6-luna-20260709` |
| actual provider | `OpenAI` |
| input／output | 23,725／683 tokens |
| request `context_management` | `[{"type":"compaction","compact_threshold":12000}]` |
| compaction output item | **0** |
| setup reply | `READY`，且沒有把合成代碼重複到 compaction 後可能保留的尾端 |
| response id 證據 | SHA-256 `f04e04ffd65851b91126c708fce07fb1854697e9a9025e198c6130b1e25d7933`；不在可公開文件保存原 ID |

完整原始 prompt、opaque 內容、credential 與 raw response 不寫入 repo。可重跑的有界腳本是 `experiments/jd-relational-app/scripts/smoke_openrouter_inline_compaction.py`；它會在每次 HTTP transport 前重新驗 model、route、storage、compaction 參數、輸出上限、實際請求數及費用保留。

## 為何第 1 次就停止

第一請求的服務端 usage 已明確超過本案 12,000 門檻，且相同回應已證明模型與 OpenAI provider route 正確。必要的第一個 opaque item 沒有出現時，後續就不存在可以合法保存及續用的 item；重送同類長輸入只會增加費用，不能把缺少的服務端契約變成證據。因此依「注意用量、達成或失去可驗性即停止」在 1 次結束，沒有為了湊滿 4 次而重複付費。

## 影響與下一裁決

1. 不修改正式 A／B2、Prompt、Skills、Memory ABC、JD writer、CAS 或背景流程。
2. 不把目前 `ChatOpenRouter` 的 Chat Completions 接法補上一個假的 request-only helper；它仍無法往返 Responses compaction item。
3. 不把 `ChatOpenAI Responses`→OpenRouter 候選升格為 production transport；客戶端考卷全綠，但真服務端沒有給出第一個必要 item。
4. 下一步不是再擴大 mock。Owner 需在以下方向中裁決後才施工：保留單一 OpenRouter 限制並接受／另設長對話策略；允許 A／B2 使用已驗的 direct OpenAI Responses；或等待 OpenRouter 提供可引用且可實測的等價契約。第三條若採用會是新設計，不能冒充恢復原接法。

## 驗證

- 離線 adapter 契約：`4 passed`。
- 真實 OpenRouter smoke：`1` 次外送、HTTP 200、OpenAI route confirmed、US$0.00556460、0 compaction item，分類 `UNVERIFIED`。
- 沒有 production 變更、commit、push、merge 或資料庫寫入。
