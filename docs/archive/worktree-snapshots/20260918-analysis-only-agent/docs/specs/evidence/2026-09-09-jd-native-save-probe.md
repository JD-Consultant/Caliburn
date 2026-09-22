# JD P01：Python、原生編輯與 PostgreSQL 保存的有限驗證

JD-R002/C03；查閱／執行日 2026-09-09。承接[接線設計 §10](../2026-09-09-jd-editor-app-integration-design.md#10-有限驗證與施工交接出口)，只驗候選 B 的固定本機保存接點。**第二輪六組固定情境通過，保存接點得到有限正證；不代表完整 P、S4 或 S5 通過。**框架、審閱政策與 production authority 尚未採用。[重現與授權](jd-save-probe/README.md)

## 1. 要回答的問題

既有 Python 顧問若把一次有限改稿交給 Plate headless editor，是否能先取得完整候選，再以同一筆 PostgreSQL 交易保存乾淨文件、目前版本及操作回執；中途失敗、過期與保存成功後回覆遺失是否可分辨？

這不是研究新的通用資料庫框架。Node 只執行兩種原生操作，Python 只處理本 probe 的三張文件表。沒有自造 diff、範圍定位、相依審核或歷史回退引擎，也沒有接入正式 Agent。

## 2. 固定環境與官方契約

- Node v22.12.0；沿用 native probe 的 Plate 53.3.11 及固定 lock，`reuseId:true`、`initialValueIds:'always'`。只用 `insertText`、`insertNodes`、原生 ID／operations；本輪不呼叫 `computeDiff`。
- Python 3.12.13／psycopg 3.3.5；使用既有隔離環境，未安裝套件。
- 實際 PostgreSQL **16.14**；沿用本機既有容器，但新建唯一測試 DB `jd_editor_probe_p01_20260909`。建立時 public schema 為空，[建立記錄](jd-save-probe/results/provision.json)可查。未寫 q019、production、Memory、Saver 或 Store 的表。
- 完整虛構 r2 fixture：43 個根節點、174 個 element／ID、102 個文字 leaf；既有合成 metadata 原樣保留。這不是正式 JD schema 或真員工資料。

PostgreSQL 16 的 Read Committed 與 row lock／條件更新契約支持在短交易內重新核對目前版本；它不替 App 識別重試的操作身分。[PostgreSQL 16](https://www.postgresql.org/docs/16/transaction-iso.html)

psycopg 使用 `autocommit=True` 並在每次多表修改外明列 `connection.transaction()`。這避免先有隱含交易、內層只釋放 savepoint，卻把它錯當最外層 commit；異常退出交易的回滾與成功退出的提交依官方固定版本契約。[psycopg 3.3.5 官方文件原始碼](https://github.com/psycopg/psycopg/blob/3.3.5/docs/basic/transactions.rst)。查閱日網站 current 文件為 3.3.6.dev1，沒有把它當成實裝穩定版。

## 3. 第一輪結果與覆核

[第一輪原始結果](jd-save-probe/results/save-probe-20260909T141142Z.json)的五組內部斷言通過，程序 exit 0；[當時脚本](jd-save-probe/results/first-run-save_probe.py)在修改前保留。它只證明當時實際測到的內容，**不能據 `status:passed` 宣告完整 P01 通過**。

覆核發現以下實驗／接線不足，先保留第一輪結果再補驗：

1. 保存後只在同程序拋例外，再另起程序查回執，尚未令寫入程序真的中斷。
2. 全文重開只開新連線；重送用追加文字，未直接檢查新增段落只出現一份。
3. no-change 只有目前基底，未驗過期基底仍須拒絕。
4. 同操作回執只在取得鎖前查；兩個重送交錯可能同時通過前查，第二個撞唯一鍵。接線須在取得同文件鎖後重查。
5. Python 接受的版本號與完整基底值未綁定；正確版本號配上錯誤 value 仍可能過版本檢查。
6. 部分原生命令失敗只比較表列數，不能排除既有內容被改掉；須另比完整 head 與操作回執。

這些是主線及獨立 reviewer 對有限 probe 的診斷，沒有據此推定 PostgreSQL 或 Plate 的原生交易失效。

## 4. 補強後實際結果

[第二輪原始結果](jd-save-probe/results/save-probe-20260909T142102Z.json)於 2026-09-09 14:20:57–14:21:02 UTC 執行，exit 0。共六組 scenario，內含下列固定效果；不把每個 assert 另算產品能力。

| 組別 | 實際觀測 |
|---|---|
| 完整 r2、重開與重送 | 原 43 個根節點保存後成 44 個；全新 Python 程序讀回完整值。相同 operation／payload 重送返回原回執，只一個新段落、一筆操作與一個新增 revision；移除該新段落後與原 fixture 完整全等，包括未改正文、結構、ID／metadata。同 ID 不同 payload 被拒絕 |
| 原生命令部分失敗 | 第一步已新增候選段落，第二步找不到目標，返回 `target_missing`／index 1；DB 完整 head 前後相等，仍為 1 個 revision、0 個 operation。這是沒有發布失敗候選，與下列 SQL rollback 分別驗證 |
| 基底值綁定 | 正確 revision 1 配上另一份 value，於 Node／保存前拒絕；完整 head 不變，沒有新列／回執 |
| 交易中故障 | 寫入 revision 並更新 head 後刻意拋異常；新連線檢查回到原 revision／內容，新增 revision 與回執均不存在 |
| 保存後回覆遺失 | 寫入 child 真正 commit 後，回覆前執行 `os._exit(91)`；stdout 0 bytes。另一個 Python 程序依相同 operation 查回 `committed`／revision 2；DB 為 head 1、revision 2、operation 1 |
| 交錯連線、人工與 no-change | AI、人工及空操作候選先在同 base 算好；人工先以相同保存函式提交，另連線交付舊 AI／空操作均得 `stale_base`。目前基底的空操作得 `no_change`，不生內容版。最終 revision 2，4 筆回執中只有一次實質提交 |

[完整乾淨值及操作快照](jd-save-probe/results/save-probe-20260909T142102Z-snapshots.json)保留原 fixture、全新程序重讀的完整 r2 revision、實際原生 operations／回執、lost-reply 回執及交錯後完整 head，供離線核對。完整 r2 新版的 canonical SHA-256 為 `55d28aaddf7ec95c6882506a53d8b0b7ed902be67e84540b580d7fd76007a480`；檔案 byte hash 與 canonical value hash 用途不同，不混用。

鎖後重讀 operation 已補入腳本；本輪仍沒有同步並發重送測試，因此不把 code review 當該情境的實測。第一輪 DB 資料、結果及原碼完整保留；第二輪每组使用新的文件 ID，沒有覆蓋或清空原資料。

## 5. 效力邊界

上述固定案例通過，仍不證明：

- 實際 Agent 的 operation 身分已在 checkpoint 綁定，或 MEM-Q005、來源查證、取消／未知狀態恢復已接通。
- 正式 JD 容器、App 發配引用、選取、貼上、繁中 IME、前端保存或員工手動編輯均已驗收；本 probe 的 `origin=human` 只是同保存界線的固定呼叫。
- 員工已接受文件，任意歷史修改可一鍵拒絕，或本文三張表已成 production schema。
- 兩個先算完候選再順序提交等於同步並發壓力驗證。它只驗可重現的交錯與過期判斷。
- 斷電、主機／資料庫崩潰、網路分割與交易仍在進行時的 unknown 已全部驗過。commit 後寫入程序中斷只是其中一個固定邊界。

前次原生 diff 13 項中的 2 個反例、history H01 的 ID 反例，以及 UI 所有必要欄位可讀的缺口均保留；P01 保存結果不會改判它們。真正模型能否按足夠理解才改稿、保留人工修改與其他工作，仍是另外的顧問品質驗收。

## 6. 獨立審查與封存檢查

獨立 reviewer 核對 final 腳本、原始結果及完整 snapshots，確認基底值綁定與 partial 完整 head 比較的兩個 P2 已關閉，主線列出的真程序退出／重送／no-change 等不足亦補齊；沒有阻擋上述限定結論的 finding。覆核沒有再次執行全部 DB 情境或把 source review 當同步並發實證。

主線另外以封存檔案重新核對四份執行來源 hash、完整 value／receipt、唯一新增段落與原稿精確保留；Python 語法及 Node entrypoint 語法檢查通過。[14 份原始材料雜湊](jd-save-probe/results/artifact-hashes.json)的來源與封存全等；本輪文件連結／anchor 檢查通過，原 native／history 證據 hash 不變。product 的 apps／packages 沒有本輪變更；無付費模型請求。
