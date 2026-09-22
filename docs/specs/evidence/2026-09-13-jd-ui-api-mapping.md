# JD 結構化 UI 與既有 API 接合核對

查閱／實測日期：2026-09-13。範圍為 `experiments/jd-relational-app` 隔離 App 的 RS-3 接線；不是 production authority 切換。本文件保存實際契約映射與本輪補上的讀取識別，不另定 JD 格式或建立第二份 DTO。

## 1. 依據與本輪決定

正式輸入／輸出來源為 [jd-read.schema.json](../../../experiments/jd-relational-app/contracts/jd-read.schema.json)、[jd-work.schema.json](../../../experiments/jd-relational-app/contracts/jd-work.schema.json)、[jd-manual-http.schema.json](../../../experiments/jd-relational-app/contracts/jd-manual-http.schema.json)、[jd-catalog-http.schema.json](../../../experiments/jd-relational-app/contracts/jd-catalog-http.schema.json) 與 [jd-result.schema.json](../../../experiments/jd-relational-app/contracts/jd-result.schema.json)。Web 匯入 [generated](../../../experiments/jd-relational-app/src/jd_relational/generated) 的 TypeScript 型別；不可手抄另一份對外介面、解碼 opaque ref 或在 Web 重算 domain invariant。

UI 調查發現，原 `item_ref` 同時綁定文件、資料集、版本及用途，保存一次即更換；`position` 也可能隨移動更換。兩者不能作跨版本保留欄位狀態的穩定身分。

**官方事實：**React 現行文件說明，同一項目應使用來源資料中的穩定 key；資料庫資料可使用其 ID。排序、插入或刪除時以 index 或每次產生的新 key 配對，可能誤接元件或丟失輸入。查閱頁標 v19.3；這是 React 公開穩定 API 的規則，非對其他產品內部實作的猜測。[React：Rendering Lists](https://react.dev/learn/rendering-lists#keeping-list-items-in-order-with-key)。框架版本、免費開源授權及採用範圍沿 [RS-3 前置](2026-09-13-jd-react-ui-preflight.md)。

**本案最小接點：**

| 欄位 | 來源與用途 | 明確界線 |
|---|---|---|
| `SectionRecord.section_key` | App 的既有六章 key：`profile / purpose / duties_tasks / knowledge / skills / conditions` | 章節導航與固定欄位歸組；不是新 section 寫入定位 |
| `ItemRecord.item_id` | 原 DB 的 canonical UUID 字串；改字、移動後保留 | 同 dataset＋document 內辨識同一筆內容；不是授權、版本 proof 或 command 參數 |

顯示身分、位置與可寫 ref 分開。清單 key 可用 `item_id`，文件／資料集需在外層元件或草稿儲存 scope 隔離。單欄位以同 item ID＋既有欄位名配對；profile 欄位以章節＋欄位名配對。這只讓 Web 認得同一項目，不授權以舊輸入覆蓋新版本。新項目未保存前的表單 key 是本地表單身分，不能當 DB item ID 送出。

`ReadPage` 與共用上述 record 的 `ChangeReadPage.format_version` 升至 **2**，source schema 與 Python／TypeScript 全部由既有 generator 更新。v1 response 明確拒絕；此次沒有 snapshot／DB schema migration。TypeScript 的 JSON Schema 整數區間生成為 `number`，因此前端不能只憑編譯通過判定 wire version 正確。cursor 與簽章 envelope 各自的 format **1** 不變：分頁 record 順序、定位語意未變，且它们是不同契約。

## 2. 六章如何由 record 組成管理畫面

使用 [reads.py](../../../experiments/jd-relational-app/src/jd_relational/reads.py) 的實際完整投影，先收齐同一次讀取所有頁，再以同版 refs 建立只讀顯示索引。這是引用與排序的呈現，不是另一份文件權威。

| 六章 | 可見內容／欄位 | record 關係 |
|---|---|---|
| 基本資料 `profile` | 職務名稱 `job_title`、組織單位 `organization_unit`、員工姓名 `employee_name`、直屬主管 `reports_to`；協作對象的 `name / scope_text` | profile FieldRecord 的 `item_ref=null`；collaborator 為此章根 container 下的 ItemRecord |
| 職務目的 `purpose` | `purpose` 完整文字與換行 | 單一 profile FieldRecord，`item_ref=null` |
| 職責與任務 `duties_tasks` | duty 的 `name / scope_text`；task 的 `name / description`；任務下分開管理多筆 outcome 與 requirement 的 `text`；任務所需 K/S 引用 | duty 為根清單；task container 的 `owner_ref` 指 duty，null 表未分組；outcome／requirement container 的 owner 指 task |
| 所需知識 `knowledge` | 可重用定義的 `name / description` | knowledge 根 container；TaskCapabilityRecord 連向使用它的任務 |
| 所需技能 `skills` | 可重用定義的 `name / description` | skill 根 container；同一個共享項目可被多個任務引用 |
| 適用條件與責任邊界 `conditions` | 全職位的工作環境、工時／出差、共通權責、共通協作及資格條件 | 五個根 container：`work_environment / schedule_travel / shared_authority / shared_collaboration / qualification`；各 item 的內容為 `text` |

每個 item 的 FieldRecord 透過 `item_ref` 配對；item 的 `container_ref` 找到 container，再由 `owner_ref` 找父項目；所有 refs 必須來自同一已收齊的版本。`position` 僅作該 container 内排序，不作身分，也不由 Web 重新編號回寫。

K/S 的定義只在第四／五章存一份。任務卡顯示引用名稱與描述、可增減引用；不把共同定義复制成每個任務的獨立文本。可由同版 TaskCapabilityRecord 呈現反向「哪些任務使用它」，不另存一份反向關係。成果與執行要求維持兩個獨立子清單，不互配一對一。

空白 JD 已有六章、五個 profile 欄位與必要根 containers，因此不啟動 AI 也可完整建立。未完整任務可只有名稱或已知敘述，不要求補造未知成果、要求或 K/S。哪些文字可空、清空後何時違反完整候選，由既有 [domain.py](../../../experiments/jd-relational-app/src/jd_relational/domain.py) 判斷。

item／section 讀取可能包含跨章的父職責、任務詳細項目與相關 K/S；不能把所有回傳 records 當成只屬於 requested section。完整管理畫面第一版可使用 `current` 全頁；item／section 供按需詳讀。

## 3. 八個既有命令對應員工操作

共同保存 envelope 為 generated `ManualSaveInput`：`operation_id`、`base_revision_ref`、`command={tool,arguments}`。operation UUID 由 App 產生並在首次送出前保留；base 使用此次 current page 的 `revision_ref`，具體寫入目標仍使用 current 的 item／field／container ref。不要讓員工或模型填 ID、position、revision number、digest 或保存時間。

| 命令 | 管理畫面操作與必要參數 | 操作完整性 |
|---|---|---|
| `jd_create_task` | `container_ref`、`after_ref`、`name`、`description`、`basis_refs`、`outcomes[]`、`requirements[]`、`capabilities[]` | 一次新增任務及已知多筆成果、要求、既有 K/S 引用；子項為 `{text,basis_refs}`，引用為 `{capability_ref,basis_refs}`；App 配所有新身分 |
| `jd_revise_work` | `changes[]`：`set_field / add_task_detail / remove_task_detail / set_task_capability / add_condition / remove_condition` | 同一目前版的一次完整修正；任務名與敘述一起改、勾選多個 K/S 差異可合成一次；全成功或全拒絕 |
| `jd_set_text` | `target_field_ref`、完整 `text|null`、`basis_refs` | 單欄位完整替換；不傳行號、選取範圍或自行產生路徑 |
| `jd_insert_item` | `item.kind` 與該種類欄位、`container_ref`、`after_ref`、`basis_refs` | 建 duty／collaborator／knowledge／skill／outcome／requirement／condition；condition 使用 `kind="condition"`，五種分類由已發配 container 指定；task 一律用 create_task |
| `jd_delete_item` | `target_ref`、`content_changes[]` | 刪 duty 保留任務為未分組，保留其詳細內容與引用；刪 task 才刪自己擁有的詳細項目與關係；被引用的共享 K/S 不可直接刪。相關內容調整只接受既有有界形式 |
| `jd_move_item` | `target_ref`、`destination_container_ref`、`after_ref`、`content_changes[]` | 移任務到職責／未分組或作合法清單排序；保留 item ID、詳細項目與引用。task 的必要範圍不因換父分類自動變義 |
| `jd_set_task_capability` | `task_ref`、`capability_ref`、`mode=link|unlink`、`basis_refs` | 單筆任務對 K/S 關係；unlink 的 basis 必須空。多筆勾選一次完成時用 revise_work |
| `jd_replace_selection` | `selection_ref`、`replacement_text`、`basis_refs` | 契約已定，但目前 read→manual host 沒有發配 selection，實際回 `selection_not_available`；本 UI 不提供假可用的選取改寫按鈕 |

`after_ref=null` 表第一筆，追加使用同版最後一個現有 sibling ref；不能以 `position` 當輸入。detail 只在原 task 內排序，不提供跨 task 的隱含搬移。每次完成後重新讀取 current，後續命令取得新 refs。

新增完整任務若還需新增共享 K/S，先保存共享定義、重讀，再用新 current capability refs 保存任務；任務表單輸入保留在本機，不把未成功的中間表單當已保存 JD。一個 command 不引用它本次才創造、尚未取得的 item ref。

目前正常 manual composition 尚未接 source resolver，使用 `basis_refs=[]`。這表示沒宣稱新的依據，**不表示清除既有來源，也不表示舊來源已重新核對**。不能因讀到 source token 就自行宣稱已讀來源全文。

## 4. 讀取與同版本分頁

`POST /api/documents/{document_id}/jd/read` 初次 body 必須完整為 `{view:"current",target_ref:null,cursor:null}`。以 `next_cursor` 續讀時 view 與 target 保持相同，收齐 `has_more=false`；核對同一 `revision_ref`、`start_index` 連續及最後 `total_records`。

current／item／section 在分頁間若 head 改變，服務回 `stale_view`；保留員工本地草稿，丟棄這批不完整的 server records 後重新讀 current，不混接前後版本。單頁可切在一張任務卡中間；不能把「這頁沒有成果」當成完整任務沒有成果。文字 record 永不截斷，過大的合法單欄位以 `oversized_unit=true` 單獨返回。

歷史索引使用 `{view:"history",target_ref:null,cursor:null}`；其 revision records 依版本遞減並固定初次索引的上界。開選定版本時仍用 history view，target 為該 `revision_ref`；cursor 保持原 view／target，不跨 current／history 混用。歷史即使是當下 head，其內容 refs 仍不能寫。current page 自己的 `revision_ref` 是唯讀版本身分，供 base/history 使用；不等於此頁 item refs 也是歷史。

## 5. 文件入口與保存呼叫顺序

[configured_api.py](../../../experiments/jd-relational-app/src/jd_relational/configured_api.py) 的所有 POST／PUT／PATCH／DELETE 都要求精確單一 Origin 與 `X-JD-Dataset`，包含使用 POST 的讀取與查回。瀏覽器自行提供 Origin；fetch 提供從文件列表取得的公開 dataset UUID，不將它當金鑰。CORS 已明示 Content-Type／If-Match／X-JD-Dataset，並公開 ETag／X-Request-ID。

| 目的 | 路由與順序 | 要保留的資訊 |
|---|---|---|
| 初始列表 | GET `/api/documents?archived=false|true|all&after=<uuid>&limit<=100` | `dataset_id`、documents、next_after；dataset 改變時舊本機待處理內容隔離，不自動改 header 後重送 |
| 建文件 | POST `/api/documents`：`{request_key,dataset_id,title}` | 送出前保留原 key 與原 title；回覆遺失先 POST `/api/document-creations/lookup` 同一 payload；同 key 查到原 document，即使已更名仍維持原請求 |
| 開文件 | GET `/api/documents/{doc}/metadata`，GET `/jd/state`，POST `/jd/read` 完整 current | metadata ETag、完整 current revision、狀態；文件標題 `title` 和 JD 內 `job_title` 是不同欄位 |
| 更名／封存恢復 | PATCH `/api/documents/{doc}/metadata`，`application/merge-patch+json`，If-Match；body 只能 `{title}` 或 `{archived}` | 使用實際 ETag；412 重讀後再決定；不會新增 JD 版本或修改訪談／Memory |
| 保存內容 | POST `/api/documents/{doc}/jd/edits` | 固定 operation UUID＋原 envelope；與該 UUID 分開保存其後繼續輸入的草稿，不覆寫正在送出的請求 |
| 查原結果 | GET `/api/documents/{doc}/jd/operations/{operation_id}` | 不提交候選；200 是「成功讀到查詢結果」，不是保證原改稿成功 |
| 明示恢復 | POST 同上 `/recover`，必須空 JSON object `{}` | 只調既有 owner 的對帳；不提供修改 payload，不靠 fetch abort／逾時當 writer 已停止證據 |

更名／封存的未知回覆使用 GET metadata 讀實際狀態；不能讀新 ETag 後悄悄重送。這些資訊由 CatalogService 共用規則處理，不在 Web 另寫一套允許封存或 writer 判斷。

## 6. MutationResult 與查回的終止分支

HTTP status、業務結果、receipt 是否確定及 writer 是否放行是不同問題。以生成的聯集分支處理，不另造一個「request succeeded」布林代替。

| 實際觀察 | UI 可做的判斷／下一步 |
|---|---|
| `committed / no_change` 且 `receipt_durability="confirmed"` | 原操作已確定；重讀 current，committed 可開 change_ref。再讀 `/jd/state` 判斷能否開始下一次保存 |
| 有 `operation_ref` 且 `next_action="reconcile_operation"` | 已綁定但結果未確定，保存原操作與草稿，有限查回同 UUID；不能依 error 名稱宣稱未改，亦不可換新 UUID 重做 |
| 已確定的 invalid_input／stale_view／target_missing／relationship_conflict／dependent_items／save_failed | 原操作結果已結束，但改稿未成功；保留員工輸入，依 `next_action` 顯示修正／重讀／停止。新修正是員工決定後的另一操作 |
| `operation_ref=null` 的 unbound 結果 | 本次沒有已綁定 receipt；其 durability 仍叫 `unconfirmed`，不是第三種 `unbound` 枚舉。它不能用來清除另一個先前已未知的原操作 |
| 網路失敗、無 response、無 `jd_result` 的 problem | 未取得原改稿結果；保留已送出的原 UUID，優先查回。瀏覽器取消請求不會停止 native writer |
| lookup／recover 的 `presence="observed"` | 回來的是確定的原結果，可能成功也可能失敗；按 `result` 處理，而非按 GET 200 判成功 |
| `presence="pending"` | 未結束。檢查 `write_state`，正在工作時有限查回；需要恢復時走原 UUID 的 recover，不重播 command |
| `presence="not_found", result=null` | 只表示此刻未找到；不構成未來不會到達、已回滾或可換 key 重做的證據 |

POST edits 的成功 body 是 `MutationResult`，**沒有 `write_state`**；lookup／recover 的 `ManualOperationState` 才包含 write_state。confirmed receipt 已得到但 checkpoint 尚在收尾時，內容可標已保存，仍不能忽略 `write_blocked` 而解鎖下一次保存。

HTTP `application/problem+json` 若含 `jd_result`，那是實際原 observation 的正式投影，仍依其 durability 處理；不含者為輸入／Origin／dataset／服務邊界問題。202 用於已綁定而未確定的結果，不只 outcome_unknown 一種名稱。對 metadata 或 document creation 的 problem 使用各自生成契約，不混成 JD MutationResult。

## 7. 差異、歷史與明示缺口

`POST /api/documents/{doc}/jd/changes/read` body 為 `{change_ref,cursor}`。按同 change_ref 分頁；同一 `change_index` 可能跨頁。每項 header 說明 create／update／delete／move／reorder／link／unlink，value record 提供 before／after 完整原欄位，另有 placement、source_value 及 affected_task；不能以 AI 敘述替代這些實際記錄。

v2 的 before／after item 可用相同 item_id 配對，但兩側仍為歷史 refs。畫面在原管理頁開側欄讀取；不從差異反向生成任意可執行 patch，不拿歷史項目直接寫入 current。來源 `basis_status` 只說內容基準是否相同；`readability="not_checked"` 不能显示來源已確認可讀。

**當前可直接接：**文件建立／列表／更名／封存恢復、六章完整讀取、所有已支援的人工內容 CRUD、任務移動與原生整筆候選驗證、K/S 共享引用、版本與原操作差異、保存查回與既有 owner 恢復。

**目前未接通／未由本輪證明：**

- 聊天／真 AI 持續訪談、Memory 與人工變更通知的正式整合；本輪沒有模型呼叫。
- selection 的實際發配與使用；source 原文 reader 接點；不能以已存在輸入 schema 冒稱實際可用。
- 整份 JD 還原與「撤回這輪 AI 全部 JD 修改」的實際命令／HTTP 接線；不由 UI 自建反向重播。
- 任務對 K/S 關係的指定位置重排沒有獨立命令；先顯示 server 原排序，不能偷偷用 unlink/relink 假裝 reorder。K/S 定義清單本身可合法排序。
- 本機草稿、autosave／IME、晚到 response 不覆寫新輸入、頁面切換與重開保護，屬 RS-3 Web 工作包；本文件只給 API 邊界，未代稱浏览器驗收。
- Excel 匯出、真人交付流程依 Owner 暫緩；不擴充帳號／多人審核。

## 8. 本輪實證與界線

首反例：**3 FAIL**，分別為 current／change record 缺 item_id、仍輸出 format1。補上 source schema、App 識別與正式生成後，讀取／差異／query 邊界固定離線測試最終 **105 PASS（9.76s）**；新增 schema 原始定義與生成 DTO 對非法／缺失身分、v1／布林／未知版本的拒絕核對。保留 Starlette TestClient 的上游 AnyIO deprecated alias 警告；不同批次不能重複相加。

真 PostgreSQL 窄接合 **2 PASS（2.79s）**：使用既有明示 opt-in 的專用 55436 合成 DB；經真正保存的 insert→改字→move 保留 item ID、更新可寫 refs，並讀回完整舊版與原操作來源。此組 authority 是既有測試替身，不宣稱 native host 或真人瀏覽器；不接 provider，不改正式資料。

正式 generator 的 `--check` 與 generated TypeScript 編譯 PASS。signed refs／cursor format、寫入 command schema、資料庫表及其他业务服務沒有變更。獨立審查與真正 Web 完整旅程由 RS-3 主工作單位接續。
