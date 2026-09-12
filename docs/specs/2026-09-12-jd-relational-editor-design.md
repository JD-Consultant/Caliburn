# JD 關聯式管理編輯器：整體可驗證設計

- 日期：2026-09-12
- Topic：JD-R002/C01、C03
- 階段：G4 DRAFT；待 Owner／外部 reviewer 審查
- 前提：[Owner 方向](2026-09-12-jd-relational-editing-requirements.md)、[官方證據](evidence/2026-09-12-jd-relational-editor-evidence.md)
- 效力：只形成可審設計；沒有改 schema、程式、資料、production authority 或付費模型設定

**保存方向已選定（2026-09-12）：**Owner 已同意[一般文字自動保存、結構操作完成後整組保存](2026-09-12-jd-autosave-research.md)。下方 §3.2／5.1 已依此修訂，輸入與恢復細節由[保存與 AI 交接設計](2026-09-12-jd-autosave-and-handoff-design.md)負責；不把方向同意當成所有工具／撤回流程已定稿。整體仍 G4 Needs revision。

## 1. 最終效果

員工在同一畫面與 AI 顧問持續訪談，右側看到的不是一篇難以管理的自由文件，而是一份有明確欄位與關係的 JD：能新增職責、建立／刪除任務、把任務移到另一職責、逐項管理成果與要求，並從任務引用共用知識／技能。所有已保存內容真正寫入 PostgreSQL relational rows；重開後仍是同一份資料。

AI 與員工使用同一份目前工作稿。AI 不必每輪改稿，只有某項工作已有足夠資訊或需要修正時才執行業務操作。每次成功修改都可查看實際前後內容、操作者來源與依據；App 不以模型的一句「已更新」代替保存證據。

## 2. 設計選擇

### 2.1 三個實質方案

| 方案 | 優點 | 主要問題 | 判斷 |
|---|---|---|---|
| A．整份 Plate／JSONB 為目前正文 | 已有隔離核心與原生文件操作證據；任意排版容易 | CRUD、移動與共享關係藏在文件樹；Owner 已確認畫面不像管理 JD；DB 無獨立業務列 | 不再作新 authority；保留舊實證 |
| B．每個 revision 完整複製全部 relational rows | 每版都完全 relational，歷史查詢直接 | 每次小改複製全部 rows；DDL、FK、查詢與寫入放大，第一版複雜度高 | 保留替代；目前不採 |
| C．目前正文 relational rows；每次保存同交易產生 immutable snapshot 與 receipt | current CRUD 與關係清楚；歷史可精確還原；沿用已驗版本／防重概念；施工範圍有限 | snapshot 是衍生副本，需測試保證由 current rows 產生且不可獨立寫入 | **推薦** |

### 2.2 唯一可寫 authority

1. 目前 JD 的唯一可寫正文是 relational current rows。
2. `jd_revision.snapshot` 是成功保存後由 server 從同交易中的 relational rows 產生的唯讀歷史材料；API 不接受 snapshot 作 current 寫入，也不能修改既有 snapshot。
3. `jd_operation` 是同一次寫入的終局回執；它證明已發生的效果，不保存另一份可編正文。
4. conversation、原始訪談、Memory 與來源原文仍由既有顧問 owner 保存。JD 只保留受核對的 source reference，不複製來源正文。
5. Web、AI、匯出與歷史畫面都經同一 application service 讀取；Web 不自行拼另一份 domain truth。

這個分工使 relational rows、snapshot 與 receipt 各有單一用途，不形成雙寫兩份目前稿。

## 3. 成品畫面

### 3.1 同一工作區

```text
┌──────────────────────────────┬──────────────────────────────────────┐
│ AI 顧問訪談                   │ 這份職務說明書                 已保存 │
│                              │ [本次改動] [歷史] [依據]              │
│ AI：你平常先從哪項工作開始？ │                                      │
│ 員工：……                      │ 一、職務基本資料                     │
│                              │   職務名稱／單位／匯報／協作          │
│                              │ 二、職務目的                         │
│                              │ 三、主要職責與工作任務      [+職責]   │
│                              │   職責 A                         [⋯] │
│                              │     任務 1  [移動] [刪除]             │
│                              │       敘述                           │
│                              │       成果／產出          [+新增]     │
│                              │       工作執行要求        [+新增]     │
│                              │       所需知識／技能       [管理引用] │
│                              │ 四、知識總覽                  [+新增] │
│                              │ 五、技能總覽                  [+新增] │
│                              │ 六、條件與責任邊界            [+新增] │
└──────────────────────────────┴──────────────────────────────────────┘
```

仍是同一個頁面、同一份 JD。歷史與差異在右側抽屜或展開區顯示，不導航到「目前稿／更正稿」兩個頁面。

### 3.2 結構化編輯行為

- **基本資料／目的：**以具名欄位直接編輯；未知可留空，不由 AI 填假值。
- **職責：**卡片顯示名稱、範圍說明、排序及其任務；可新增、改名、移動順序與要求刪除。
- **任務：**每筆有穩定身分、名稱、完整敘述及所屬職責；用選擇器或拖曳移到另一職責。未分組任務顯示於「尚未歸入職責」，它是合法 current data，不是 Memory 待辦區。
- **成果與要求：**任務內兩組並列項目，各自新增、修改、刪除及排序；沒有一對一連線，也不自動合併。
- **知識與技能：**各自只有一份完整定義。任務使用 relation selector 加入／解除；總覽從同一 relation 反向顯示「用於哪些任務」。
- **條件與責任邊界：**依工作環境、工時／值班／出差、共通責任與決策、共通協作與交接、必要資格／授權分組；每項仍是可識別列。
- **保存：**一般文字完成輸入、短暫停頓後自動保存，正常保存時可繼續打字；新增、移動、刪除與相關聯的更正，在明示完成該業務操作後整組保存。日常不要求按整份保存。AI 與人有相同完整業務效果及原子邊界，依[業務操作設計](2026-09-12-jd-business-operations-and-scope-design.md)與工具契約；不是逐欄成功便稱整項完成。

### 3.3 Plate 的新角色

整份 JD 不再是一個 Plate value。結構、卡片、關係選擇、移動、刪除及保存由 App 管理。

Plate 只保留為**單一長文字欄位**的 leaf editor 候選，例如任務完整敘述或知識說明；其 value 必須映回該 relational row 的欄位。第一版若只需普通文字與換行，使用標準文字輸入即可，避免為每個小欄位建立 editor instance。是否啟用 Plate leaf editor 由 bounded UI spike 以 IME、paste、selection、undo 與多卡效能決定，不影響資料庫 schema。

## 4. 六章到資料與畫面的對照

| 成品章節 | 目前可寫資料 | 關係／數量 | 主要畫面 |
|---|---|---|---|
| 一、職務基本資料 | 職務名稱、單位／職位、員工姓名（可選）、匯報對象、主要協作對象 | profile 1:1；協作對象 1:N | 表頭欄位＋協作清單 |
| 二、職務目的 | purpose | profile 1:1 | 長文字欄位 |
| 三、主要職責與任務 | duty、task、outcome、requirement | JD 1:N duty；duty 0:N task；task 1:N detail | 職責／任務卡片與子清單 |
| 四、知識總覽 | knowledge 定義 | JD 1:N；task N:N knowledge | 總覽卡＋任務 relation selector |
| 五、技能總覽 | skill 定義 | JD 1:N；task N:N skill | 總覽卡＋任務 relation selector |
| 六、條件與責任邊界 | 五類 condition item | JD 1:N | 分組清單 |
| 文件旁資訊 | revision、operation、source link | 內容 N:N source refs；revision 線性 | 本次改動／歷史／依據 |

物理表可將結構與生命週期相同的 outcome／requirement 放在 `jd_task_detail`，以 `kind` 區分；knowledge／skill 可放在 `jd_capability`，以 `kind` 區分。這不改產品章節，也不讓兩類內容混用。完整欄位與約束見[資料庫設計](2026-09-12-jd-relational-schema-and-write-contract.md)。

## 5. 一次修改的正常流程

### 5.1 員工直接編輯

1. App 依保存契約 §9 取得同一版 current relational projection、關係與 `revision_ref`。
2. 員工在具名欄位、卡片或 relation selector 操作；App 保留具體輸入與候選，按 §3.2 的操作種類觸發保存。
3. 送出前 App 配發 operation identity，固定原 view token 與完整 commands 並暫存；同文件一次只有一個送出中的寫入，後續普通文字另留在本頁候選。
4. server 依固定順序鎖該文件 catalog／head rows，核對 current revision、target、同文件關係與 archived／writer gate。
5. 同一 SQL transaction 修改 current rows，從結果產生 canonical snapshot，新增 revision／receipt，更新 head。
6. commit 確認後，只確認該 submission 涵蓋的輸入，不清除較晚輸入；顯示實際變更並依序處理剩餘候選。失敗回執本身亦須真實提交才 confirmed；回覆遺失先以原 operation identity 查回。細節依[保存／恢復](2026-09-12-jd-autosave-and-handoff-design.md)，不能套用舊保存時鎖住全部文字的實作。

### 5.2 AI 顧問修改

1. 顧問持續訪談；資料不足、只是補充案例或沒有實質變更時，不呼叫寫入工具。
2. 需要撰寫時先以 `jd_read` 取得目前結構與 App-issued refs；最新人工變更由 App 以受限 context notice 提供。
3. 模型只提出完整業務意圖，例如「建立任務及已知成果／要求／K/S」「一起修正正文、要求與錯誤引用」「保留必要範圍並移到職責 B」。一般獨立單欄仍有簡單入口；工具形狀依責任契約，不要求模型填通用任意 command graph。
4. App 注入 document、operation、base/version、stable IDs 及 position，驗證後走與人工保存相同 service／transaction。
5. 工具回傳 committed／no_change／明確錯誤、真實 before/after references 與下一步。模型只能依結果對員工說明。

### 5.3 員工更正後的下一輪

人工保存產生 `origin=manual` 的 revision。App 在下一個模型 request 前比較最後 response-backed model view 與 current head，附上人工事件數、受影響項目、確切 change refs 及有界前後預覽；完整內容仍透過 `jd_read`／`jd_change_read` 取得。這個通知是 App context，不偽裝成員工原話，也不自動寫入 Memory。知道有變動不代表 AI 必須立即改 JD。

### 5.4 JD 與 Memory 持續修訂

兩者都能反覆補充、更正、刪去錯誤內容與整理，直到符合實際工作。顧問依證據決定本輪改哪一項、兩者或先追問，不強制每輪雙寫；Memory 沿既有即時修補與背景整併，JD 沿共同業務操作。App 分開提供真實保存／發布結果，不把一方成功當兩方完成，也不因人工通知直接改 Memory。[責任、來源與驗收](2026-09-12-jd-business-operations-and-scope-design.md#6-jd-與-memory-的反覆修訂)不新增 Memory 引擎、跨系統交易或已停放的額外完成檢查。

### 5.5 歷史、整份還原與重開

Owner 已選歷史對照、局部直接更正及明確整份還原，第一版不加最近一步撤回；零散資料用聊天或未完整任務承接，不加待整理區。依[歷史與恢復設計](2026-09-12-jd-history-and-recovery-design.md)，歷史在同頁唯讀展開，整份還原先看完整影響，再由人工端 `restore_revision` 經共同 domain／保存流程形成新 revision。只還原 JD，保留中間歷史、原始訪談、Memory 與模型已讀基準；下一輪收到新的人工還原事件。

AI 仍可反覆修改；[WS-01 裁決](2026-09-12-jd-agent-workspace-necessity-research.md#7-owner-澄清後的裁決第一版不設持久-ai-試稿區)先不設持久試稿分支，不把單次 App 候選驗證當專業品質保證。取消 AI 不撤銷已保存結果。重開先查原 operation，再處理未提交候選；瀏覽器暫存不是另一份正式 JD，版本／容量／資料集識別尚須工程前置閉合。

## 6. 差異、歷史與來源

- 每個 duty、task、detail、capability、condition 都有穩定 UUID；排序或所屬職責不是身分。
- 當次差異以 operation 的 before revision 與 after revision 比較；按 stable ID 顯示新增、刪除、移動、欄位修改與 relation 增減。
- 移動任務顯示「職責 A → 職責 B」，不呈現為刪除再新增；任務子項與引用保持相同 ID。
- 修改共用 K/S 顯示定義前後及受影響任務清單；不聲稱每個任務都已由員工重新核實。
- 歷史 view 只讀當時 snapshot，使用當時的名稱、定義與關係；不能以 current relation 重新解譯舊版。
- source link 使用既有來源 port 發配、可回讀確切原始問答的引用，Memory 協助查找；裸 Memory 路徑不是永久依據，本輪未建立 Memory-version locator。連結保存目標內容 digest；目標文字改變而 digest 不符時標示「修改前的依據，需重新核對」。這不會自動偵測較新訪談已推翻舊說法，顧問仍核对最新理解。
- AI 摘要可說明這次改了什麼，但不能取代可展開的 actual diff。

## 7. 刪除與關係生命週期

### 7.1 已形成的設計

- **刪任務：**推薦在確認畫面列出任務擁有的成果／要求數量及 K/S link 數量。確認後同交易刪除任務、其成果／要求與 relation rows；共享 K/S 定義保留。歷史 snapshot 仍可查看被刪內容。
- **刪成果／要求：**只刪指定 item，不影響同任務另一組或其他項目。
- **刪 K/S：**若仍有任務引用，DB `RESTRICT`；畫面先列出引用任務，員工明示解除或改接後才能刪。不能因刪任務的一條 link 刪除共享定義。
- **刪整份 JD：**不在本版；文件只提供封存／恢復。

### 7.2 D01 已決：刪職責、保留任務

Owner 已授權研究者裁決，採[需求 §8](2026-09-12-jd-relational-editing-requirements.md#8-d01刪除職責時保留任務2026-09-12)的任務保留政策；[AWS 與 PostgreSQL 依據](evidence/2026-09-12-jd-relational-editor-evidence.md#7-aws-業務邏輯與-d01-裁決依據2026-09-12)支持依物件獨立性分開生命週期，不宣稱通用的刪父留子規範。

- 員工刪除職責後，原任務出現在「尚未歸入職責」，可繼續閱讀、編輯、重新歸類及匯出。任務 ID、敘述、成果／要求、K/S links 與各自 source links 保留；不連帶刪除工作。
- App 對人工與 AI 使用同一完整業務操作：解除該職責任務的分組、按既有順序規則放入未分組清單，再刪 duty；current、實際差異、snapshot／head 及成功 receipt 同交易提交。工具不逐項要求模型搬任務或選 SQL 模式。
- DDL 保留 `RESTRICT`，阻止漏做解除關係的直接刪除；不是將正常刪職責繼續當成待選政策。職責自有 current source links 隨目標移除，歷史保留當時原文／來源；若需把仍有效條件保留到其他欄位，必須明示調整並重新核對來源，不自動改掛。
- 刪除影響列出職責名稱／說明與受影響任務；任務卡保留任務特有必要範圍，職責只作概括。需調整時，同一候選改相關欄位或新增成果／要求，再解除分組／刪 duty；來源不自動轉掛。依[受權裁決與固定例子](2026-09-12-jd-business-operations-and-scope-design.md#3-r05-裁決必要範圍隨任務職責摘要不產生繼承)，App 驗關係與原子性，員工／顧問核含義；不把歷史保留當目前稿保真。JR-R05 文件複核結果另見 evidence，產品實測未執行。

## 8. 匯出能力的設計位置

relational current projection 可確定性轉成不同輸出，不讓 LLM 生成 Excel：

1. application service 讀指定 current revision 或歷史 snapshot；
2. export mapper 將 duty/task/detail/capability relations 轉成輸出模型；
3. renderer 產生 iCAP、公版或一般 JD Excel；位置碼、欄寬與合併儲存格只在 render-time 生成，不回寫業務 rows。

本輪只保證資料能無損投影。輸出種類、欄名與版型仍 OPEN，沒有宣稱下載功能完成。舊 iCAP XLSX renderer 可當測試 oracle／版型研究，不直接接回 retired packages。

## 9. 責任分工

| 負責者 | 必須做 | 不做 |
|---|---|---|
| AI 顧問 | 理解工作、判斷撰寫時機、選 issued target refs、撰寫文字、選既有 source refs、依錯誤重讀或停止 | 生成 document／operation UUID、SQL FK、position、revision、保存成功或任意 line number |
| App／application service | current projection、command mapping、ID／version／position、domain validation、transaction、receipt、人工變更通知、diff/export projection | 猜員工工作、把 tool call 當已完成、把人工文字偽裝成 AI 來源 |
| PostgreSQL | row identity、同文件 FK、junction uniqueness、delete restriction、atomic commit、head lock、durable current/history/receipt | 判斷文字專業品質或資料是否足夠撰寫 |
| Web | 結構化卡片、未保存 buffer、清楚操作／錯誤、actual diff/history/source 呈現 | 自行修外鍵、重算 authority、以 client disabled 當 server 安全 |
| Plate（如啟用） | 單一文字欄位的 selection、IME、paste、undo／redo 與富文字 transforms | 整份 JD schema、跨卡 CRUD、關係、DB 保存及歷史 authority |
| 員工 | 提供自身工作、指出誤解、可直接編輯及確認刪除影響 | 判斷專業 JD 寫作是否完整或維護資料庫關係 |

此分工參考 [AWS ports／adapters 與命令處理](evidence/2026-09-12-jd-relational-editor-evidence.md#7-aws-業務邏輯與-d01-裁決依據2026-09-12)：人工與 AI 的輸入接點可以不同，domain rules 與保存效果共用。只採所需分層，不因此加入 AWS 服務、微服務或另一個資料權威。

## 10. 失敗與恢復

| 情況 | 結果與出口 |
|---|---|
| 參數形狀錯誤 | strict schema／server validation 拒絕；回 `invalid_input` 與可修正欄位，不執行 DB mutation |
| target 已不存在 | `target_missing`；模型或 Web 重讀 current，不猜新 ID |
| 人／AI 基底過時 | `stale_view`；不部分套用，保留人工 buffer；AI 可重讀一次再重新決定 |
| 關係跨文件或類型錯誤 | `relationship_conflict`；不自動改接相似名稱 |
| 刪 duty，仍有 tasks | 依 D01 由共同業務操作保留任務並解除分組；不能僅因有任務就回待選政策。職責共通條件的保存前置及錯誤出口仍由 JR-R05 補齊 |
| K/S 仍被引用 | `dependent_items`；列出引用任務，依既定明示解除／改接流程處理 |
| SQL transaction 明確失敗 | 正文保持不變；只有失敗回執實際提交才 confirmed。原 operation 已綁定但尚無確認結果，先 reconcile；分支依保存契約 §6.2–7 |
| commit 結果未知／回覆遺失 | `outcome_unknown`；以原 operation identity 對帳，不用新 key 重做 |
| 已有相同 operation、相同 payload | 回原 receipt，不再套用 |
| 已有相同 operation、不同 payload | `operation_conflict`；拒絕覆寫原結果 |
| AI run 進行中 | 同文件人工手改暫停，仍可閱讀；停止後先閉合 writer／receipt 才恢復 |

寫入不做無界自動 retry。`stale_view` 的重讀不是重播原寫入；`outcome_unknown` 只能對帳同一 operation；invalid input 可由模型修一次，仍失敗就停止並告知。

## 11. 驗收情境

1. 新建兩個職責與三個任務；一個任務保持未分組。
2. 任務 A 從職責 1 移到職責 2，ID、成果、要求、K/S links、source links 均不變；歷史顯示 move。
3. 同一知識供兩任務使用；修改定義後兩處顯示新內容，歷史仍解析舊定義；解除一條 link 不影響另一條。
4. 刪一項成果不影響同任務要求；刪任務保留共享 K/S。
5. D01：人工與 AI 刪除含兩任務的 duty，兩任務保留為未分組，未受修改的從屬內容及各自來源不變；職責自有 current sources 無懸空引用，歷史可回查。故障不得只解除一半分組；繞過 command 直接刪含任務 duty 則被 `RESTRICT`。依業務設計固定例子核「維護限服務約定」、安全確認及維修紀錄交付：必要時同次修正文／新增正確子項，不能只驗資料列存在。
6. AI 寫→員工手改→下一輪純訪談；模型 request 能看到人工變更 notice，但沒有新的 JD revision。
7. 人工 batch 的第二步故障，current rows、revision、head 全無部分更新。
8. commit 回覆遺失，以原 operation 找到 committed receipt，不重複新增。
9. 繁中、換行、重複文字、相同名稱 K/S、reorder、selection ask-AI 皆以 stable target 處理，不用行號。
10. 重開 App 後 current relation、歷史 snapshot、原始問答與 Memory scope 一致。
11. export projection 能將完整樣稿轉成中立表格模型；尚未選定的實體 Excel 版型不列 PASS。
12. **反覆修訂完整旅程：**訪談先釐清一項工作並形成初稿 → 員工補充另一工作 → AI 保留原有有效內容並新增 → 員工更正第一项工作的責任邊界 → AI 修正受影響的敘述、要求及引用，不抹去第二項工作 → 員工手改並保存 → 關頁重開續談 → AI 得知人工變更、取得最新版，資訊足夠時再修訂。同一工作不因多次改寫重複新增；每次實際改動可查、過時內容不當成現行工作；純追問／重述回合可不產生 JD 修訂。固定操作只驗資料與操作保真，自然訪談另驗理解、更正及內容完整性；沿[需求 §7](2026-09-12-jd-relational-editing-requirements.md#7-功能目的與使用方式釐清2026-09-12持續討論)，不將初稿或固定流程成功稱為完整個人化 JD。

## 12. 本輪不做與重開條件

追加業務驗收由[完整操作 §5](2026-09-12-jd-business-operations-and-scope-design.md#5-固定驗收與停止條件)及[JD／Memory §6](2026-09-12-jd-business-operations-and-scope-design.md#6-jd-與-memory-的反覆修訂)負責：包含新增整組失敗、正文＋要求＋引用共同修訂、UTF-16 選取、最終候選驗證與两種保存結果交叉，不以舊 Plate 測試代稱新版已通過。

不做登入／ACL、多租戶、多人即時協作、CRDT／OT、雲端同步、RAG、舊資料搬移、永久刪除、真人顧問權限或特定 Excel renderer。自然模型品質與員工試用仍依成品計畫另驗。

若外部 review 證明 derived snapshot 無法在同交易保持一致、generic source link 無法提供足夠完整性、Plate leaf editor 對 IME／undo 不成立，或 D01 選擇改變資料生命週期，回到本設計修訂。沒有具體反證時不重開整份關聯方向。

下一步：本輪完整業務操作、範圍與選區的文件反例已修訂，依[複核紀錄](evidence/2026-09-12-jd-business-operations-review.md)確認局部閉合；接續未歸任務草稿、保存後撤回／歷史分組與暫存恢復等真正未決效果。整體 G4 與 Proposed ADR 未通過，尚不能開始正式 migrations。
