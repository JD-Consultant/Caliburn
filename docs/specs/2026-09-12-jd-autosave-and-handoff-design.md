# JD 自動保存、人工輸入與 AI 交接設計

- 日期：2026-09-12；Topic：JD-R002/C02、C03。
- 效力：Owner 已同意[保存方向](2026-09-12-jd-relational-editing-requirements.md#9-保存方式重審自動保存已選定2026-09-12)；本稿是 G4 可驗證細節，尚未實作。正式權責仍按 ADR0060，ADR0075 保持 Proposed。
- 分工：[官方產品研究](2026-09-12-jd-autosave-research.md)保存選項；[資料庫契約 §6–9](2026-09-12-jd-relational-schema-and-write-contract.md)負責唯一正文、交易、回執與一致讀取；本稿只負責觸發、輸入保留與交接，不再定義第二份 SQL 或工具 schema。

## 1. 補充官方證據

查閱日均為 **2026-09-12**。官方事實與本案映射分列；不是宣稱以下廠商使用相同表數、等待秒數或 JD 操作。

| 來源／適用版本、狀態與授權 | 官方事實 | 本案映射與限制 |
|---|---|---|
| [AWS idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，Builders' Library 現行方法文章，非版本化 API；只參照文件、不採 AWS 服務或複製程式 | caller token 表達同一意圖；token 與效果需原子記錄；相同 token 不同參數不能當同請求 | 原 operation／payload 固定，結果不明先查回。兩次相同文字操作未必同意圖；不只用內容雜湊當請求身分 |
| [AWS Java 2.x Enhanced Client extensions](https://docs.aws.amazon.com/sdk-for-java/latest/developer-guide/ddb-en-client-extensions.html)，現行穩定 SDK 2.x 文件；本案不安裝 Java SDK | VersionedRecordExtension 用版本條件保護更新；deleteItem 不因 version annotation 自動保護，須明加条件 | 驗讀取版本的原則也用於刪除／移動。本案實作為 PG 的鎖內 base 檢查，不照搬舊版 DynamoDBMapper 或 DynamoDB 資料格式 |
| [AWS SDK retry behavior](https://docs.aws.amazon.com/sdkref/latest/guide/feature-retry-behavior.html)，現行文件的 2026 行為須 `AWS_NEW_RETRIES_2026=true` opt-in，尚非所有 SDK 無條件預設；非新增依賴 | 重試依錯誤分類、有限次數、退避及額度控制；不同模式有不同影響 | 沿本案未知先對帳，不開所有 mutation 的自動重送；沒有設定該旗標，也不把 SDK 行為說成 App 已具備 |
| [AWS hexagonal application change](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/adapt-to-change.html)，現行方法指南；只參照架構原則 | 不同入口可經 application commands 使用業務核心；可只採所需命令處理，不必完整 CQRS | Web 與模型共用完整業務操作、驗證與保存；不新增微服務、事件匯流排或讀寫雙資料庫 |
| [PG16 isolation](https://www.postgresql.org/docs/16/transaction-iso.html)、[SAVEPOINT](https://www.postgresql.org/docs/16/sql-savepoint.html)、[ROLLBACK TO](https://www.postgresql.org/docs/16/sql-rollback-to.html)，本案指定穩定主版本；PostgreSQL License | 多次查詢的快照受 isolation 控制；回到 savepoint 可撤候選而保留外層交易，仍需 COMMIT | 一致讀取用短唯讀 REPEATABLE READ；寫入及停止後對帳用 READ COMMITTED。failure receipt 另在同外層交易提交，不能以 rollback 本身代稱已保存結果 |
| [MDN IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API/Using_IndexedDB)、[storage quotas](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)，現行標準 Web API 文件；文件 CC BY-SA，只摘要引用 | IndexedDB 支援非同步交易；交易完成與單項 request 成功不同。瀏覽器暫存受配額、清除及持久性限制 | 候選採單一瀏覽器恢復記錄；等待交易完成才稱已暫存。它不證明 PG 保存成功，也不能承諾最後按鍵斷電不失；不採非標準 readwriteflush |

OpenAI／ChatGPT 的目前文字編輯保存、apply_patch 的 App 執行回報，以及 Anthropic／Claude 的迭代與 tool result 接法，沿[研究 §2](2026-09-12-jd-autosave-research.md#2-官方證據與適用範圍)與[工具契約](2026-09-12-jd-relational-agent-tool-contract.md)。共同原則是更新已知內容、回報實際效果、減少不必要的模型參數；廠商未公開的內部自動保存協定保持未知。

## 2. 員工看到的保存單位

| 操作 | 觸發與效果 |
|---|---|
| 一般既有文字欄位 | 中文組字完成、短暫停頓後保存最新已完成輸入；離開欄位可提前排程。正常背景保存可繼續打字。延遲／最長待存時間是互動驗證參數，不是大廠統一數字 |
| 新增任務、成果或要求 | 在原頁完成該新增動作後，已填的有效內容一次提交；尚未完成時保留候選。不先存假名稱或必填空殼，再強迫員工／模型補寫 |
| 移動、刪除、選擇引用 | 看清影響並完成明示操作後，一次保存完整效果；拖曳經過或選單選到一半不提交 |
| 同一更正涉及多個欄位／要求／引用 | 以一個明示完成的業務操作整組提交；不能僅靠停頓推斷各欄已互相一致。範圍與模型入口依[完整業務設計](2026-09-12-jd-business-operations-and-scope-design.md)，不把一項更正拆成多次自動保存 |

自動保存只保存當下工作稿，不認證內容完整。一般日常輸入無整份「保存」步驟；若提供立即保存快捷入口，只會提前執行同一排程。已提交的改動不因關頁或取消表單而消失。

## 3. 保存中繼續打字：有限狀態與資料

每個 document 的頁面 session 只有一個送出中的寫入；其他文件不共用全域寫入鎖。App 區分以下用途，並不呈現兩份可編 JD：

| 材料 | 用途 |
|---|---|
| 已確認基準 | server 回的版本與正文；唯一已保存事實 |
| 畫面輸入 | 員工正編的具名欄位及未完成新增候選；含本頁遞增的輸入序號，不是 server 版本 |
| 固定送出記錄 | 原 document／operation／base／完整 commands 及其涵蓋的輸入序號；送出後不可被新輸入改寫 |

正常順序：

1. 員工输入由頁面記錄。只有有效且已完成的編輯單位可進保存排程；IME composition 中不得送出半個字。欄位無效時保留原輸入，標示原因，不用空字串或自創文字替換。
2. 排程擷取一次固定內容 A、配發原 operation，先完成 §5 的固定送出記錄暫存，再發 request。A 完成前不得另外發 B；使用者可繼續輸入 B，新的序號與候選保留。
3. 收到 A 結果時，同時核 document、session generation、operation identity；舊頁或其他文件結果不可更新目前頁面。只有 confirmed committed／no_change 可承接已確認基準。
4. A 只確認其涵蓋的輸入，不清除序號更大的 B。對同一文字欄，保留 B 的最新全文；不可拿 server A 投影重設整份表單。即使 B 恰好改回 A 之前的文字，仍按真實現在輸入比較，不靠 dirty 布林猜測。
5. A confirmed 後，將已確認基準與剩餘 B 的恢復記錄原子更新；再從此基準為 B 形成**新的** operation。這只適用於本頁已確認的前一保存所帶來的版本承接，且 B 的目標及結構前提仍成立。若 current 已被其他入口改動，依 stale 流程重新比較；不可任意把舊命令換 latest base 自動套用。
6. 一般背景保存只允許後續普通文字留在 buffer；結構操作要開始前，先完成現有文字保存與結果確認，再作該操作。送出結構修改期間暫停可能受影響的管理操作，避免 B 指向剛被刪除／移走的未確認結構。這是本版有界交接，不建立通用 command rebase 引擎。

UI「已保存」要求：所有目前畫面可保存輸入皆已確認、沒有更晚 dirty、沒有未知 operation。A confirmed 但 B 尚未保存時，仍顯示尚有未保存內容；不得用 A 的成功橫幅表示全份已保存。

| 結果 | App 接續 |
|---|---|
| 已確認成功／no_change | 只承接對應內容；有 B 才繼續下一保存，沒有則顯示已保存 |
| 已確認語意拒絕或 stale | 保留候選，停止該組自動提交，指出欄位／需要重新比較；不每次 timer 重送相同錯誤。員工修正後才能形成新意圖 |
| 正文已知未改，但原 receipt 未確認 | 保留原 A 與後續 B，先由 App 沿原 operation 閉合；不能先另發 B 或叫 LLM 改參數 |
| 寫入結果未知 | 顯示正在確認保存結果，唯讀查詢／明示恢復沿既有契約；不將舊 A 自動 replay，不顯示已失敗或成功 |
| 本機服務不可用／恢復失敗 | 保留可找回輸入，顯示具體原因及查詢／恢復出口。停止新寫入，其他文件按各自可用狀態處理 |

## 4. 與 AI、匯出及離開操作交接

**送出聊天：**先完成正在組字的輸入；組字尚未结束的送出動作不觸發模型請求。員工明示送出後，頁面暫停手改並使舊 autosave timer 失效，等待 A，然後保存仍待存的有效 B。若未完成新增／組合候選或無效欄位阻止交接，保留聊天草稿，提供完成該項或明示捨棄未提交內容的出口；不默默略過它送模型。這期間尚未呼叫模型或送出聊天。

全部 JD 修改 confirmed 後，App 以該版本請求既有 run admission。server 在同文件 gate 下核 head 仍符合預期，才建立 AI turn／writer ownership；不只相信 Web disabled。若不符，保留聊天並要求重新載入比較；若聊天請求已送出而回覆未知，依**原聊天 request identity**查回，不能新建另一回合。取得 writer 後，模型上下文沿[工具契約 §8](2026-09-12-jd-relational-agent-tool-contract.md#8-人工修改如何進下一輪-context)讀一致版本與人工變更。前景回合完成／取消並確認 writer 結束後，才恢復手改。

此交接不要求 LLM 填版本、判斷是否存好，或每輪重寫 JD。手改保存事件不是員工原話，也不自動寫進 Memory。模型服務離線但本機 API／DB 正常時，手動管理仍可使用。

**匯出目前稿：**先完成同樣的 JD 保存交接，再取得指定確切版本的 projection 供 Excel renderer；若保存失敗，不以舊版冒稱最新版。歷史版本仍可明示選取閱讀／匯出，但不新增第二份可編正文。

**歷史、切文件及封存：**同頁歷史可唯讀展開。正常切文件或封存先等待已送結果並處理未提交候選；有未解結果時提供留在原頁／查看狀態／恢復的出口。封存仍經 server gate，不能跳過 pending writer。正常關頁以尚未保存提醒輔助，不能依賴 beforeunload 完成最後保存。重開依 §5 恢復。

## 5. 瀏覽器暫存與重開

**候選選擇：單一 IndexedDB 恢復記錄**，同一記錄容納固定 submission 與較晚候選；不再同時把兩者分別保存為互不一致的 localStorage 正文。採原生非同步交易能力、每個 session／document 只保留目前必要恢復材料，成功無剩餘候選後清除。本輪只定責任與更新原子性；儲存 schema／版本上限及元件接線須在 UI 施工前完成有限驗證，不沿舊 localStorage 實證直接標通過。

- 瀏覽器以 origin 隔離；記錄另綁 server 發配的資料集身分、document、session 及 draft format version。資料集身分是非秘密的安裝／還原相容性識別，具體沿正式 catalog／備份設計閉合；未核對身分前只能顯示可恢復內容，不能套用另一資料集。不可存 DB DSN 或金鑰。
- 普通輸入有界暫存；送出 A 前先以同一 IndexedDB transaction 保存其不可變請求與當時候選，交易完成才發送。收到 A 後將確認基準、清除的 submission 及剩餘 B 一起更新，避免重開後只剩不相符的一半。不得跨網路 request 持有 IndexedDB transaction。
- **所有恢復記錄更新共用同 session／document 的串行入口**，包含普通暫存、送出固定請求及處理 confirmed 結果；不能各自擷取舊整筆物件後異步 put。入口按目前 record generation／submission identity 處理狀態轉移：普通暫存只更新候選且不覆蓋更大的輸入序號，不能清除 submission；清除 submission 只接受匹配原 identity 與目前階段的 confirmed 結果。A 確認更新在實際開始儲存時合併當時最新剩餘候選 C，不能把先前擷取的 B 寫回蓋掉 C。只比較 input seq 不夠，因為候選與固定 submission 可以有相同 seq。這是本頁恢復記錄的不變量，不將所有文件或 server 寫入串成全域鎖。
- 寫暫存失敗時保留記憶體內容並提示「尚未保存，恢復暫存不可用」；固定 submission 尚未記好時不發送，不假稱重開一定找得回。已存在的原請求保留，不能為騰空間清掉未閉合記錄。
- 重開先讀 server current 與原 operation 結果；有固定 submission 先對帳。只有候選時，在同頁呈現找回的文字與目前版的差別，讓員工明示繼續或捨棄；不自動重播。其他 session 的候選另列來源，不能自動合併覆蓋。
- 候選已過時、目標被刪、版本不相容或資料集不同時，不自動改 base、按名稱配對或清空記錄；保留可讀內容並說明不能直接套用。無快取也不能由「查無待處理」推斷舊寫入未發生，仍沿[原恢復契約](2026-09-10-jd-manual-recovery-transport-design.md)。
- 暫存成功只顯示可恢復候選，**「已保存」專指 server／PG 確認**。瀏覽器被清除、儲存不足或程序／電源中斷不能承諾最後每個按鍵保留；已確認 JD 則由正式 DB 備份機制保護。

這是為未保存輸入與不可變 request 提供有限恢復，不新增可離線自行決定正式版本的同步系統。IndexedDB 選擇仍須通過目標瀏覽器驗證；若其實無法改善既有有限 cache，回報證據與替代，不自行擴成通用離線引擎。

## 6. 必要驗證與未決項目

以下全部 **未執行**；文件走查或官方 API 存在均不代表功能通過：

| 情境 | 通過條件 |
|---|---|
| A 送出後輸入 B，A 晚到；B 改回最初文字 | B 不被清除；只在全數確認後顯示已保存；歷史與人工事件保留真實次序 |
| IME 組字、取消組字、換行、連續輸入 | 不保存半字、不吞輸入；排程可在有限時間完成，無效文字留在原欄可更正 |
| A 成功後 B 保存遇到其他入口改版 | 拒絕過時，不自動 rebase 或覆蓋；保存目標、欄位內容可比較 |
| A timeout、failure receipt 失敗、COMMIT 回覆遺失 | 不發 B、不換原 key；依實際回執／停止與 DB 邊界證明閉合 |
| 保存中送聊天／切文件／封存／匯出 | 交接一致、原聊天不重複；沒有跨文件、漏手改或舊版冒充最新 |
| IndexedDB abort／quota／重開／舊 session 回覆 | 不假稱 PG 已存，不丟掉晚輸入；不自動套用另一 session 或資料集 |
| A 確認回存 B 晚於 C 暫存；舊普通暫存晚於固定 A 請求 | 重開仍有 C；原 A identity 不被普通暫存抹掉。更新序列及 submission 階段與記錄一致 |
| 讀取 r5 時 writer 提交 r6；跨頁讀 | 完整同版 projection／refs；過時 cursor 要求重讀，沒有混版 |
| 複合命令第二步失敗 | 正文回 base，只留下實際確認的 failure receipt；查不到時不以新意圖重做 |
| 長輸入與多次保存 | 記錄保存延遲、版本增長與可讀性；不為美化歷史刪除實際保存證據 |

**仍須閉合：**自動保存後的整項撤回、歷史顯示分組，以及暫存 schema／容量／資料集識別。JR-R01／04／05 已通過[完整操作文件複核](evidence/2026-09-12-jd-business-operations-review.md)，R02／03 另見[審查結果](evidence/2026-09-12-jd-relational-editor-needs-and-design-review.md)；這些均未執行新產品實測，不因保存方向同意推定全部完成。

下一工作把未完整草稿、保存後撤回、歷史與恢復用同一份樣稿說清楚；沿已定完整業務操作，不補造條件繼承／通用回退引擎。
