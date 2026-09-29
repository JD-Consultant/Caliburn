# 業務、資料及契約接線

- 狀態：**工程設計／分切片施工中**。T02 的檔案與開場保存見[實際接線](interview-storage.md)；其餘依任務表，不因此宣稱 JD／Memory／執行均已實作。不在此預先列所有資料表；表名、索引與 DDL 由任務依測例實現並留下 schema 圖。
- 語意權威：[資料保存與交易](../architecture/persistence.md)、[Memory 生命週期](../specs/2026-09-25-b1-b2-information-gap-lifecycle.md)、[JD 工具](../specs/2026-09-29-jd-model-tool-contract-review.md)。本頁只說接線方式。

## 1. 一個 service、一個正式結果，兩種入口

人工 HTTP 與 Agent tool 各自轉譯輸入，呼叫同一領域用例。服務輸入包含 App 綁定的檔案／執行資格、解析後的內部目標、型別化修改與原操作辨識；模型不填這些執行值。返回 typed result，再分別投影為 HTTP DTO／精簡工具文字，不以模型可見 `updated` 作資料庫收據。

API 接受的 client command ID 用於辨認瀏覽器重送同一命令；模型 `call_id` 用於 function output 配對；業務 operation ID 用於重入查回原效果。用途分開，但不強制三張表或三套 registry。operation identity 在派送前可恢復，重入不重新解析改名後的 target_title。

## 2. SQL／交易責任

單庫短交易預設從 PostgreSQL Read Committed＋顯式條件／短行鎖開始驗證，不以 Serializable 包住整輪。跨列不變量以唯一鍵、FK、檔案／候選控制列鎖或條件更新保障；Serializable 只有具體反例需要時局部採用，serialization failure 由原操作重試而非重跑 LLM。所有可見資料均檢查 job_file scope。

業務服務定義「一次必須成立什麼」，SQL adapter 實現原子性；工作流開短交易、相關服務參與同一 session，內層不提交。模型、串流、PDF、等待使用者、重試 backoff 期間不得持有該交易。DB pool connection 與 Graph checkpointer connection 各自管理，不能假設 saver 與業務共享 transaction。[PostgreSQL](https://www.postgresql.org/docs/current/transaction-iso.html)、[SQLAlchemy async session](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks)

**每筆具副作用操作的共同接法：**

1. 先以 scope＋原操作身分查已成立結果；有結果就校驗原 payload 一致並回它，不拿 latest 代替。
2. 未能確認時不能當未執行。取得本操作所需的資格／短鎖，重新查原結果，排除仍在途或舊 writer。
3. 校驗執行仍有效、候選位置／權限及該領域不變量；在記憶體暫算修改。
4. 同一交易保存候選位置、效果及原結果；COMMIT 確認不明再查原操作。相同 ID 不同內容拒絕。
5. Graph 接回該結果；Graph 落後不重新產生業務效果。

不把這五步造為任意任務都可回滾的框架。共用 transaction／operation plumbing 可抽小函式，領域命令與 validator 仍各自維護。一次修改多欄全成／全拒；一 Step 多筆工具是多筆操作，不能誤稱整 Step 一個 DB transaction。

## 3. Memory：可變工作稿與固定快照不是兩個相反模型

候選的關係連 stable object ID；工具 title 先在有權的當前 layer map 精確解析，取得 ID 後才對該物件操作。改名先固定目標再改；同層有效 title 唯一，歷史／不同層不作同名限制。新命令使用重用名稱時選目前物件；**沒有「模型一定知道舊名」的保證，也不追加被否決的強制 read proof**。原操作重入與歷史引用均維持原 identity。

候選每次有效操作有可恢復的位置；position 可由不可變修訂選用或可復原 checkpoint-linked 快照實現，但只有領域是可寫 owner。刪情境同次移除候選理解指向它的 bindings，不刪理解；歷史快照不變。B1 只能改情境；B2 只能改理解，讀目前固定交接的情境；權限在 service 再驗，不只藏 tool。

發布演算法用固定候選位置，不讓 LLM 處理版本：

1. 確認原發布操作、有效批次／階段及 B2 完成資格；這是權限與併發 gate，不是再請模型審格式。
2. 固定本批正式訪談範圍，依有效候選選出所有情境。內容／來源未變的重用原修訂；變動建立新修訂。
3. 將理解中的候選 bindings 解析成上步選定的情境修訂。即使理解文字未變，只要固定引用改變也建立新修訂。
4. 在單一短提交邊界保存 Memory snapshot 的選用、固定關係、涵蓋邊界及原發布結果，再前移正式 head。

凍結正文的大額純計算可先在交易外對固定位置完成，提交時再核位置／資格，不能用未鎖定的 latest 拼成快照。未變物件重用，改回舊文字仍是新修訂；不要求整版物件共用版號。來源集合可空，候選合法性每次操作即維護，不在發布時新增最少引用數。

每個正式 snapshot 的 maps 都由其選用投影，任何路徑到同一物件均同修訂。所有已發布且供 A／JD 使用的可達資料保留；舊候選只按恢復／diff 需求保存，不實作 Git delta 或永久事件重播。B2 看的是當前候選＋交接 diff，不提供任意舊版全文工具，不要求逐筆 confirm_reference_alignment。

## 4. JD：關聯式候選、來源與正式完成

JD 業務沿既定 profile／職責／任務／成果／要求／知識／技能／關係建立型別模型；schema 不從 Memory Markdown 或 UI widget 反推。欄位意義依[JD 指南](../specs/2026-09-09-jd-field-and-writing-guide.md)。舊 SQL／測例只供參考，沒有相容表名義務。

T03 已實作的 profile、職責／任務、共用知識／技能及任務關係、協作對象／共通條件人工端點與 UI、固定修訂、原結果及交易見 [JD 保存接線](jd-storage.md)；候選及本節其餘未交付項目仍依任務施工，不能將人工正式 API 當作 A 候選寫入。

JD `read_ref` 解到本輪 JD identity／型別與合法內容基準；Memory `target_title` 解到本輪固定 snapshot 內 identity。existing `citation_ref` 解到 JD 自己保存的特定來源，不用同名猜舊來源。直接來源可選正式訪談、情境、理解或 current_input；pending current_input 僅在 A 完成交易取得正式來源資格。

保留「來源修訂」與「核對時 JD 內容基底」兩種依據：來源沒換，但使用者改了該 JD 內容，原確認也不代表已核對新內容。待核對依當前 JD 與本輪可見來源推導，不建永久通知副本。

- `read_jd_changes(manual)` 比上次成功 A 的正式 JD 到本輪起點，原人工操作可辨「改過又改回」；不是員工事實。
- source diff 以 citation 固定舊來源到本輪 pinned Memory 同身分新來源，展開相關引用鏈變化；舊正文只作 diff 材料，不給任意歷史閱讀入口。
- `confirm_reference_alignment` 只對指定 JD 依據與目前內容基底成立；讀 diff、更新文字、重加既存來源不能自動確認。刪除／同名新建不冒充同身分。

完成 A 由 workflow 協調 **JD 候選、有效訪談與序號、完整正式答覆、current_input 來源解析、完成結果、背景要求上界**同次提交。序號使用檔案內受交易保護的分配，不直接依會跳號的全域 sequence 保證取消不佔號。完整已公開中間訊息另按回看政策保留，無正式序號、不作依據。

取消只使該輪候選／來源／後續寫入失效，回有效基底；不是把已提交的外部修改反向逐筆 undo。A 暫停／活躍時，人工 JD 寫由後端拒絕；正式完成後的 JD 撤回則是獨立條件命令，不撤回訪談／Memory。

## 5. 唯一契約來源及生成

新目標 `apps/api/contracts/http/` 保存跨語言 DTO，`contracts/tools/` 保存模型可見 schema。Schema 與描述按業務拆，不每參數一檔。鎖定 datamodel-code-generator 產 Python DTO，json-schema-to-typescript 產 TypeScript；OpenAPI 從 API 的生成型別形成，不再手寫 OpenAPI／TS／Pydantic 三份 shape。HTTP／tool 邊界仍做執行時驗證，TS 型別不代替它。[現行策略](../contract-strategy.md)的原則保持，路徑不同不接回退役 package。

模型 schema 與 HTTP 不強求相同：HTTP 需要保存／預覽狀態，tool 只回推理下一步所需資訊。模型 strict wire 是薄編譯邊界：有限 variants、required／additionalProperties 按 provider 子集，語意上未列 change 仍是保留，不把 null 當清空。生成後以真 SDK payload 驗，而非只測 Python class 建得出來。

原始 Responses items 不塞進自製 message schema；按官方 SDK output→input 轉換後保留必要 metadata、opaque bytes 與順序，兩種方向各有 round-trip 測例。生成檔不手改；CI 再生成比 diff。新 schema 尚未產生前，本文不宣稱任何 wire 已完成。

## 6. 資料演進與恢復

新產品使用新的 PostgreSQL database／schema namespace 與 fresh migrations，沒有舊資料 ETL。Alembic autogenerate 是候選 migration，需人工／Agent 審閱及真 PG 空庫升級測試；它不自動理解所有 rename 或 data change。[Alembic](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)

首版不自動清理候選／checkpoint，也不新增備份產品；保留邊界仍需可測。新 migration 前 fail fast 檢查 DB 版本與配置；schema 不相容不得帶著半套表啟動。框架 saver schema 用官方 setup／upgrade 路徑，不在業務 Alembic 中手抄其結構。

取消與最後提交使用相同持久資格裁決；重啟時舊 runner 的資格不得沿用到新 attempt。租約／fencing 具體 SQL 由 T02／T08 依兩連線反例選擇，不把 Python mutex 當跨程序保存保證。未知 COMMIT 要對帳，不能因查詢超時便把目前表頭回退。
