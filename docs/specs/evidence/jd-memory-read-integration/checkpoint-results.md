# Memory 讀取版本與原生 checkpoint：作者結果

日期：2026-09-13。基準：`81a1ca76`。本檔記錄原設計審查後，經主代理授權轉為實作的範圍；**不是這兩個檔案的獨立實作審查**。[獨立接合審查](review.md) 由另一作者負責；其他唯讀工具的獨審另見 [source-review](source-review.md)。

## 實作與責任

- [ai_checkpoints.py](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py) 將 `jd_memory_view` 經 START discovery、root／child material、`AiRunObservation.memory_view` 及既有 `close(...)` 保存。`close` 呼叫介面不變；property 每次回傳獨立 JSON 副本。
- 驗證委派 [memory_context.checked_memory_view](../../../../experiments/jd-relational-app/src/jd_relational/memory_context.py)：固定 dataset／document／run；revision 0 對應 null version，正 revision 對應版本 UUID；不查 Store、不重讀導覽、不重新選目前出版版。
- 舊 START 原四欄及舊 saved payload 缺少 Memory 欄仍相容。START 明確將缺欄視為 `None`，不繼承前輪的版本。已有 Memory view 卻沒有 AI run，以及同一 run 的 root／child 固定版本不一致，皆拒絕為 `invalid_checkpoint`。
- 收尾 readback 必須仍是原 view；其餘收尾欄正確但 Memory 被改動，仍回 `closure_unconfirmed`。這個 view 是本輪選定的讀取版本，不是模型確實讀過內容的證據，也不提升 JD 寫入或模型通知基準。

## 可重現反例與結果

測試：[test_memory_read_recovery.py](../../../../experiments/jd-relational-app/tests/test_memory_read_recovery.py)。使用真正 StateGraph／InMemorySaver、合成 child 與 native START／interrupt；不使用 DB、Store I/O、provider 或背景工作。

1. 先寫 21 個反例，未改實作時 **21 FAIL／3.98 秒**：包含 Memory property 缺失、START 多一欄被拒、壞 view 被接受、root／child 版次不同仍通過，以及無 AI run 卻帶 view 被當空歷史。
2. 最小修改後，新 21 案及原 `test_ai_checkpoints.py`／`test_ai_checkpoint_discovery.py` 合併 **106 PASS／8.58 秒**。
3. 再加 revision 0／非空版本與 ACK readback 偷換合法 Memory view 的兩項必要反例；新專檔最終 **23 PASS／6.21 秒**，exit 0。

案例保留原 Human 換行與訊息內容，涵蓋既有／無 Memory 的 START、中斷子圖、ACK 遺失、重新建立 adapter、legacy payload、欄位／scope 錯誤與 close 重複。將出版版查詢及 artifact 讀取改為一旦觸發即失敗，證明恢復不重取 Memory。

執行使用新 App 的 `uv run --offline --frozen --no-sync`，指定 `-p no:cacheprovider`；沒有變更 dependency 或其他代理程式。以上三組有重疊，不相加。owned code／tests 的 `git diff --check` 通過。本檔不代稱真 PG、程序重開、真模型或完整 Memory 工作流程通過；獨立審查由另一代理負責。
