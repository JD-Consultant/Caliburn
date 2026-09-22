# JD 關聯式管理編輯器：第三方審查入口

- 日期：2026-09-12
- 審查類型：設計／authority／schema／tool contract；不是 code review
- 狀態：**Needs revision**；[2026-09-12 需求重審與設計 findings](2026-09-12-jd-relational-editor-needs-and-design-review.md)為最新結果，草稿尚未通過，不可直接施工。
- 本次更新：Owner 已選自動保存，另授權必要範圍裁決、澄清 JD／Memory 均可反覆修訂。[保存與 AI 交接](../2026-09-12-jd-autosave-and-handoff-design.md)與[完整業務操作](../2026-09-12-jd-business-operations-and-scope-design.md)承接。R02／03 見[保存窄複核](2026-09-12-jd-relational-save-contract-review.md)，R01／04／05 見[操作與內容複核](2026-09-12-jd-business-operations-review.md)，均 DESIGN CLOSED、未實測；整體 G4 仍 Needs revision。

## 1. 建議閱讀順序

1. [Owner 方向與可依情境重審的基線](../2026-09-12-jd-relational-editing-requirements.md)
2. [官方證據與本地現況](2026-09-12-jd-relational-editor-evidence.md)
3. [整體產品與資料流設計](../2026-09-12-jd-relational-editor-design.md)
4. [13 張 JD scope 表與保存交易](../2026-09-12-jd-relational-schema-and-write-contract.md)
5. [AI／App／員工操作契約](../2026-09-12-jd-relational-agent-tool-contract.md)
6. [Proposed ADR0075](../../adr/0075-relational-jd-authority-and-structured-editor.md)

本輪變更理由先讀[完整業務操作／範圍／JD 與 Memory](../2026-09-12-jd-business-operations-and-scope-design.md)；它不取代欄位寫作指南或資料庫／工具契約。

[Current Decision Register](../../current-decisions.md) 是狀態入口；[ADR0073](../../adr/0073-plate-jd-app-working-document-and-revision-authority.md) 只供比較被取代的完整 Plate JSONB 候選與既有實證。

## 2. 審查前提

- 產品是單機、單一操作者、多份隔離 document；不加入登入、ACL、多租戶、多人即時協作、雲端、RAG 或舊資料搬移。
- 六章 JD、成果／要求並列、K/S 供多個任務引用、AI 主寫但員工可編輯，是先前有背景的選擇；Owner 本輪允許依現在需求重新討論，不視為不可重議。欄位內文字與換行、App 統一排版已再次確認。
- 目前只審設計。沒有 migration、runtime、UI、自然模型、Excel renderer 或 production 切換可供宣稱 PASS。
- 舊管理畫面可解釋 CRUD 體驗；舊 package、route、checkpoint owner 與整份 PUT 不得接回 production。
- OpenAI／Anthropic 公開資料只支持 tool contract 原則；不要要求文件證明兩家公司使用相同 JD SQL schema，因該資訊未公開。

## 3. 請 reviewer 主要回答

1. **單一 authority：**relational current rows、derived immutable snapshot、operation receipt 是否分工清楚；有沒有可獨立寫入而形成第二份 current truth 的路徑？
2. **資料關係：**task→detail 1:N、task↔capability N:N、nullable duty、typed source targets 是否能由 PK/FK／service 共同保證同文件與生命週期？
3. **保存一致性：**current rows、snapshot、head、receipt 同 transaction 的順序是否會留下孤立 revision、部分套用或回覆遺失重做？
4. **歷史正確性：**move、shared K/S update、unlink、delete 與 source basis change 是否能使用 stable IDs 產生確切前後結果，而不拿 current 關係改寫 history？
5. **工具責任：**以實際新增／更正／移動工作核對工具粒度與人／AI 共用規則；不預設七工具或越小越好。是否說清何時使用、成功界線，且未把 document／operation／version／position／SQL responsibility 丟給 LLM？
6. **錯誤與 retry：**stale、missing、relationship conflict、dependent items、save failure、outcome unknown 是否各有唯一安全出口？
7. **產品操作：**結構化卡片／欄位與同頁歷史是否能完成 Owner 所說的 JD 管理，而不是換皮文件？
8. **可施工性：**是否有尚未明列、會改 schema／契約／主要 UX 的決策？請以 finding 指出，不以偏好的框架或命名取代具體產品影響。

## 4. 已知 OPEN 與刻意未決

**JD-R002/D01 任務保留政策已決：**Owner 授權研究者裁決，採刪職責、保留未分組任務，見[需求 §8](../2026-09-12-jd-relational-editing-requirements.md#8-d01刪除職責時保留任務2026-09-12)及[AWS 依據](2026-09-12-jd-relational-editor-evidence.md#7-aws-業務邏輯與-d01-裁決依據2026-09-12)。必要範圍隨任務，必要調整與結構原子保存；底層 `RESTRICT` 防繞過。JR-R05 已閉合文件反例，不能據此宣稱產品實測或整體 G4 通過。

真正未決：未歸任務的成果／要求草稿、保存後撤回與歷史分組、暫存恢復細節。兩者持續修訂已納入，沒有新增 Memory 引擎／永久 Memory 路徑引用。

「工作執行要求」仍是 UI 名稱推薦；domain kind 固定 `requirement`，名稱調整不需要改 relationship。Excel 版型也未決；本包只保證中立 projection 可形成。

## 5. 原作者初次自審紀錄（已由最新 finding 補正）

下列只是成稿當時的自查，不代表通過設計審查；「唯一未決」「ambiguity」等原判斷並不完整。最新已找到組合保存、讀取快照、失敗回執、選取替換及移動語意缺口，並重開部分產品情境，見頁首審查結果。

- **placeholder：**沒有 TODO／TBD 代替必要內容；唯一未決以 JD-R002/D01 及 Excel profile 明確標示。
- **contradiction：**0073 已在 header、ADR index 與 docs index 標成歷史 Proposed；current register 只路由 0075。Accepted production0060 仍有效，沒有以 draft 靜默取代。
- **scope creep：**沒有加入登入、多租戶、多人協作、CRDT、RAG、舊資料 migration、永久刪除或真人顧問權限。
- **ambiguity：**表數、欄位、PK/FK、delete action、source owner、current/history read、工具參數與錯誤出口已有責任文件；Plate leaf 是否啟用被隔離為不改 schema 的 UI spike。
- **known risk：**derived snapshot 與 current rows 的一致性依同一 transaction＋唯一 serializer＋round-trip tests；DB 不可能以一般 FK 證明 JSON snapshot 等於所有 rows。這是 reviewer 應優先判斷的取捨。

## 6. Finding 格式

每個 finding 請包含：

```text
ID / severity:
文件與段落:
違反的已定需求、官方契約或內部不變量:
可重現的產品／資料影響:
要求修正或需要 Owner 決定的具體問題:
```

若建議每版 relational clone、event sourcing、另一組工具或另一個 editor，請同時說明它解決的具體 failure、增加的 authority／migration／runtime 成本，以及為何 current design 的有限機制不足。
