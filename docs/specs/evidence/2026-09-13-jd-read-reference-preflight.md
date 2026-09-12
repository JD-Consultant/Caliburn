# JD 讀取與 App 引用：有界實作前置

**同日採用進度：**輕量 mutation result 與永久 receipt／外部 refs 分界已回寫工具及保存契約，結果 schema／HTTP 投影已[實作驗證](../2026-09-13-jd-result-and-storage-foundation.md)。讀取 DTO、正式 ref 發配／驗證及永久 receipt 型別仍待施工；本文簽章套件維持候選。

- 查閱日：2026-09-13；Topic：JD-R002；RS-1 設計建議，尚非讀取／DB／重啟實測結果。
- 依據：[工具 §3.1／3.7／5／9](../2026-09-12-jd-relational-agent-tool-contract.md)、[保存 §4.3／9](../2026-09-12-jd-relational-schema-and-write-contract.md)、[業務 §3–4](../2026-09-12-jd-business-operations-and-scope-design.md)、[完整六章旅程](../2026-09-13-jd-complete-app-journey-design.md)、[欄位充分性](../2026-09-13-jd-field-sufficiency-audit.md)及[施工計畫](../../plans/2026-09-13-jd-relational-app-implementation.md)。
- 本單位只新增本文件；未改程式、契約、生成器或依賴，未讀金鑰、呼叫模型、接資料庫。公開官方查閱不含私有 JD 材料。其他作者正在實作的結果契約不以本文冒稱已完成。

## 1. 可採方向與目前缺口

保留同一個完整 JD read service：由 current relational rows 或指定 immutable revision 取得材料，再產人工／模型各自需要的投影與 typed refs。ref 是受控定位材料，不保存第二份正文、事件或 operation 結果。分頁限制每次交付量，不能取消完整讀取或把摘要當完整內容。

目前 [domain.py](../../../experiments/jd-relational-app/src/jd_relational/domain.py) 的 `CommandContext`、`Ref`、`Source` 和 [selection.py](../../../experiments/jd-relational-app/src/jd_relational/selection.py) 是 App 注入的合成可信材料；已驗同 document／base、item/field/container 類型和 UTF-16 替換。尚無正式發配、簽章驗證、資料集識別、history 用途隔離、完整 read DTO、source port 接線或 SQL 一致讀取。原 289 tests 不涵蓋這些新能力。

第一個可施工接點可為少數明確 Python ports：完整材料讀取、既有來源回讀、固定 JD ref 發配／驗證；對外 `jd_read`／`jd_change_read` 與 read result 仍從同份 JSON Schema 生成。不新增 query DSL、任意 JSON path、通用 locator 或任意檔案 workspace。

## 2. 需求到投影的完整映射

| 既定要求 | 最小讀取責任 |
|---|---|
| 六章與已知但無名稱的工作 | 基本四欄與多筆 collaborators；purpose；duties、未分組 tasks；task.name/description 與分開的多 outcomes、多 requirements；knowledge、skill 的完整 name/description；五類 conditions。空值、空清單、完整有意義空白與 LF 原样保留，不能自動补「無」。 |
| 名稱可重複、K/S 共享 | 可讀名稱／說明與 opaque typed ref 同時回傳；task→capability、capability→task 的用途從同一 junction 推導，不另存反向可編清單。ref 定位依穩定 ID，不以名稱猜配。 |
| 任務的必要範圍不能遺失 | task item read 可完整取得自身欄位、兩組子項、關係、父 duty 摘要與來源；duty item read 可讀完全部子任務及其相關內容；K/S item read 可讀完完整定義與全部受影響任務。較大內容可續頁，但必明示未讀部分與入口，不能以截斷預覽當刪除／移動前的完整影響材料。 |
| 任務移動與 D01 | 來源 duty、任務、目的 duty 的同版內容都可取得；未分組 container 有明確 ref。新 ref 不代表自動確認專業含義，工具不因看到 history 就推論目前必要範圍已保留。 |
| 來源支持狀態 | 每個 link 的 target 及 basis_digest 對同份 JD 材料計算 `current`／`needs_recheck`；source owner 的可讀性／原文另行觀察，不混成同一狀態。relation 的來源仍掛 relation，不誤作 K/S 定義來源。 |
| 空白 JD 可全手動建立 | 即使清單空白，基本欄位與合法新增 containers 仍可取得；不須先由模型或樣稿建立項目才能發 ref。 |

建議將 `current` 回應視為六章完整投影的可續讀入口。`section` 用固定六章的只讀 section ref：基本資料、職務目的、職責與任務、知識、技能、條件與邊界；它不是新增正文欄位或通用區段路徑。

工具尚待工程精確化的兩點：現 §3.1 使用 section view，§5 尚未列 section ref；history view 的 null target 用法未明。建議 `history + target_ref=null` 回本文件的 revision 索引，`history + revision_ref` 回該份不可變稿。索引需有可用的 revision/change refs，否則首次查歷史沒有合法入口。這些是既定完整歷史讀取的接線，不需重問 Owner 是否要歷史。

## 3. 一致讀取、分頁與真實差異

### 3.1 Current 與分頁

依保存 §9.1，在第一個 query 前開短 `READ ONLY REPEATABLE READ`，一次 materialize document/head/revision metadata 及該文件所有正文、relations、source links。交易內取得人工 notice 的固定上界及所需事件；結束後才投影、簽 refs、呼叫外部 source port。不要重新查 head 來簽 ref，也不讓分頁或模型思考持有 DB transaction。

固定 projection order 沿既有章節、container 及 `position,stable ID`；cursor 綁 document、dataset、revision、view、target、投影格式版本和下個位置。續頁重新讀完整材料，current head 若不等於 cursor revision 就回 `stale_view`，不拼接新頁。history/change cursor 則綁不可變 revision 或 base/result pair，head 前進仍可繼續讀。

對外頁面須有 `has_more`／`next_cursor` 與明確的完整性語意。單一 task 可因子項多而分頁，但父項、子項及關係必有型別／ref 可接續；不得缺頁卻顯示「已完整讀取」。優先讓單一已允許文字欄位完整交付，不截半句；頁大小是可有限驗證的工程值。上限必按序列化後 UTF-8 bytes、已簽 ref 的長度與現行單欄上限核算，不能把任意固定 token 數當保證。若一個允許的內容單位超過一般頁預算，应有明示單項頁規則；不能因此靜默少讀或降低既定欄位容量。

### 3.2 History 與 change read

history 由選定 revision snapshot 產生，source links 及目標正文沿當時版本；如今原話不可讀只改此次觀察，不能改歷史。即使選中的歷史 revision 恰等於 current head，history 發出的 item／field／container refs 仍不可寫。

`jd_change_read` 以已確認 operation 的 base/result snapshots 和稳定 IDs 比較，產出確切 create/update/delete/move/reorder/link/unlink、欄位 before/after 及 source-link 變動。no_change 或失敗不捏造差異。不可用模型摘要、目前 rows、logs 或時間近似重建。

排序比較要區分「新增／刪除造成 position 正規化」與「存活 sibling 的相對順序真的改變」；否則在第一個位置新增任務會把全部舊任務誤標為 reorder。move 的父容器變動與內容更新可以同時出現。這是 stable ID diff 的必要反例，不需通用 diff 引擎。

## 4. Refs、重啟與 receipt 的建議邊界

### 4.1 永久 receipt 與對外 ref 投影

**建議永久保存穩定 IDs＋結果語意，讀取時才發 refs。**`jd_operation.receipt` 是永久 authority；其格式保存已核 document/operation/base/result 身分及固定 status/effect/error/next action。精確變更全文由 `jd_change_read` 讀原 immutable base/result snapshots 推導，不在 receipt 另存一份巨大 before/after。不要保存暫態 registry token、簽章外殼或由最新 head 推導的 writable ref。

2026-09-13 主代理採輕量 mutation result 方向：status/effect/durability、operation/result-revision/change refs、error、next action；舊 `actual_changes` 例子相應更新。此取捨不刪 UI 的確切差異能力，前提是 `jd_change_read` 的全部欄位、結構、K/S、來源變動與完整續頁入口仍可用。成功後看原變更使用 change_ref，下一次寫入則讀 current 取得新 refs；不能沿舊 refs 或以名稱猜新項。工具 §3.3「回新 refs」與 §6 舊例須同步這個讀取出口。

同 key／同 digest 返回同一份永久 receipt，status、效果、base/result、變更與錯誤不變；對外 refs 可由該原始材料重新發配。這不與 idempotency 衝突，前提是保存 §4.3 明文說清：相同的是原結果及身份，不是要求每次 HTTP／tool JSON bytes 完全相同。投影失敗不得覆寫原 receipt、改判保存失敗或重做 mutation。舊 result revision 只能指原 result，不能因目前 head 已前進而換成最新版本。

receipt 內已知 target 用 typed stable identity，錯誤中尚未驗明的引用只能是「原輸入 token 的無權能回顯」，不能投影成新可寫 ref。錯誤碼／固定人讀文案與候選輸入的敏感資料仍分開。

request digest 也要界定在 App 已核的固定意圖上，不受重新發配 token 的隨機／簽章外殼改變；不得用新的 ref 重簽結果改寫原 digest。對已存在 operation 先查原結果，再作新 mutation 的 current-head 新鮮度判斷，否則成功操作在 head 前進後重送會被誤報 stale。若無法驗明原意圖，只允許原 operation 的查回／對帳，不能當成授權新寫。

### 4.2 最小可持續方案

可採候選為 **ItsDangerous 2.2.x `URLSafeSerializer`＋固定 JD payload**。官方現成簽章／驗簽可讓 App 發出的資料往返而不需 per-ref DB registry。它不提供 JD 欄位／範圍／revision 驗證，仍由 App 完成；不自行實作密碼演算法。主代理尚須衡量 token 大小及持久 key 管理代價，本文沒有定案採用、安裝或授權提前實作；永久 receipt／外部投影分界可獨立先行。

payload 只含版本、資料集身分／還原世代、document、revision、用途、固定 ref kind 及該種類必要 locator。item 用 entity kind＋stable ID；field 再含固定 field enum＋base value digest；container 含合法 child kind＋parent；revision/change 只讀；section 是六個固定區段；cursor 包含固定讀取範圍。使用不同 signing contexts/salts 隔離 ref／cursor／selection，並在已驗簽 payload 上檢查精確型別與閉合欄位。沒有任意 table、SQL、JSON path 或由 client 指定的解碼策略。

這裡 opaque 是 API 契約：Web／LLM 不解析或產生 token，App 不接受裸 DB UUID。**簽章不等於加密，接收者可以解碼 payload；不得聲稱內部 ID 被保密。**它防止改造成另一個有效 capability，沒有新增登入／ACL 或授權模型。

簽章 key 必由資料集宿主持久提供，正常 process restart 不換 key。token 解碼不依記憶體 registry；restart 後仍須讀 authoritative rows/snapshot、核 scope、revision、用途和存在性。資料集還原／替換須沿 DA-03 改變有效世代或明確失效舊 refs，不能因 UUID 恰好相同而把舊瀏覽器暫存／游標誤接另一資料集。key 遺失或世代不符時要求重新讀取並重新取得 refs，不能略過驗簽。

只用隨機 ref→物件的程序記憶體 registry 有較短 token 的優點，但程序重啟會令模型歷史中的 ref 無法使用；若選這條路，必須提供從永久身分重建新 refs 的完整續談／歷史入口，並明示舊 ref 失效，不得把 registry 持久化偷偷變成第二個結果 authority。可有可丟棄 cache，但 cache 不發明或恢復正文／receipt。content rows 或 immutable snapshot 都不應保存短效 tokens。候選取捨用 token 大小、新程序續談與原 operation 查回反例閉合，不需同層品牌廣搜。

### 4.3 Resolver 與現有 domain 的接合

新 resolver 在 mutation 前驗簽、dataset/document、用途為 current-write、revision/base、target kind/存在及 field digest；全部通過後才構建現有 `CommandContext.refs`。history-only refs 即使 revision 符合也在此拒絕；domain 現有只核 document/revision 的 `Ref` 不能單独辨識歷史用途。這個可信轉換不能接受 client 直接傳入整份 context mapping。

原始問答 `source_ref` 繼續由既有 source owner 發配。JD 不另簽一份可取代來源權威的 locator；只有經來源 port 驗同文件、種類與可讀性，才加入此次 `CommandContext.sources`。既有 link 的可讀性失敗不刪 link；新 basis 不因以前曾讀成功就豁免當次查核。

選區只由 UI/App 入口發配：先完成組字與保存，再核同一 LF 全文、field ref 和原生 UTF-16 起訖／精確 selected text。selection token 可保存 field locator、全文 digest、UTF-16 range、selected digest，不必攜帶或永久另存全文。解碼後從同版 authoritative field 重建 `Selection`，重核全文／範圍／片段才調用既有替換。LLM 仍只填 `selection_ref/replacement_text/basis_refs`。重啟後不恢復游標，不靠搜尋重複字猜位置；同資料集、同版、同摘要者才可能驗明，否則重新選取。

## 5. 官方依據與本案取捨

各頁正文查閱日為 2026-09-13；沒有官方資料證明兩家模型採相同 ref 格式或 token 技術。本案採用何種 ref payload、revision 規則與 scope 都是既定 JD 需求的工程映射。

| 官方來源 | 支持的有限事實與限制 |
|---|---|
| [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)，現行 Responses 指引；本地 SDK 3.13.0 | 已知參數應由程式承擔，清楚描述工具及輸出。本案因此由 App 注入 document/base 並發 refs。它未提供本案的 JD locator、資料集恢復或 SQL snapshot 機制；未呼叫 provider。 |
| [Anthropic Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents)，官方工程文章／持續網頁 | 工具應提供相關、可行動內容，可用分頁與有界輸出；若截斷須有繼續取得資料的指引。本案不抄其示例 token 上限，也不藉精簡輸出刪除完整工作資料。 |
| [AWS CLI v2 pagination](https://docs.aws.amazon.com/cli/latest/userguide/cli-usage-pagination.html)，現行官方指南 | continuation token 用於取得後續內容，服務排序變化可能導致漏項或重複；官方也提到完整取回後本地分頁。本案的 revision 綁定是自己的更強一致性要求，不是 AWS 保證。未採 AWS 服務或 CLI。 |
| [PostgreSQL 16 isolation](https://www.postgresql.org/docs/16/transaction-iso.html) | Repeatable Read 中後續查詢使用同一交易快照，支持既定短 read transaction；不能由此推論跨請求或外部 source port 同快照。尚未执行本版真 PG 交錯測試。 |
| [ItsDangerous stable 2.2.x](https://itsdangerous.palletsprojects.com/en/stable/)、[serialization](https://itsdangerous.palletsprojects.com/en/stable/serializer/)、[concepts](https://itsdangerous.palletsprojects.com/en/stable/concepts/) | 現行 stable 文件列 2.2.0；serializer 包裝簽章，salt 區分用途，換 key 會令既有 token 失效；輪替 key 的保存／管理不由套件負責。簽章可供不設 server registry 的往返，payload 可讀。這只支持候選機制；未安裝／鎖版或實測。 |
| [ItsDangerous BSD-3-Clause](https://itsdangerous.palletsprojects.com/en/stable/license/) | 免費 OSS 套件；分發須保留授權條款。沒有新增付費服務。 |

## 6. 待定技術細節與有限驗收

下列皆可由工程完成，沒有新產品選擇需要 Owner 重答：

1. 先與 root 結果 SSOT 對齊永久 receipt／外部 response 兩種型別，以及 canonical request intent 的 resolver 次序；不能先把短效 refs 寫進 DB 再補修復。
2. 完成固定 read variants、六章 section refs、history 索引入口、cursor completeness 與單項頁上限。輸出不得暴露模型可直接填的 DB IDs，也不能缺少 task/K-S/來源關係。
3. 鎖定 signer 版本、payload format／固定 salts；持久 key 位置、首次建立、備份還原與 dataset epoch 由 RS-2／DA-03 宿主設計閉合。RS-1 可注入合成 key/dataset 做離線測試，但不能因此宣稱已具備新程序重開與還原保護。
4. 真來源 port 尚未接線時，只能以可用／不可用／跨文件的合成來源做邊界測試，不稱原始訪談已接通。

最低反例組：同名異義 K/S；空白六章全部合法 containers；nameless task 與長文字／多 O/P 全頁重組無損；跨文件/資料集/ref kind/用途/偽造 token 拒絕；r5 讀取期間 writer 提交 r6 仍全 r5；r5 cursor 下頁遇 r6 拒絕；history cursor 不隨 head 改版；current revision 的 history ref 仍不可寫；普通新程序同 key 可驗 token、換世代不可用；emoji/重複文字選區在改全文後失效；同 operation 重查保持原 receipt 語意且不發最新 writable target；同頁新增導致位置位移不冒稱所有舊項 reorder；source 不可讀與 target needs_recheck 分別呈現。

以上為待執行驗收，不把文件審查、純資料 fixture、真 SDK 離線序列化、真 DB／新程序或真人選區混為一種證據。既有八操作可持續施工；完整 read/ref 與永久回執邊界閉合前，RS-1 不標整體完成。
