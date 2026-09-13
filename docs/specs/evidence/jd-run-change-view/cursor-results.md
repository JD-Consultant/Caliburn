# 整輪改動固定游標：作者驗證結果

- 日期：2026-09-13；本輪 CV-01 整輪改動接線。
- 作者：`jd_ref_signer_preflight`。本檔整理當輪已實跑的首敗及最後結果；整理文件時沒有重跑測試。
- 產物：[`references.py`](../../../../experiments/jd-relational-app/src/jd_relational/references.py) 的 `RunChangeCursor`／專用 codec 接點，以及 [`test_run_change_cursor.py`](../../../../experiments/jd-relational-app/tests/test_run_change_cursor.py)。
- 這是**作者證據**。同目錄 [server-review.md](server-review.md) 審查的是其他作者的伺服器接線，明確排除對本游標實作的自我獨審。

## 完成效果

App 將本次已確認的 operation IDs、捕捉時是否已完整收尾，以及頁面 offset 保存為有簽章的 continuation。後續頁能固定在原捕捉範圍，不靠記憶體 registry，不增加資料表，也不把後來新增的操作默默混入。游標本身不判定 SQL 已保存或回合已停止；這些事實由既有 owner／native 回合與歷史 reader 核對。

`RunChangeCursor.capture(document_id, run_id, operation_ids, settled)` 接受嚴格的 0–96 個不同 UUID tuple，排序以保持同組 ID 的表示一致；不默默去重。欄位只有 canonical document／run UUID、`operations_b64`、嚴格 boolean `settled`、0 至 `2**63-1` 的嚴格 integer `offset`。`operation_ids` property 還原原 tuple。格式 envelope 為 exact integer `1`，拒絕 `True`、`1.0` 或字串冒充版本。

新增 `ReferenceCodec.issue_run_cursor`／`resolve_run_cursor` 使用**原有 ItsDangerous 2.2.0 `URLSafeSerializer`、SHA-256 signer、同一 configuration key／dataset**，僅另設用途 salt `caliburn.jd.run-change-cursor.v1`。沿原 `_dump` 與 4096-byte 限制；沒有新簽章、壓縮、定位或續頁引擎。既有 JD reference／read cursor 的 payload、salt 與實際 token 格式不變，測試直接用官方 serializer 比對。

## 容量與拒絕條件

- 以 Python 標準 `UUID.bytes` 串接固定 16-byte IDs，再用標準 URL-safe Base64。96 個 IDs 為 **1536 bytes／2048 Base64 字元**；沒有存成 96 個帶引號的 UUID 字串。
- 沿原 signer 的未壓縮 JSON 最壞長度 admission，**不因 ItsDangerous 恰好壓得小就放寬**。本輪高熵合成 96 IDs 的 raw 上界與最終 token 均在既有 4096 限制內；0／1／96 IDs、兩種 settled 值及最大 offset 均完成 round trip。
- 原容量探針對 UUID 字串版與 packed 版的精確量測，集中見[本輪接線設計](../../2026-09-13-jd-run-change-view-slice.md#唯一必要的容量驗證)。本檔不把他人的容量探針列成作者另一次實測。
- 256-byte 普通 ASCII dataset 通過；需要大量 JSON escape 的 256-byte 控制字元 dataset 仍明確拒絕，沒有提高上限。正式 managed dataset／document／run 是 canonical UUID。
- 解碼使用標準 Base64 嚴格驗證、回編字串 exact 比對、byte 數為 16 的倍數且不超過 1536、IDs 不重複。錯誤 padding、非 canonical pad bits、標準 Base64 的替代字元、97 IDs、錯型別及額外欄位均拒絕。

簽章提供完整性與用途隔離，不是加密或權限授予。游標沒有正文或金鑰；不把 opaque token 解碼交給 Web／模型。相同 key／dataset 的新 codec 可查回；換 key、換 dataset、跨 document／run 或拿其他用途 token 代入均拒絕。

## 首敗與最後結果

下列數字依本輪工具執行記錄整理，沒有用本次文件編寫補跑冒充原始結果。

| 階段 | 實際結果 | 意義 |
|---|---|---|
| 新反例先落檔、實作尚未提供 | 1 個 collection error：不能 import `RunChangeCursor` | 新能力尚不存在的首敗；不是故意放寬原測試 |
| 完成實作後的新游標測試 | **62 PASS，0.27s** | 真官方 signer 與嚴格 payload／scope／容量反例 |
| 原 reference 93 案＋新游標 62 案 | **155 PASS，1.36s** | 新用途加入後，原 reference／read cursor 行為及 token 契約回歸通過 |

最後回歸範圍：

```text
uv run --frozen --offline pytest -q tests/test_references.py tests/test_run_change_cursor.py
155 passed in 1.36s
```

當次有既有 pytest cache 目錄 ACL warning；沒有測試失敗。覆蓋還包括合法簽章包住非法資料、內部 `model_copy`／`model_construct` 被 issuer 重新驗證、跨用途／資料集／文件／回合、token 篡改、過長或非 ASCII token，以及固定 `invalid_ref` 不在 exception cause／traceback 回顯 token。

## 證據界線

以上為合成 IDs／合成 key、真 OSS serializer 的離線單元驗證；沒有 DB、服務、provider 或付費模型呼叫。它不單獨證明 native 捕捉正確、SQL 快照一致性、HTTP 原回合查回或 UI 分頁。這些責任分別由 [PG 接合結果](postgres.md)、[伺服器獨立審查](server-review.md) 及本輪其他接點證據說明，不混算驗收層級。
