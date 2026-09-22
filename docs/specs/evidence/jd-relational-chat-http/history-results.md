# 固定聊天歷史頁：實作與原生證據

日期：2026-09-13。基準 `2734b82b`；本單位只實作聊天投影、專用 cursor，以及既有固定 checkpoint 讀取的必要 source 接點。零 provider／DB／宿主服務操作，未新增資料表或另一份對話權威。

## 1. 效果與責任

[ChatHistoryService](../../../../experiments/jd-relational-app/src/jd_relational/chat_history.py) 的 `read(document_id, *, cursor=None, limit=50)` 回傳 exact dict：`dataset_id`、`document_id`、`anchor`、`messages`、`next_cursor`。每個 message 只有 `message_id`、`run_id`、`role=user|assistant`、`text`。外部 DTO／response 驗證由同輪正式生成契約負責，這裡不另維護外部 schema。

第一頁從同一份有效 native observation 取得完整 messages；續頁固定原 root **及 source**，新回合、結案或同一子流程後續寫入都不混入原頁。`anchor` 是原定位的簽名 opaque token；空紀錄回 `anchor=null`、`messages=[]`、`next_cursor=null`。原 Human 的 ID 是 run 歸屬；其後 AI 公開回覆沿該 run，工具或 system 消息不改變歸屬。當前最後一筆 Human 必須和 observation 的 run 一致。

`public_chat_text(message)` 是共用的公開文字投影：Human 保留原純字串；完整 AI 使用現行 native `.text` **property**；空的 AI 公開文字、tool、system 不展示，partial chunk 拒絕。不輸出 thinking／reasoning／signature、tool arguments／result／artifact、usage 或其他 metadata；不為顯示方便改寫 Saver 中的完整消息。

`ChatHistoryCodec(secret_key, dataset_id)` 由 trusted composition 注入既有設定的同一組 key／dataset。使用 ItsDangerous `URLSafeSerializer` 和具名 salt `caliburn.jd.chat-history.v1`，與 JD ref／ReadCursor 分隔。簽名 payload 只有 format、purpose、dataset/document/run、root/source 位置與 offset，不含對話正文或秘密。Token 可讀、非加密，亦不是權限證明；不加入第二個 key、持久 registry 或 key 檔。正常重新建立 codec 可繼續讀原 cursor；更換 dataset／key、跨文件、把 anchor 或 JD cursor 當續頁皆拒絕。

每頁最多 **50 則公開消息及 1 MiB compact UTF-8 JSON**。只切整則消息；若單則放不下，回固定 `history_page_too_large`，不截正文。每則大小只編碼一次，減少候選頁時僅重算小型 envelope，避免重複序列化大正文。這個界線不代表底層 Saver 只載入一頁：現有 native graph 仍讀一個固定的完整消息集合；尚未加入對話刪除、壓縮或大型歷史儲存優化。

## 2. 查明並修正的原生接點

**CH-H01：只有固定 root，仍可能混入前進後的 child。** 修改前以真 InMemorySaver 建立 root／child、停在 child interrupt，然後只推進同一 child，原 `observe_at(root)` 得到：

```json
{"fixed_root_equal": true, "source_changed": true, "first_messages": 2, "later_messages": 3}
```

這是行為反例，不是透過修改預期把既有測試標紅。探針初次因沒有加入 App `src` import path 而未執行；修正探針路徑後取得上列原生結果，前一個 import 錯誤不算產品故障。

因此窄擴 [AiRunCheckpoints.observe_at](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py) 的 optional keyword `source_config`。省略時保留原本行為；指定時：

1. 核 exact root/source config 的 thread、namespace 與 checkpoint ID 形狀。
2. 用官方 `get_state(root, subgraphs=False)` 讀原 root 和 task scope，避免讀取 latest child 作為副作用。
3. 核原 root 的唯一 consultant task namespace，直接讀已指定的 exact source；原 source 是 root 時保持原 root 材料。START 只允許自己的 root source，沿原 saved input 解碼。
4. 仍共用原 record／Human digest／完整 messages／view 配對驗證；固定位置缺失或相互矛盾時明確失敗，不 fallback latest 或回空歷史。

這不是 worker 停止證据、writer authority 或 SQL 結果確認；唯讀 callback 的 owner 範圍由上層 `inspect` 負責。

## 3. 官方事實及本案選擇

| 查閱依據 | 已核事實 | 適用與限制 |
|---|---|---|
| [LangChain Messages](https://docs.langchain.com/oss/python/langchain/messages)；已裝 `langchain_core/messages/base.py:263–295` | 原生消息保留內容與 metadata，AI 可以包含 tool calls；現行 `.text` property 只連接純字串及 `type=text` 的字串欄位。`.text()` 方法已棄用。 | Core **1.6.3**、穩定 MIT；使用 property，不自行從 reasoning／未知 blocks 猜公開文字。這是 UI 投影規則，完整 native message 保存方式不變。 |
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)；現有固定 checkpoint／history 探針及本次真 native 反例 | 原生 config 可固定 checkpoint；subgraph 狀態另有 namespace／位置。 | LangGraph **1.2.11**、checkpoint **4.2.0**，穩定 MIT。先前固定 root 的共用介面不足以承諾跨請求同一 child，因此以有界原生實測補 source pin，而非推測內部產品行為。 |
| [ItsDangerous general concepts](https://itsdangerous.palletsprojects.com/en/stable/concepts/)；既有 reference signer 證據及本地 package license | 同 key 可用不同 salt 區分用途；簽名保護內容完整性，不加密 payload。 | **2.2.0** 穩定、BSD-3-Clause（本地 `LICENSE.txt`）。新 salt／typed cursor 是本案映射，未自建密碼機制。4 KiB token／未壓縮 admission、沒有時鐘逾時是本案工程界線。 |

頁面公開格式、50 則／1 MiB、空 AI 不顯示與 role/run 對應均為本案產品接合，不稱大廠共同採用的統一 schema。Provider 原 call/context 完整性沿[既有工具保存依據](../jd-relational-ai-runtime/admission_checkpoint_notes.md)；這次沒有新的模型呼叫契約或需重開的品牌研究。

## 4. 驗證結果

[test_chat_history.py](../../../../experiments/jd-relational-app/tests/test_chat_history.py) 首個實作組 **21 PASS／0.97s**；補固定 source、signed malformed payload、START、完整消息大小等反例後，本檔 **39 例**。最後命令：

```text
uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_chat_history.py tests/test_ai_checkpoints.py tests/test_ai_checkpoint_discovery.py tests/test_ai_history.py
145 passed in 1.98s
```

覆盖：106 則分頁／後續新 run／新 codec；作用中 child 前進但原頁不變；原 Human 換行與 Unicode；thinking／reasoning／signature／工具／usage 不外露且 native 保存值未改；anchor/cursor 與 JD cursor 不混用；跨 dataset/document/key 拒絕；bool／float 版本、額外欄位、offset、來源 scope／位置缺失拒絕；空紀錄；START 原 Human 加先前 V1 完整消息；完整文字不截斷；未知例外隱藏原細節。既有 observe/discover/history 回歸保留預設行為。

所有建立／推進圖動作都是測試合成 StateGraph fixture；讀取方法不 invoke、update、resume 或寫資料。這不是 HTTP、真 DB、新宿主、瀏覽器或自然模型驗收。正式契約、HTTP／Web 接合、可用性与 provider 成本仍由後續／同輪其他工作包證明。
