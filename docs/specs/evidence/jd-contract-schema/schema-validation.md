# 最終 JD schema 的限定離線核對

**歷史版本提示（2026-09-10 後續補正）：**下方是當時85 defs／hash `6B42…` 的原始觀測；其完整 schema 現另存[補正前快照](../jd-contract-closure/schema-before.json)。目前 SSOT 已補正，最新結果見[獨立驗證紀錄](../jd-contract-closure/README.md)。下方舊腳本仍讀 current schema／當前文檔例子，直接重跑會檢查後來內容，不能重現當時全文環境或冒稱本次新結果；舊 script／數字不改。

2026-09-10；JD-R002/C03；root 另行執行的驗證，不是模型、Node editor 或產品整合測試。

使用既有 Node 22.12.0、AJV 8.20.0 Draft 2020-12 與已安裝的 `ajv-formats`。未安裝依賴，未執行 Plate、DB、ToolNode、DOM 或外部 provider。封存[實際腳本](schema-validation.cjs)與[正式 schema](../../contracts/jd-editor-v1.schema.json)配對；schema SHA256 為 `6B42BA220C0102590DC651692BE7497AE400BD713CB6F0D86FA1C5103F753F67`。

實際結果：85 個 definitions 皆能編譯解析；11 個檢查皆符合預期，0 errors。未開啟 coercion、預設值補入或額外欄位刪除。

| 檢查 | 結果 |
|---|---|
| F02 官方插件 canonical 完整 r2 | 通過 `JdDocumentValue`；沒有把舊 raw `li→p`／業務 leaf props 當作正式稿 |
| 契約附件 4 個 JSON 範例 | 分別通過 edit input、兩個 write results 及 manual input |
| Browser 選取 capture | base＋原生 range 通過；模型 read 直接傳 capture 被拒絕 |
| 人工 request key | 非 UUID 被拒絕 |
| 模型新增內容 | 帶既有 element ID 的 new content 被拒絕 |
| Node read-selection | 固定 request 與 success result 的正例均通過 |

最初 root 檢查未載入 `ajv-formats`，AJV 警告 UUID format 被忽略；因此沒有據此宣稱格式已驗。隨後使用既有官方格式套件，增加非 UUID 反例後重跑上述 11 項，結果如上；未放寬 schema。作者另行執行的代表例及 schema check 見[契約附件 §7](../../2026-09-10-jd-editor-contract-schema.md#7-有限驗證與未涵蓋範圍)。

重現：在 `S:/caliburn` 使用相同既有 runtime 執行 `node docs/specs/evidence/jd-contract-schema/schema-validation.cjs`。腳本只讀固定材料及輸出檢查結果；其他 checkout 需調整腳本的 root 路徑後另記結果，不改寫本次觀測。

這不能證明來源 scope、全文件 ID 唯一、基底仍為 head、實際原生 range 正確、保存交易、真 provider 接受或顧問品質。這些由六切片計畫各自驗收。先前 provider 序列化另有[執行時 schema 及版本沿革](provider-wire-schema-history.md)，不得拿新全檔 hash 回填舊觀測。
