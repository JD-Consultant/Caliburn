# JD v2 語意契約有限驗收

2026-09-10；JD-R002/C01／C03。只在本目錄建立新證據；v1 SSOT、既有 runner 與封存结果不修改。

唯一候選來源為 [`../../contracts/jd-editor-v2.schema.json`](../../contracts/jd-editor-v2.schema.json)。本目錄的 [fixtures](fixtures.cjs) 與 [runner](check-contract.cjs) 是固定合成案例及離線檢查，不是 runtime／codegen 的第二份契約，也不是員工資料或正式 JD 樣稿。

## 執行狀態

root 確認 v2 schema 就緒後，使用既有 Node 22.12.0／AJV 8.20.0 執行；兩次 exit code 均為 0。

| 實際結果 | 定義編譯 | Shape 案例 | 有限契約模型 | 合計／不符預期 |
|---|---:|---:|---:|---:|
| [首輪](initial-v2-results.json) | 105 | 114 | 40 | 259／0 |
| [最終](final-v2-results.json) | 105 | 121 | 42 | 268／0 |

首輪後追加 9 項新建 grammar 與兩阶段固定候選檢查；不是修改 schema 讓反例通過。本輪未重跑舊 v1 封存 runner，也沒有把此次執行說成修改 schema 之前的 red 階段。最終 runner 可重現 268 項，首輪 JSON 保留當時 runner hash 與全部觀測。

- v2 schema SHA256：`c6cc0f996b7a24b37cdf784a9d46e88cbb1d59f4d68d327e4167f3dfa40fb715`。
- 最終 runner SHA256：`5a8312b3bd71c21b29ff5158bc8b387b76022a8f587b58506f74891abfcf6234`。
- fixtures SHA256：`19fbf43d431e36fd799b8736a462e5f8d64eee4e6c6ddf708c06b0fef763114d`。

268 是不同層次的 assertion 數，包含 105 個編譯檢查，並非 268 個員工情境。結果內逐例標出層次、預期與實際值、輸入是否改變；沒有以 schema-valid 代替端點／scope 有效。

## 有限範圍

1. JSON Schema：全部 definitions 編譯；Task 平行成果／要求、完整 K／S、允許位置及有效空稿；saved IDs／model refs／resolved IDs 分隔；set／unset 交集；read targets 的正反向 refs；人工完整 value。AJV 不轉型、不补預設、不刪欄位，每例核對輸入不變。
2. 有限 read-only 契約模型：完整候選的 ID／端點／kind、同文件同版解析、history 只讀及 issued ref 範圍。刻意保留 shape-valid 但語意無效的反例，不能把 schema 綠燈說成 App 已檢查。
3. 固定前後候選：共享改名、移動、複製、刪除／ancestor 刪除、unwrap、人工全值、序列化回讀。這些只證明指定結果符合契約，**不執行或證明 Plate 複製／貼上／刪除／移動／unwrap 的實際運算**。同文件複製／跨文件帶相同 ID 的真 provenance 檢查仍須實際操作接點驗收。

首建只驗「新 items 無 link」及「後續已有 refs 的 set」兩種形狀、未發配／temporary ID 拒絕，並以固定第一階段未連結快照與第二階段連結候選，核對項目保留與關係有效；本 probe 不執行兩次實際保存或發配 refs。source_refs 與 relation refs 分開處理，未驗真實來源 owner。完整 JSON round-trip 不等於 Node normalization 或新程序重開。

外文件已發配 ref 的反例刻意使用與目的文件相同的 item ID，仍須因 scope 拒絕。單靠保存後的裸 ID／全候選存在性，不能識別貼上來源文件；這仍須真正 paste／copy 接點處理 provenance，不能讓本有限模型冒稱已攔下所有外文件手改。

## 重現

在 repo root、使用既有 Node／AJV 執行：

```text
node docs/specs/evidence/jd-semantic-contract-probe/check-contract.cjs
```

可用第一個參數指定候選 schema 路徑；stdout 是結果 JSON，失敗 exit code 為 1。後續新觀測另存新檔，不覆寫既有封存。此 runner 不連 DB／模型、不安裝套件、不開服務；SQL 原子發布、receipt、取消、真原生操作、DOM／IME、ToolNode 及自然模型品質仍按既有施工切片驗收。
