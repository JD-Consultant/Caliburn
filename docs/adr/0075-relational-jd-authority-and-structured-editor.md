# 0075. 關聯式 JD authority 與結構化管理編輯器

- **狀態**：Proposed／Needs revision；[原設計 findings](../specs/evidence/2026-09-12-jd-relational-editor-needs-and-design-review.md)已文件閉合，產品未決與整體驗證仍待完成，尚未改變 production authority
- **日期**：2026-09-12
- **Topic**：JD-R002/C01、C03
- **Owner 方向**：要求關聯式資料庫、職責／任務／成果／要求／K/S 的獨立 CRUD 及任務跨職責移動；舊編輯器可作需求參考，不沿用其 authority
- **設計**：[整體設計](../specs/2026-09-12-jd-relational-editor-design.md)、[資料庫契約](../specs/2026-09-12-jd-relational-schema-and-write-contract.md)、[AI／App 工具契約](../specs/2026-09-12-jd-relational-agent-tool-contract.md)

## Context

ADR 0073 提議以完整 Plate 文件樹、immutable JSONB revisions 與三個工具承接新的唯一工作稿；隔離核心已完成固定操作、保存、差異與恢復驗證。Owner 實際查看預覽後指出，成品像一篇文件，職責、任務、成果、要求及 K/S 缺少清楚欄位與關係操作，無法成為預期的 JD 管理編輯器。

舊 `ApprovedDocumentEditor` 能新增／刪除 duty/task、移動 task、管理 O/P/K/S 與多任務 K/S 引用，證明需求的具體操作；但其後端仍整份保存 `ApprovedJobDocument`／LangGraph state，並非新的 relational authority。照搬舊碼會重新接入已退役 package 與 lifecycle。

PostgreSQL 16 提供 PK/FK、junction tables、delete actions、transactions 與 row locks；OpenAI 與 Anthropic 的現行工具契約都把模型呼叫與 App 執行／結果回饋分開。這些可作機制基礎，但沒有供應商公開 Caliburn 應採的 JD SQL schema。[官方證據與邊界](../specs/evidence/2026-09-12-jd-relational-editor-evidence.md)

## Decision

1. **目前 JD 正文改以 relational rows 為唯一可寫 authority。**職責、任務、成果／要求、知識／技能、條件與關係都有 stable business identity；名稱、位置或 Plate path 不作身分。

2. **使用 shared document catalog，加 12 張 JD 表。**完成態共 13 張 JD scope 表：正式 `jd_document` 共享 conversation／Memory／JD document identity；`jd_profile`、`jd_collaborator`、`jd_duty`、`jd_task`、`jd_task_detail`、`jd_capability`、`jd_task_capability`、`jd_condition`、`jd_source_link` 保存 current；`jd_head`、`jd_revision`、`jd_operation` 保存目前指標、歷史與回執。隔離 `q019_document` 只屬研究命名，fresh adoption 一次改用正式表名，不建立第二份 catalog。正式欄位及 FK 由 schema spec 負責，ADR 不另造第二份 DDL。

3. **Outcome／requirement 與 knowledge／skill 各按相同生命週期合表、用 kind 區分。**`jd_task_detail.kind` 固定 outcome／requirement；兩組平行、無一對一 pairing。`jd_capability.kind` 固定 knowledge／skill；任務與 capability 由 junction table 建 N:N，同一關係反向投影使用任務，不存第二份 incoming 清單。

4. **目前內容 relational，歷史 snapshot 唯讀。**每次成功保存由 server 在同一 SQL transaction 從 current rows 產生 immutable canonical JSON snapshot；snapshot 不接受作 current write payload，不能被修改。current、revision、head 與成功 receipt 同交易全成或全敗；語意失敗先撤候選、另確認外層 failure receipt 提交。回覆不明保留原 operation，沿既有停止證明及 DB 邊界對帳，不重播。current 多表讀取、head 與 refs 使用同一短唯讀快照；外部原始問答來源查核分開標示。具體分支由資料庫契約 §6–9 負責。

5. **同一頁採結構化管理畫面。**聊天與唯一 JD 並存；右側以具名欄位、職責／任務卡片、成果／要求子清單、K/S relation selector、歷史／差異／來源抽屜呈現。未分組任務是合法資料。沒有「目前稿／更正稿」雙頁、pending 接受／拒絕或第二份可編正文。

6. **Plate 不再控制整份 JD。**結構、CRUD、relations、dirty buffer、保存與歷史由 App 處理。Plate 只保留為需要 selection／IME／undo 或富文字的單一長文字欄位候選；普通 text 足夠時不強制啟用。是否使用 leaf Plate 由 bounded UI spike 決定，不改 relational authority。

7. **模型使用具名且能完成完整工作的業務工具。**依工具責任稿提供讀取、完整新增任務、有界內容修訂、單欄／選區與結構操作；不凍結七工具或讓同項更正逐欄提交。strict schema 與 App-issued refs 協助定位；模型不填 document／operation IDs、SQL FK、position、revision 或 line number。人與模型共用 service／validator／transaction 並取得真實結果；具體 variants 與驗收見[完整業務設計](../specs/2026-09-12-jd-business-operations-and-scope-design.md)。

8. **人工自動保存，已保存事件進下一輪模型 context。**Owner 已選一般文字短暫停頓後保存、結構操作完成後整組保存；保存中的後續輸入須保留。啟動 AI 前完成手改交接，App 以 response-backed model-view boundary 查後續 revisions，提供有界 manual event notice 與 change refs；不偽裝成員工原話、不改寫 Memory、不表示本輪必須再編輯 JD。細節及尚待驗證項目見[保存與交接設計](../specs/2026-09-12-jd-autosave-and-handoff-design.md)，不是新建另一份可寫正文。

9. **來源保留引用，不複製原文。**`jd_source_link` 指向既有來源 owner；目標文字改變後以 basis digest 標成需重新核對，不能讓舊 source 無條件替新文字背書。K/S relation 本身可有來源 link。

10. **刪除政策按 ownership 分開。**刪 task 的 owned details 與 task relations 可在明示 command 中一併移除，共享 capability 保留；仍被引用的 capability 採 RESTRICT。D01 已依 Owner 授權由研究者採[刪職責保留任務](../specs/2026-09-12-jd-relational-editing-requirements.md#8-d01刪除職責時保留任務2026-09-12)：App 同交易解除分組再刪 duty，DB 保留 RESTRICT 防止直接刪除。任務特有必要範圍隨任務卡、職責僅概括；必要內容調整及成果／要求新增與結構操作原子保存，自有來源分開處理、不自動轉掛。人與 AI 共用此業務效果，參照 [AWS 官方分層與生命週期依據](../specs/evidence/2026-09-12-jd-relational-editor-evidence.md#7-aws-業務邏輯與-d01-裁決依據2026-09-12)，不因此採用 AWS 服務。

11. **同文件寫入依固定順序鎖 document／head rows，不用 service-global mutex。**archive／restore 走相同順序；不同 documents 可獨立操作。同文件 manual／AI foreground writer 仍沿既有 admission。模型與 transaction 外的候選計算不持有 SQL row locks；canonical snapshot 在短交易內由 current rows 產生。

12. **fresh adoption，不搬舊資料、不雙寫。**新 schema 在專用新 DB 驗證；正式切換一次移除舊 JSONB current write、舊 approved/candidate writers 與 retired routes。conversation／Memory／source owner 仍依其 successor ADR 決定，不由本 ADR 重做。

13. **Excel 是 deterministic projection。**current relational projection 或指定 history snapshot 可映成中立 export model，再由 renderer 產生選定格式；LLM 不產 Excel。實體版型尚未決定，舊 iCAP exporter 只作研究與 oracle，不直接接回 retired package。

## Supersedes when Accepted

| 既有決策 | 取代部分 | 保留 |
|---|---|---|
| [0073](0073-plate-jd-app-working-document-and-revision-authority.md) | 完整 Plate JSONB 作 current authority、whole-document model edit 與 Plate whole-document UI | 同一工作稿、實際差異、operation receipt、同文件 writer、來源／Memory owner 邊界及既有故障證據 |
| [0060](0060-langchain-langgraph-consultant-runtime-and-durable-authority.md) JD authority 部分 | Saver／Store 中的 approved／candidate JD writers 與舊文件審核 publication | 顧問 runtime、conversation／Memory 分工；其正式採用另由 0074 或 successor 完成 |
| [0066](0066-persistent-ai-jd-working-draft-and-semantic-review.md)、[0067](0067-deep-agents-store-backed-jd-working-draft.md)、[0069](0069-shared-current-jd-working-copy-and-semantic-approval.md) 的 JD 保存部分 | Store workspace、current↔approved 雙狀態、semantic accept/reject／rebase | 同文件延續、按需讀取、保存後可查差異等產品目的 |
| [0070](0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md) 的 JD 表單候選 | 舊 pending lifecycle、舊整份物件寫入與舊欄位形狀 | 舊畫面作 CRUD／relation 需求證據，不作 runtime import |

Accepted 歷史 ADR 不改原文；只有本 ADR Accepted 且 production G6 完成後，上表才改變正式 authority。

## Consequences

員工得到真正能管理 JD 項目與關係的畫面；任務移動、K/S 共享、刪除影響與 Excel 投影不再依文件排版猜測。AI 工具參數更少，也不需生成整份文件或維護 DB metadata。Stable IDs 與 immutable snapshots 讓歷史比較不靠模糊文字定位。

代價是 current save 需同時維護 8 類正文／關係 rows、canonical snapshot 與 receipt；source link 的 typed targets、position normalization、current→snapshot round-trip 及 relation diff 都需專門測試。Leaf Plate 是否值得保留尚需 UI spike，不能把既有 whole-document Plate 測試直接當成新畫面通過。

13 張表不是產品品質指標，也不是宣稱 JSONB 不可表示關係；它是目前 CRUD、關係完整性與歷史需求下的可審映射。若未來證明每版 relational clone 更簡單可靠，可另以 successor 比較，不在第一版並建兩套。

## Rejected alternatives

- **保留整份 Plate JSONB，只在 UI 外觀加卡片：**仍沒有 relational current rows，移動／引用／刪除完整性只能由整份 validator 承擔，沒有解決 Owner 指出的資料與操作問題。
- **把舊 ApprovedDocumentEditor 及 backend 接回來：**舊畫面可學，舊 authority／route／package 已退役且仍整份保存，會產生 compatibility path。
- **每個 revision 複製所有 relational rows：**歷史純 relational，但每次小改都複製全部資料，第一版 schema、FK 與查詢顯著擴張；沒有目前需求需要支付此成本。
- **event sourcing 只存 commands、靠 replay 重建 current：**對本機 JD 的 read、重開與匯出增加 replay／upcaster／snapshot 管理，現有需求可由 current rows＋derived history 完成。
- **讓 LLM 送 generic CRUD／SQL-like payload：**增加無關欄位、跨類型錯誤與資料庫責任外洩；不符合 strict、small named tool 的證據方向。
- **所有文字都使用 Plate editor instance：**沒有內容需求證明每欄需要 rich text，並增加多 editor focus／undo／效能風險；先以 leaf spike 決定。

## Open decision and acceptance gate

**D01 任務保留政策已依 Owner 授權裁決；完整設計仍 Needs revision。**讀取與回執 JR-R02／03 通過[保存文件窄複核](../specs/evidence/2026-09-12-jd-relational-save-contract-review.md)，JR-R01／04／05 通過[完整操作文件複核](../specs/evidence/2026-09-12-jd-business-operations-review.md)；均未實測。Owner 後續已選不另設待整理區、歷史對照／局部更正／整份還原，研究者受權裁決先不设持久 AI 試稿區，見[需求 §10–11](../specs/2026-09-12-jd-relational-editing-requirements.md)。[歷史與恢復設計](../specs/2026-09-12-jd-history-and-recovery-design.md)將還原限定為人工端經同一 domain／交易產生新 JD 修訂；保留中間歷史，不倒退原始問答或 Memory。暫存格式／容量／資料集識別與完整 G4 尚待閉合，本 ADR 保持 Proposed。

進 G6／施工前還必須：

1. D01 與必要範圍已回寫；閉合其餘產品未決並以固定案例驗刪除保留及仍有效條件；
2. reviewer 可只依設計回答 current authority、表關係、工具責任、錯誤／恢復及歷史來源；
3. 無影響實作的 schema／contract finding；
4. 另產生實作計畫、generated contract、fresh migration 與可證偽測試；
5. 不使用付費模型完成 core schema／CRUD／failure tests；自然模型另按核准預算驗收。

本稿未建表、未改 code／runtime、未搬移、未呼叫產品 provider、未 merge 或 push。
