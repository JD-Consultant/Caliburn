# JD 關聯式保存：JR-R02／03 修訂窄複核

- 日期：2026-09-12；Topic：JD-R002；層級：文件設計複核。
- 結論：**JR-R02、JR-R03 DESIGN CLOSED**；其他 findings 與整體 G4 維持 Needs revision，ADR0075 Proposed／production0060 不變。
- 範圍：[schema §4.3、6.2、7、9](../2026-09-12-jd-relational-schema-and-write-contract.md)、[工具 §3.1、6、8](../2026-09-12-jd-relational-agent-tool-contract.md)。原始反例保留於[首次審查](2026-09-12-jd-relational-editor-needs-and-design-review.md)。
- 方法：主代理核 AWS／PostgreSQL 現行文件後修稿；唯讀子代理 `save_transaction_research` 獨立追查來源、核對既有恢復契約，再讀修訂稿回覆窄核結論。主代理核實並接受下列結論。沒有讓 reviewer 改檔或自行接受 ADR。

## 修訂及複核結果

| Finding | 修訂與 reviewer 核對 | 判定 |
|---|---|---|
| JR-R02：多表 current 混版 | 短 READ ONLY REPEATABLE READ 一次讀完 head、正文、關係、source links；refs／target digest 由該材料產生。current 分頁固定 revision，變動要求重讀；history 固定 immutable revision。外部來源可讀性另外觀察，不宣稱全域快照 | 文件矛盾已解；DESIGN CLOSED |
| JR-R03：rollback 後假 confirmed | 區分 binding 前拒絕、bound stale／資格再驗失敗、savepoint 內語意拒絕、整筆失敗與 COMMIT 未知；只在 terminal 真提交後 confirmed。原 operation 未閉合優先 reconcile；停止證明後使用 READ COMMITTED document→head barrier，再於下一 statement 查原 receipt。known-none 才原 key failure-only 閉合，無 replay | 文件矛盾已解；DESIGN CLOSED |

額外核對：request digest 涵蓋 document、origin、base 與完整 commands；同 key 偷換 base 不能當重試。候選 savepoint 位於 document／head 鎖之後；mutation 同步逐句送且不繞過相同鎖，才能沿既有停止／DB 邊界證明。binding 後 archived／ownership 檢查不再留下無 terminal 卻已解綁的出口。

## 自動保存草稿的追加走查

同一 reviewer 另唯讀核[自動保存與 AI 交接稿 §2–6](../2026-09-12-jd-autosave-and-handoff-design.md)，發現 AS-R01：單次 IndexedDB 更新原子，不代表多次更新不會舊稿蓋新稿。反例為 A 確認時擷取 B，C 先暫存，A 隨後寫回 B；或舊普通暫存清掉同輸入序號的固定 A identity。

主代理接受反例，補入同 session／document 串行更新入口、record generation／submission 階段保護、普通暫存只能更新候選、confirmed 只清匹配原 identity，以及回存時保留最新候選；加入兩個有限驗收情境。**修稿經同一 reviewer 窄複核，AS-R01 DESIGN CLOSED**；不宣稱 IndexedDB／整份自動保存已實測通過。其餘 A／B 承接、未知先對帳、重開不 replay 及 AI admission 核預期版本，reviewer 未發現新矛盾，可保留為 G4 細化候選。

## 證據界線與後續

本次 **未執行** SQL、DB 交錯實驗、Web 或模型測試。DESIGN CLOSED 表示原 finding 的契約矛盾已閉合，不能當成 migration／程式或成品驗收。

實作必測：r5 讀取中提交 r6 仍完整同版；原 batch 先移任務後驗證失敗；failure receipt INSERT／COMMIT 失敗；成功或失敗 COMMIT 已成但 ACK 丟失；同 key 不同 base；停機後舊 SQL 晚到；分頁過時。全部沿資料庫責任稿驗收，不建立第二份保存引擎。

JR-R01、04、05 繼續 OPEN；自動保存的整項撤回、操作粒度、瀏覽器格式／容量及資料集識別亦未由本次窄核定稿。
