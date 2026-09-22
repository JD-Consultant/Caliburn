# JD 保存關係與 PostgreSQL 約束核對

- 日期／查閱日：2026-09-10；Topic：JD-R002/C03。
- 範圍：主設計 §5.4、Proposed ADR 0073、六切片 Task 2、正式設計 schema 的唯讀核對。只新增本證據稿；沒有 DB 連線、SQL 實驗、安裝、migration、Memory 或 production 修改。
- 結論：既有三份 JD 邏輯資料的責任可保留，沒有因「多對多」就新增來源資料庫的理由。尚須補齊的是初版參與關係、版本／回執的條件約束、循環 FK 的插入時點，以及交易錯誤的精確出口。這些是既有契約與 Task 2 的有限補正，不是新產品選項，也不阻塞獨立的 Task 1。
- 證據標記：**Fact** 為官方或本機文件直接所見；**Mapping** 為本案設計映射；**Inference** 為由該設計推出的後果；**Unknown** 為尚無實作／驗收證明。下表的 cardinality 是本案需求，不冒稱 PostgreSQL 或 AI 廠商規定的 JD 模型。

## 1. 權威與版本範圍

本輪依 [current register](../../current-decisions.md)、[decision process](../../decision-process.md)、[主設計 §4.1／§5.4](../2026-09-09-jd-editor-app-integration-design.md)、[ADR 0073](../../adr/0073-plate-jd-app-working-document-and-revision-authority.md)、[Task 2](../../plans/2026-09-10-jd-editor-core-implementation.md#task-2同-pg-唯一工作稿revision-與回執)、[schema](../contracts/jd-editor-v1.schema.json)。Owner 已選同 PG 唯一 JD 工作稿、immutable revisions 與可查差異；來源／Memory 保留既有 owner。ADR 仍 Proposed，隔離接合不等於 production authority 切換。

**Fact：**repo [docker-compose.yml](../../../docker-compose.yml:8) 指定 `postgres:16`；官方 current 文件本次解析為 PostgreSQL 18。本文實作依據均另核 PostgreSQL 16 固定文件，不使用 18 才有的能力。未查 DB，不能由浮動 image tag 推定正在執行的 minor 版本或實際 WAL 設定。

下列來源 publisher 均為 **The PostgreSQL Global Development Group**；查閱日均為 **2026-09-10**。頁面未標單頁發布日；網站當日公告日期不代替該頁發布日期。

| ID | 官方頁面／版本 | 本輪直接支持的範圍 |
|---|---|---|
| P1 | [Constraints，16，§5.4](https://www.postgresql.org/docs/16/ddl-constraints.html) | PK／UNIQUE／複合 FK、可空 FK、CHECK 跨列限制、關係表例子 |
| P2 | [Constraints，current→18，§5.5](https://www.postgresql.org/docs/current/ddl-constraints.html) | 現行交叉核對；上述基本原則仍存在，不代表本案升版 |
| P3 | [CREATE TABLE，16](https://www.postgresql.org/docs/16/sql-createtable.html) | 延後 FK、NULL 唯一性、constraint 與 `ON CONFLICT` 限制 |
| P4 | [JSON Types，16，§8.14](https://www.postgresql.org/docs/16/datatype-json.html) | JSONB 與關聯欄位併用、原子資料單位、表示與包含比較限制 |
| P5 | [Transactions，16，§3.4](https://www.postgresql.org/docs/16/tutorial-transactions.html) | 多步全成／全敗、未提交中間狀態不可見 |
| P6 | [Transaction Isolation，16，§13.2](https://www.postgresql.org/docs/16/transaction-iso.html) | Read Committed、每句快照、等待後重新檢查 |
| P7 | [Explicit Locking，16，§13.3](https://www.postgresql.org/docs/16/explicit-locking.html) | `FOR UPDATE`、row lock、deadlock 與一致鎖順序 |
| P8 | [Serialization Failure Handling，16，§13.5](https://www.postgresql.org/docs/16/mvcc-serialization-failure-handling.html) | `40001`／`40P01`／部分 `23505`；完整交易重試的責任 |
| P9 | [WAL settings，16，§20.5](https://www.postgresql.org/docs/16/runtime-config-wal.html) | `fsync`、`synchronous_commit` 與成功回覆的持久性條件 |

## 2. 實際關係與責任表

**Fact：**PK 提供唯一且非空身分；FK 保證被引用列存在，複合 FK 可以核對同一組欄位。這些機制不自行決定業務中的「一定有幾筆」。[P1](https://www.postgresql.org/docs/16/ddl-constraints.html)

以下全部為 **Mapping／Inference**，不是已實裝 DDL。

| 關係 | 本案 cardinality | SQL／App 各自承擔什麼 |
|---|---|---|
| catalog → head | 每份成功建立、啟用 JD 的文件恰一個 head；每個 head 恰屬一份文件 | `head.document_id` PK＋catalog FK 只保證 catalog 至多一個 head；「至少一個」由 catalog＋初版＋head 同交易建立保證。既有無 JD 的隔離 catalog 不因這句话自動完成搬移 |
| catalog → revision | 初版建立後一對多，每版只屬一文件 | `(document_id, revision_id)` 複合 PK；文件 FK／scope。只有完整新版本進此表，不保存未發布候選 |
| head → current revision | 每 head 恰一版；一版最多被同文件的一個 head 指為 current | current revision 非空，`(document_id, current_revision_id)` FK 指同文件複合 PK；只核 revision UUID 存在不足以證明同文件 |
| revision → parent revision | 初版無父版；其餘恰一個同文件父版 | 可空同文件自我 FK＋初版條件；自我 FK 本身不證明沒有分叉／循環。現行線性版本序列來自「鎖 head，核 base，成功才發布」協定，不需要另一套歷史引擎 |
| catalog → operation | 一對零至多；每個回執只屬一文件 | `(document_id, operation_id)` PK；同鍵綁相同 digest，終局不可覆寫。UUID 本身不代表來源或操作已授權 |
| operation → **產生的新 revision** | committed 恰一個；no_change／確定失敗為零 | 一筆成功操作只產一版；非初版的 producing operation 對應該次提交。初版不是虛構的模型操作 |
| operation → **引用的 result revision** | committed 引用新版本；no_change 引用既有 base；許多 no_change 可指同一版 | 與上一列不同，不能將所有 `result_revision_id` 設成唯一。可選 result/base FK 仍限同文件；失敗不以 result 引用冒充新產內容版 |
| 一個保存版 → JD 樹節點 | 有序樹：每次出現的節點恰一個父位置，父節點可含多個 children；root array 為虛擬根 | 完整 value 放一份 JSONB；grammar／Element ID 唯一性由固定 profile 驗證。同一 Element ID 可跨版本延續，不建立「每個 Task 一列」或額外身分引擎 |
| JD 節點 ↔ canonical 原文引用 | 語意上可多對多：一節點有零至多來源，同一原文可支撐多節點／版本 | 在 value／操作記來源 handles；既有來源 owner 核文件 scope 與精確原文範圍。這不是要求把 source 複製到 JD 表或另造 junction store，也不對 Saver／Store 私有資料結構建立新 FK |
| run／tool call → JD operations | 一個 run 可零至多次工具修改；工具呼叫與操作的綁定由 App 保存 | 純訪談可無 JD operation。外部 opaque refs 經 mapper 解析，不把模型給的字串直接當資料庫 FK；run／Memory／來源 authority 不搬到 `jd_operation` |

例如先保存 r7，員工連按兩次沒有內容差別的保存，會有兩個不同 operation 都回 `no_change` 並引用 r7；此時不是兩個新版本。接著 AI 修改產 r8，只有這筆 committed operation **產生** r8。這解釋為何不能籠統說「回執與版本是一對一」。

## 3. 必須補正、不能用 schema／FK 名稱代稱已閉合的地方

### R1：初版、空稿與可空引用

**已有設計：**Task 2 明列同交易建立 catalog、canonical 空 `p` 及 head；schema 的 `JdDocumentValue` 非空，空稿不是 `[]` 或無 head。此方向完整，不需再問 Owner。

**尚須落實：**初版 `origin=initial`、無 parent、無 producing operation；後續版本需要同文件 parent 與產生操作。對可空 `(document_id, parent_revision_id)`／result FK，文件 ID 仍非空，不能不加區分地採 `MATCH FULL`。同列的狀態與可空條件由明確約束處理；只有 FK 不會限制一文件最多一個初版。

**Fact：**預設 nullable FK 與 `MATCH FULL` 的規則不同；CHECK 遇 NULL 不等於失敗，必填欄位仍需非空約束。條件唯一性及 NULL 比較也須明列，不能靠預設推論。[P1](https://www.postgresql.org/docs/16/ddl-constraints.html)、[P3](https://www.postgresql.org/docs/16/sql-createtable.html)

### R2：版本與回執的循環引用、條件一致性

**Inference／重要缺口：**主稿同時描述 revision 保存 producing-operation、operation 引用 result revision。若兩側都做立即 FK，新增成功版與回執便出現互相等待對方先存在的插入關係。Task 2 在寫 DDL 前須固定其中一側 FK 延後到交易結束檢查，或採單向持久關係並查得反向關係；不要把兩個立即 FK 寫完後才用暫存假回執繞過。

**Fact：**PostgreSQL 16 可延後 REFERENCES 約束；可延後 constraint 不可充當 `ON CONFLICT` 的 conflict arbiter。因此若採延後 FK，沒有理由連 operation 去重 PK 都改成延後。[P3](https://www.postgresql.org/docs/16/sql-createtable.html)

**Mapping：**需要一張有限的保存結果條件表：committed 的 result 是新版本且 parent=base；no_change 的 result=base 且未新增版本；確定失敗不產新版本；所有 `actual_changes` 的 before／after 與 receipt 對應。現行 schema 核型別與狀態欄位，沒有比較 opaque refs 彼此相等，也不查資料列。可放同列的關係用 CHECK；跨列用 FK、鎖內核對及 mapper／service 斷言。不可用會查其他列或 Memory 的 CHECK 函式假裝完成跨 owner 一致性。

**Fact：**CHECK 不能可靠承擔對其他資料列的檢查；官方建議適用時使用 FK／UNIQUE 等約束。[P1](https://www.postgresql.org/docs/16/ddl-constraints.html)

### R3：JSONB 是完整文件的存法，不是取消 relational constraints

**Fact：**PostgreSQL 允許 JSON 與關聯資料共用，建議資料有可預期形狀，並留意整個 JSON row 的鎖定範圍。JSONB 不保留空白、object key 次序及重複 object keys；其 array containment 比較不考慮次序與重複項，不能拿來證明兩棵有序文件樹相同。[P4](https://www.postgresql.org/docs/16/datatype-json.html)

**Mapping：**完整 JD revision 是本案原子保存單位，所以 value／native operations 可以用 JSONB，文件／版本／操作身分與關係仍有獨立受約束欄位。`no_change` 與 digest 要沿固定、經 schema 驗證的 Python 表示及結構比較，不由 JSONB 顯示字串或包含運算臨時推算。`immutable` 不是 JSONB、PK 或 FK 自動提供：JD store 必須只新增版本、拒絕覆寫終局回執，並在既有 Task 2 驗收；此處不另加事件庫。

**Unknown：**正式輸入到 JSONB 的邊界尚未驗證，例如 PostgreSQL JSONB 拒絕的 U+0000、非法 surrogate；若不被既有 validator 阻擋，必須走確定未發布的保存錯誤，而非自動改文或另造 codec。這不推翻已驗的普通 JSON-native 正常文件。

### R4：交易、重試與持久確認必須分層

**已合理：**Read Committed 配合單文件 head row lock、鎖內再次查 receipt／digest／base，符合 PostgreSQL 的等待及重檢能力；模型與 Node 候選留在交易外。`FOR UPDATE` 只鎖實際存在的列，不能把查不到 head 當成已取得該文件鎖或自行初始化既有文件。正式同時競爭仍由 Task 2 兩連線驗收，P01 交錯執行不冒稱相同證據。[P5](https://www.postgresql.org/docs/16/tutorial-transactions.html)、[P6](https://www.postgresql.org/docs/16/transaction-iso.html)、[P7](https://www.postgresql.org/docs/16/explicit-locking.html)

**尚須固定：**已確認交易中止的 `40P01`，以及若實際使用會產生該錯誤的隔離層時 `40001`，只能在有限次數內以同 operation／digest 重跑完整保存交易與決策；不重跑模型、另配 operation 或略過 receipt/base。`23505` 不能一律重試，去重衝突須讀原 receipt 並分辨同鍵同意圖／不同 payload。commit 後連線斷開的未知結果走 receipt reconcile，不視為 rollback。已保存的 terminal failure 也不能在重試時改寫成成功。[P8](https://www.postgresql.org/docs/16/mvcc-serialization-failure-handling.html)

**Mapping：**沿現有 head→receipt 核對順序固定各 writer 的鎖順序，維持短交易即可，不為此新增全域鎖或通用 retry 引擎。deadlock 是資料庫可偵測並中止交易的失敗，不代表只要用了 row lock 就不可能發生。[P7](https://www.postgresql.org/docs/16/explicit-locking.html)

**Unknown／驗收前提：**`receipt_durability=confirmed` 不能只代表 Python 已拿到記憶體結果。正式測試需記實際 PostgreSQL 版本與 logged tables／WAL 設定；官方 `fsync` 與 `synchronous_commit` 預設為 on，但本輪沒有查正在執行的 DB。`synchronous_commit=off` 可在未保證 WAL 落盤前回報成功，會改變當機後回執保證。這是應查證的執行前提，不是本輪另改 DB 設定。[P9](https://www.postgresql.org/docs/16/runtime-config-wal.html)

### R5：catalog 刪除沿革與隔離實況矛盾

**Fact／本輪讀取時的 finding：**主稿 §5.4 尾段仍要求「active 狀態／既有刪除生命週期／實際刪除驗收」，但 §4.1 與 Task 2 已明列隔離 catalog 沒有 deleted／active 欄位或刪除 API。不能將 production 舊能力當成 CT49–51 已有接點。

**處置分工：**主線已確認會修主稿沿革；本附件不修改它。隔離核心只核文件存在性與 scope，整份文件刪除及來源／Memory 清理仍由 production adoption 的獨立 authority gate 處理；不能為湊 FK 級聯測試自行新增刪除流程。JD 正文內刪 Task 與刪 catalog 是不同操作。

## 4. 有限退出條件

1. 契約補正／Task 2 明列初版及 committed／no_change／failure 的欄位關係，決定循環 FK 的實際檢查時點；同文件 FK 與 producing/result 的不同基數有明確落點。
2. 既有 Task 2 測試包含同文件初版、no_change 多回執引用同版、跨文件引用拒絕、原子 rollback、真正同步竞争、同键重開與 commit 回覆遺失；檢查真實 head／revision／receipt，不只狀態字串。schema 合法不代表資料庫已驗。
3. 鎖順序、有限 SQLSTATE retry、unknown reconcile 與實際 DB 持久設定有明確責任；不因錯誤重新執行模型或變更操作身分。
4. 來源驗證留既有 owner，JSONB 文件驗證留固定 Plate profile，業務條件留有限 App／DB 邊界；不新增 Memory、source junction store、通用歷史或資料同步引擎。

以上是本案可以直接收斂的工程責任，不要求員工或 Owner 選 PK／FK／資料表類別。官方能證明 SQL 機制；本案哪些關係是一對一、多對多、何時算成功，仍須由已同意產品語意及可驗證契約決定。本輪沒有把這些待施工條件改判成已通過。
