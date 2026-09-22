# LangMem Domain Semantic Memory 窄實驗記錄

- **日期**：2026-08-29
- **狀態**：Completed experiment；尚未核准 production 導入
- **分支／基準**：`refactor/current-only-architecture` / `eedc73e1351f62a31750d269ddf6065045104e71`
- **上游研究**：[對話連續性與工作理解 Context 研究 §16](2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md#16-domain-semantic-memory-底層重審codexclaude-與-langmem2026-08-29)

## 1. 問題與邊界

Caliburn 的 Domain Semantic Memory（工作理解）必須跨長訪談保存員工工作的具體細節，接受局部補充、更正與衝突釐清，又不能因一次修訂遺失無關內容。本實驗只回答兩個窄問題：

1. LangMem core memory manager 能否在現行 `ReceiptChatOpenRouter` 上運作，而不撞到已知 strict Tool schema 相容問題？
2. 在成本受限的多輪情境中，它能否保留細節、選對既有 record、處理更正／未知／一次性事件，而不把無關內容寫入記憶？

這不是正式 eval、production migration 或資料庫測試；不加入 dependency、migration、Store writer、RAG、embedding 或第二 memory owner。

## 2. 環境與成本護欄

| 項目 | 實際值 |
|---|---|
| 模型 | `openai/gpt-5.6-luna`，reasoning `medium` |
| 路由 | 現行 `ReceiptChatOpenRouter`，OpenRouter provider only=`OpenAI` |
| Python | 3.13.12 |
| LangMem | 0.0.30（一次性 `uv --with`，未加入專案） |
| TrustCall | 0.0.39 |
| LangChain / LangGraph | 1.3.15 / 1.2.11 |
| langchain-openrouter | 0.2.7 |
| 最大模型呼叫 | 6 |
| 每次最大輸出 | 2,000 tokens |
| 總 token 護欄 | 50,000 |
| 成本護欄 | 若 receipt 可取得，US$0.50 |
| LangMem `max_steps` | 1（不允許額外 synthesis／repair step） |

為避免不必要成本，16 個員工訪談輪次分成 6 批，每批只執行一次 memory manager。第 6 批前重建 manager object，再把既有 collection 載入，驗證 core manager 不依賴 process-local hidden state。

所有送往外部模型的內容都是明確標示的「完全虛構月球溫室」資料。原先較貼近人資／勞動法的 synthetic payload 在任何 API 呼叫前被安全層拒絕，故沒有外傳、沒有 token 或費用；實驗隨即改採明顯虛構資料，沒有繞過安全層。

## 3. 最小 schema 與原因

```python
class WorkMemory(BaseModel):
    kind: Literal["pattern", "case", "unresolved"]
    body: str
```

模型只填它真正能從語意判斷的 `kind` 與完整 `body`；stable ID 由框架／application 取得，模型不填 ID、版本、時間或來源位置。

前置兩輪 compatibility probe 曾使用 `subject + detail`。雖然 10 筆細節完整保留、目標 ID 正確，模型把 `detail` 從「每月」修成「每兩週」後，重複表意的 `subject` 仍殘留「每月」。因此長訪談 probe 刪除這個冗餘欄位。這是實際證據支持的 field-contract 縮減，不是為了讓測試變綠而另加 verifier。

## 4. 固定情境

六批內容依序覆蓋：

1. 建立感測器警報處理的完整 recurring pattern，包括查核資料、三十分鐘時限、一般處置與高風險核准例外。
2. 補充追蹤表六個欄位、每日／每週節奏、演練內容與同事分工。
3. 明確把「每週五彙整」更正為「每週三」，增加重大壓力下降的即時通知，混入與工作無關的午餐資訊。
4. 加入一次性的跨組資料搬移，明說不是固定工作。
5. 加入「某些一般重新啟動可能要組長覆核，但尚不確定」的衝突線索，並要求不要覆寫既有規則。
6. 重建 manager 後，確認只有營養泵韌體更新需要組長覆核；另把演練從每兩個月更正為每月。

## 5. 實際結果

| 驗收項目 | 結果 | 證據摘要 |
|---|---|---|
| 現行 adapter／strict schema | **Pass** | 6/6 呼叫成功，沒有 strict schema、validation 或 repair 錯誤 |
| coherent record boundary | **Pass** | 首批 3 輪整合成 1 筆完整 pattern，沒有一句一筆；最終共 5 筆 coherent records |
| 局部補充 | **Pass** | 追蹤表六欄與重大壓力通知加入既有主 pattern，同一 ID 保留 |
| 明確更正 | **Pass** | 「週五→週三」與「每兩月→每月」都更新原 record ID；舊頻率沒有殘留 |
| 未提及細節保留 | **Pass** | 角色、查核來源、30 分鐘、核准規則、追蹤表欄位、每日檢查與同事分工皆保留 |
| 一次性事件 | **Pass** | 資料搬移獨立成 `case`，明確保留「非固定、非定期」；未污染 recurring pattern |
| 衝突／未知 | **Pass** | 未知先形成 `unresolved`，沒有把所有一般異常改成需核准 |
| 未知解決 | **Pass** | 下一批確認後，同一 unresolved ID 轉成 `pattern`，寫入營養泵例外 |
| 無關內容 | **Pass** | 午餐資訊未進入 collection |
| manager 重建 | **Pass（窄義）** | 重建 manager object 後仍選對既有 ID 並更新；未測 DB/process crash resume |
| stable identity | **Pass** | 五個最終 record 的更新均沿用既有 ID，沒有更正後 duplicate |
| 完全無重疊 | **部分通過** | 最終營養泵例外 record 重述了有毒氣體核准規則；內容一致、沒有矛盾，但有輕度跨 record 重疊 |

最終 collection 為：

- 主要警報處理與追蹤 pattern；
- 每日檢查／每週三彙整 pattern；
- 每月演練與同事分工 pattern；
- 一次性跨組支援 case；
- 營養泵重新啟動覆核例外 pattern（由 unresolved 原 ID 轉成）。

## 6. 實際成本與效能

| 指標 | 實際值 |
|---|---:|
| Model calls | 6 |
| Total tokens | 11,658 |
| OpenRouter reported cost | US$0.00546695 |
| Model latency 加總 | 36,723 ms |
| 實際 provider / model | `OpenAI` / `openai/gpt-5.6-luna` |
| Retry／repair calls | 0 |

這組結果證明，在一組 16-turn synthetic transcript 上，用 6 個單步 reconcile calls 可以低成本完成局部記憶維護；它不能外推成所有真實長訪談都會成功。

## 7. 已知限制與未證明事項

本實驗**沒有**證明以下項目：

- 真實員工語句的 source handle、quote anchor、revision lineage 與 retire mapping；
- LangGraph PostgreSQL checkpoint 的 crash／restart／time-travel；
- 8～10 筆以上 collection 的 index＋JIT detail retrieval；本次每回合仍把完整既有 collection 交給 manager；
- 多次隨機重跑、不同模型、不同職務或極長訪談的統計可靠度；
- validation failure 後 canonical checkpoint 不受污染；本次完全沒有接 canonical storage；
- `case／pattern／unresolved` 是否就是 production 最佳 schema；目前只用來驗證機制。

因此不能把結果寫成「LangMem 已全面取代 Work Understanding」。能成立的結論只有：**現行 adapter 技術相容，LangMem core 的 collection reconcile 在這個固定案例中展現了本產品需要的主要行為，而且成本可接受。**

## 8. 暫定裁決

1. LangMem core `create_memory_manager` 維持為 semantic reconcile 的優先候選；不採 direct Store manager，不改 LangGraph checkpoint 的 canonical owner。
2. production field contract 應維持最小，避免同一事實由多個模型欄位重複表達；stable ID、revision、timestamp、source resolution 由 application 負責。
3. 不因這次成功建立正式 Eval 平台或先跑昂貴的大量重複試驗。產品實作完成後，再以 anonymized／synthetic golden transcripts 做 deterministic regression。
4. 若下一步要決定正式導入，最小剩餘證據是：source／revision mapping、checkpoint rollback，以及 index＋JIT read path；不得把未測項目宣稱為已通過。

## 9. 參考資料

- [LangMem Core Concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- [LangMem Memory API](https://langchain-ai.github.io/langmem/reference/memory/)
- [LangMem semantic-memory guide](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)
- [TrustCall](https://github.com/hinthornw/trustcall)
- [OpenAI GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
- [OpenAI Graders](https://developers.openai.com/api/reference/resources/graders)
