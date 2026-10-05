# ADR 0080：以明示設定接入公版參考工具

- 狀態：Accepted（2026-10-05；使用者要求「現在接入 tool」，同時要求保護正在進行的其他測試）。接線施工與驗證狀態依[計畫](../experiments/engineering/README.md#角色接線)，本次不重啟現行服務。
- 範圍：在 ADR0079 的正式 App 上增加可選 HTTP consumer；RAG 仍是獨立服務，不成為預設啟動依賴，也不移入 App 套件。
- 接續：將先前「獨立 RAG 不接 JD App」調整為「明示設定時可供模型按需呼叫」。不改寫歷史 ADR，也不變更 JD／Memory／訪談權威。

## 決定

沿已確認的[公版工具與排除範圍契約](../specs/2026-10-04-public-reference-completion-design.md)，由 App 設定決定是否在新請求啟用。顧問有五個工具，可查找公版、按需讀取、選主要參考與保存員工明確否認的工作；B1／B2 只讀固定批次上界內的排除範圍。公版提供查漏線索，正式工作事實仍由員工訪談支持，選用公版不等於認定職位或完成 JD。

`Settings.occupation_references` 預設空；配置 URL 後，composition root 沿既有資源生命週期建立 HTTP client。沒有設定時不建 RAG client、不增加工具、不碰 reference candidate。URL 與 timeout 由 App 提供，模型無權填 scope、版本或服務位置。公版 state 保存在既有獨立 feature，不複製進 Memory／JD。

工具沿現有 native prepare／execute／result 邊界，使用既有 JSON prepared command 與原 operation replay，不新增 Agent loop、恢復引擎或持久配置表。每個 execution／role 已保存的請求保留原工具清單與提示；發布新程式或更改配置不能改寫已開始的請求。新功能設定只影響尚未綁定的新請求。

## 取捨與啟用

明示啟用讓既有部署、離線測試與其他人正在進行的模型比較維持原行為。代價是實際使用前要啟動獨立 RAG、配置 URL，並在安全點重啟欲使用功能的 App。此輪施工不操作共用服務或正式 DB。

既存研究支持 D20／T20 完整聯集後全文重排序的比較基準，使用時機依顧問收尾查漏需求；檢索來源與分數仍由[API 設計](../specs/2026-10-05-occupation-reference-api-design.md)負責。本 ADR 採用接線權責，不將程式測試提升為真人訪談效果。
