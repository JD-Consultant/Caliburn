# 當輪原話來源：來源模組作者驗證

- 日期：2026-09-13；OI-02 局部。設計依[本輪接合切片](../../2026-09-13-jd-consultant-source-integration-slice.md)及[來源接點核對](source-seams.md)。
- 作者：`jd_ref_signer_preflight`；只新增 `experiments/jd-relational-app/src/jd_relational/conversation_sources.py` 與 `tests/test_conversation_sources.py`。root／middleware／人工 API／PG 接合由其他作者負責。
- 本檔是作者證據，獨立審查另記；未開服務、未寫 DB、未呼叫 SDK／provider 或付費模型，沒有新增依賴、資料表、模型工具或通用 registry。

## 完成的有限能力

`ConversationSourceCodec(secret_key: bytes, dataset_id: str)` 使用既有 ItsDangerous 2.2.0 `URLSafeSerializer`／SHA-256、同持久 key／dataset，獨立 salt `caliburn.jd.conversation-source.v1`。只有私有固定 source position，沒有接受任意用途／payload 的公開 codec。原 `ChatHistoryCodec` 與 JD ref 格式未改。

| 公開接點 | 實際語意 |
|---|---|
| `ConversationSourceService(checkpoints, codec).dataset_id` | 唯讀 scope，供 trusted composition 核與 JD dataset 一致。 |
| `capture(document_id, run_id)` | 從 `AiRunCheckpoints.discover` 的固定 root/source 選本輪已保存 Human，及其前面最近的公開 AI 回應。向前遇到另一個 Human 即停止，不把較早答案隱藏在引用範圍內。 |
| `read(source_ref, document_id)` | 用 token 固定的 root/source 呼叫原 `observe_at`，重核 first/last 必須等於這份材料的 App 選取。last 是該 run 的 Human；不 fallback latest，不 invoke 或修復 graph。 |
| `resolve(source_ref, document_id)` | 真讀取與驗證通過才回 `domain.Source(document_id, readable=True)`；錯誤窄轉原 `ReadError`，供人工／AI 共用保存。 |
| `for_turn(document_id, run_id)` | 回傳 lazy callable，首次才 capture；其後同輪固定相同 excerpt／token。每次驗證傳入 request messages 的相同 ID、role、完整公開文字及顺序，才產生純 metadata notice。 |

capture/read 返回 frozen、隱藏 repr 的 `SourceExcerpt(source_ref, messages)`；messages 是 tuple frozen `SourceMessage(message_id, role, text)`，不含 tool／thinking／signature／usage。通知僅有 `type=conversation_source_notice`、source_ref、message IDs/roles、固定 instruction；沒有原話正文。instruction 明示 AI 是上下文，不是已確認的員工事實，來源可讀不等於支持全部 JD target。

request 可省略 AI 的 private thinking blocks，但同一則 AI 的公開文字必須完整相同。Human 原字串連同繁中、CRLF、空白與 emoji 都比較 exact；遺失、更改、角色替換、反序、重複、插入別的 Human 或傳入 chunk 不能聲稱來源仍可見。驗證不改 request 或原 Saver messages。

token 固定格式 `1`／purpose `source`，定位欄位為 dataset/document/run、root checkpoint、source namespace/checkpoint、first/last IDs；不含原文。嚴格 Pydantic 固定形狀，沿既有 4 KiB token／未壓縮 worst-case admission；不是新簽章或 JSON 定位引擎。簽章不是加密、writer permission、模型理解或語意支持證明。

## 首敗與修正

1. 先落新測試而尚未實作模組：**1 collection error，3.12s**，`ModuleNotFoundError: jd_relational.conversation_sources`。
2. 模組初版：**42 PASS／2 FAIL，4.42s**。一項是作者測試 oracle 錯誤：root 與 source 相同時，原 helper 只應讀一次固定 root，不能要求重讀同點。修正該斷言，沒有改原 helper。
3. 另一項為實際錯誤映射：合法 source token 指向已不可讀的固定 root 時，原 helper 的 `run_not_found` 被誤當 `invalid_ref`；改為 `source_not_available`，仍不選 latest。錯 token／scope／first-last 範圍保持 `invalid_ref`。
4. 修改後新檔全組：**44 PASS，3.83s**。

```text
uv run --frozen --offline pytest -q tests/test_conversation_sources.py
44 passed, 1 warning in 3.83s
```

warning 為既有 pytest cache 目錄 ACL，非測試失败。首失敗兩次亦有相同 cache 類 warning。本次沒有重新跑整套 checkpoint／signer 舊矩陣。

## 覆蓋與限制

覆蓋本切片五類新增行為：

1. 真 native InMemorySaver 的 root／active child／START 已保存原話，無本輪完成 AI 回答仍可提供来源；前 AI 及 Human 各自公開角色與內容保留。
2. 同 child 前進／後續新 run／新 codec 後固定來源不變；read 僅使用原固定配置、模型節點呼叫數不增加。
3. 同輪首次 lazy capture、後續不重發；metadata defensive copy、原 request 不改，以及上述可見性負例。
4. 新用途、舊 `conversation:`、chat anchor、JD ref、錯 key/dataset/document、篡改、錯格式／first-last、缺固定 checkpoint／driver exception 的拒絕與安全錯誤。
5. 70,000 個繁中 AI 字及 43,000 個繁中 Human 字完整讀回，沒有新增分頁或截句；immutable excerpt 與錯誤 traceback 不洩 private marker。

這些是**真 native 保存＋合成節點／訊息**的離線來源驗證；`for_turn` 對傳入 message list 的單元反例不等於已捕捉真 SDK model request。native middleware 時序、實際 provider request metadata、同源人工／AI SQL 保存、手改 basis 與回覆遺失查回，由本輪其他接合測試負責；此檔不能取代那些證據。

本模組的來源讀取本身不授予 owner／停止能力；呼叫者仍負責既有前景執行及唯讀排空。沒有變更較早 Memory source 檢索、背景整理、完整專業指引、來源 UI 或自然品質；OI-02 仍非整體完成。
