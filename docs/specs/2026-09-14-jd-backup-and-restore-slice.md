# JD App 備份與還原演練

日期：2026-09-14；Topic：JD-R002；[產品交付計畫](../plans/2026-09-10-jd-product-delivery.md) 第 6 項與 P5 的「全體資料備份及還原演練」。隔離 App，ADR0075 Proposed／production ADR0060 不變。零 provider。

## 1. 要完成的效果

**員工的 JD 換一台機器、或資料損毀之後拿得回來，而且拿回來的是完整的——不只是 JD 正文，還有訪談、工作理解與能繼續談下去的位置。**同時說清楚哪些東西不在備份裡，還原之後必須重新設定。

## 2. 一份完整備份包含什麼

| 要備份 | 為什麼 |
|---|---|
| App 的 PostgreSQL 資料庫**全部 schema** | `public` 是 JD 的十四張表；`jd_runtime` 是對話 checkpoint、pending writes 與 Memory Store。只備份 JD 表會失去訪談與續談位置。 |
| 本機 DPAPI 設定檔 `host.v1.dpapi` | 內含安裝身分、資料集識別與**簽章金鑰**。所有對外發出的引用（版本、改動、訪談窗口、context）都以這把金鑰簽章並綁定該資料集；金鑰不同，先前發出的引用一律拒絕。 |

| 不在備份裡 | 還原之後怎麼辦 |
|---|---|
| provider 金鑰（Windows 認證管理員） | 依既有決定不匯出。還原後由操作者重新 `set-key`；在那之前人工 JD 照常，AI 顯示未啟用。 |

## 3. 先寫的反例

- 只 dump `public` 的備份還原後，`jd_runtime` 的對話 checkpoint 是空的——**還原成功不等於能續談**。
- 用**新初始化**的設定（新簽章金鑰）打開還原後的資料庫時，先前發出的引用必須被**拒絕**，不得默默接受。
- 資料集識別不同時同樣拒絕。
- 還原後每一版的 `content_digest` 與原本逐版相同；JD 十四張表與 `jd_runtime` 的列數一致。
- 備份檔內不得出現 provider 金鑰字樣。

## 4. 依據

| 依據（查閱 2026-09-14） | 官方事實與本案使用範圍 |
|---|---|
| [PostgreSQL 18 Backup and Restore](https://www.postgresql.org/docs/18/backup.html)、[`pg_dump`](https://www.postgresql.org/docs/18/app-pgdump.html) | `pg_dump` 備份**單一資料庫**，預設涵蓋該資料庫的所有 schema；`-n` 只取指定 schema。custom 格式需以 `pg_restore` 還原，且還原目標資料庫需先存在。官方未規定本案要備份哪些檔案。 |

`pg_dump` 與伺服器同為 18.6（容器內 `pg_dump (PostgreSQL) 18.6`）。沒有宣稱其他廠商採用相同備份組合。

## 5. 演練結果（2026-09-14）

[演練腳本](evidence/jd-backup-restore/backup_restore_drill.py)、[紀錄](evidence/jd-backup-restore/drill.json)。對象是一個真的安裝（含一次真訪談留下的對話），用容器內與伺服器同版的 `pg_dump 18.6` 備份，還原到**新建的空資料庫**——沒有 drop、沒有覆蓋、沒有清 volume，零 provider。

| 檢查 | 結果 |
|---|---|
| 整庫備份還原後的 JD | 十四張表都在；三個版本的 `content_digest` 逐版相同（`bbec73fa…` → `bf07204f…` → `bbec73fa…`）、operation 2 筆、標題一致。 |
| 還原後的訪談 | checkpoint 19 筆、pending write 51 筆、Store 0 筆，與備份前**完全相同**——還原後**談得下去**，不只是讀得到。 |
| 只備份 JD（`-n public`）會失去什麼 | 該備份內 `jd_runtime` 物件數為 **0**（整庫備份是 30）；`jd_revision` 在裡面，`checkpoints` 不在。**JD 救得回來，訪談救不回來。** |
| 設定檔是不是備份的一部分 | 是。員工頁面上已發出的引用，只有備份下來的那把簽章金鑰＋同一資料集識別解得開；換金鑰、換資料集、或全新初始化的設定，三種都**被拒絕**，不是默默接受。 |
| provider 金鑰有沒有跟著跑進備份 | 沒有。兩份備份檔的位元組內都找不到金鑰前綴或認證管理員的 target 名稱。 |

**操作上的意思：**備份 = 一次 `pg_dump`（整個資料庫，不要用 `-n`）＋ 一份 `host.v1.dpapi`。還原 = 先有同名的空資料庫、`pg_restore`、把設定檔放回原位，然後重新 `set-key` 設定 provider 金鑰。

## 6. 限制

- 還原目標是**新建的別名資料庫**，不是同名覆蓋：本機只有一份安裝，同名覆蓋必須先移除原庫，這一步沒有演練，文件照實說明。
- 沒有演練世代輪替、異地保存、備份加密或損毀備份的偵測。
- 沒有演練 PostgreSQL 服務本身的損毀、磁碟故障或還原到不同 PostgreSQL 大版本。
- 「還原後談得下去」是由 checkpoint 與 pending write 完全相同推得，本次**沒有**在還原後的資料庫上真的再跑一輪訪談。

## 7. 啟停與失敗提示

同一批另外固定了操作入口自己的行為（[測試](../../experiments/jd-relational-app/tests/test_operator_entry.py)，7 項通過）：

- 這台機器上**沒有安裝**時，`status` 與 `serve` 都說「尚未找到本機設定」、回 exit 1，而且**不會順手建立**設定檔或它的資料夾。`serve` 永遠不會偷偷初始化。
- 未預期的失敗只印固定的安全訊息。反例用一段含 DSN、埠與密碼的驅動錯誤，確認螢幕上不出現其中任何一項；變異驗證：把 `str(error)` 放回輸出，該項立刻失敗（改動後以 `git hash-object` 確認還原）。
- 中途中止回 exit 130 並要求重新查看實際保存狀態，不宣稱任何結果。
- 每個已知錯誤碼都有自己的白話訊息，不會退回泛用句。

**沒有做的：**沒有在這台機器上建立真正的安裝（固定的 Known Folder 位置目前不存在），所以 `python -m jd_relational serve` 的真程序啟停沒有端到端跑過。宿主層的真程序啟動、正常停止、Saver 關閉與程序確實退出，已由既有 helper 在真 PG 上反覆驗過（見還原／撤回與背景恢復結果稿）；缺的是 CLI 這層外殼。要補這一項需要在本機建立正式安裝與資料庫，那是操作者的動作。
