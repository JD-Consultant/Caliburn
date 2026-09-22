# OpenRouter Responses inline compaction 真實 smoke 重跑

日期：2026-09-21
範圍：只驗 `ChatOpenAI Responses` 指向 OpenRouter 的服務端相容性候選；不是正式接線、Memory 重設計或顧問品質驗收。

## 結論

**結果為 `UNVERIFIED`，正式 transport 不切換。**

本次依使用者授權執行有界真實測試。請求正確送到 OpenRouter `/api/v1/responses`，HTTP 200，由 OpenAI route 的 pinned Luna model 完成；實際輸入 usage 已高於 `compact_threshold=12000`，但回應沒有產生任何原生 `compaction` item。因此不能進入 Saver 保存、graph 重建與下一次 opaque context 續接驗收，也不能把 HTTP 成功當成 compaction 支援。

這只表示本次模型、provider route、日期與參數組合沒有產生必要 item；不宣稱 OpenRouter 永久不支援，也不否定離線 adapter fixture 的往返能力。

## 護欄與實際結果

| 項目 | 實際值 |
|---|---:|
| 外送上限 | 最多 4 次 |
| 實際外送 | **1 次** |
| 總預算上限 | **US$0.03** |
| 實際 provider 回報費用 | **US$0.00500740** |
| SDK 自動重試 | **0** |
| model request | `openai/gpt-5.6-luna` |
| actual model | `openai/gpt-5.6-luna-20260709` |
| actual provider | `OpenAI` |
| route | OpenAI only；fallback disabled |
| provider storage | `store=false` |
| compaction threshold | `12000` |
| max output tokens | `1024` |
| compaction output item | **0** |
| 輸入／輸出 usage | 23,495／257 tokens |
| 資料 | 固定合成內容；沒有正式 JD、Memory、對話或使用者資料 |
| credential | 從 `apps/api/.env` 唯讀讀取；值未輸出、未複製、未保存 |

預檢先以序列化 UTF-8 bytes 作輸入 token 上界，合成 setup 為 60,487 bytes；第一請求保留額為 US$0.01357600。回應後只採 provider 回報 cost 入帳，未假設快取折扣或把未知費用算成零。

## 觀察到的契約結果

- 第一請求確實回報高於 compaction threshold 的 input usage。
- 回應 HTTP 200，且 setup 回覆為預期的 `READY`，沒有把合成識別碼重複到後續可保留尾端。
- 回應沒有 `compaction` item，故沒有合法的 opaque item 可供保存、讀回或下一請求續用。
- 因第一個必要 item 未出現，腳本在 1 次停止；沒有為湊滿 4 次而重複相同付費測試。

## 決策與限制

1. 不修改正式 A／B2、Prompt、Skills、Memory、JD、DB 或 production authority。
2. 不把目前 Chat Completions 接法補成假 request-only compaction helper。
3. 不把本次候選升格為 production transport；`CLIENT-PASS` 仍只代表離線客戶端契約，不代表服務端能力已驗證。
4. 不重跑同類 smoke，除非有新的服務端契約、模型／參數變更或明確的新驗證問題。
5. 下一個 transport 裁決仍由產品決定；本次沒有授權 direct OpenAI production 切換，也沒有新增 credential。

## 可重現與證據界線

預檢及真實測試均使用：

`experiments/jd-relational-app/scripts/smoke_openrouter_inline_compaction.py`

腳本保留最多 4 次請求、預算閘門、無自動重試、無 provider fallback、OpenAI-only route 與 `store=false`。原始 prompt、opaque payload、credential、raw response 及 response ID 不寫入 repo。此次沒有 production 變更、資料庫寫入、commit 或 push。
