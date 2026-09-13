# 當輪原話 → JD 引用：真 PostgreSQL 縱向驗收

- 日期：2026-09-13。
- 狀態：**限定情境 PASS**；使用真 PG／PostgresSaver／LangChain Agent／Anthropic SDK，以及離線固定模型回覆。不是自然模型、真瀏覽器或新 OS 宿主驗收。
- 範圍：[本次來源接合](../../2026-09-13-jd-consultant-source-integration-slice.md)；本文件只記獨立資料庫縱向證據，不取代[原生時序證據](native-timing.md)與來源模組的負面案例。
- 唯一新增測試：[test_conversation_sources_postgres.py](../../../../experiments/jd-relational-app/tests/test_conversation_sources_postgres.py)。未修改產品實作、既有測試、依賴、設定或 schema。

## 環境與資料界線

重用既有專用測試環境：`127.0.0.1:55436`、`caliburn_jd_relational_test`、`jd_test`；連線實際核對 PostgreSQL `180006`、JD migration `20260913_0001`，以及 `jd_runtime_test` 的四張原生 Saver 表。沒有 setup、DDL、啟服務或清除既有資料。

測試經 `JD_RELATIONAL_TEST_DB=1` 明示啟用；每次新建合成文件與 dataset/run 身分。使用專案固定測試憑證及合成簽章 key，不讀日常設定。沿既有 `_offline_model` 的 `httpx2.MockTransport` 固定 6 次 SDK 回覆，非同步網路路徑被測試禁止；**真 provider 呼叫 0、費用 0**。

## 已驗效果

| 階段 | 實际證據 |
|---|---|
| 第一輪原話供給 | 當輪 Human 已存於原生 messages；含 CRLF、前置空白及繁中的文字在 SDK 請求和來源回讀保持相等。`conversation_source_notice` 只有來源位址與訊息身分／角色，system 沒有重複原話正文。 |
| 同輪工具循環 | 讀稿、建立任務、最終回覆的三次 SDK 請求使用同一個 source ref；notice 首輪只列該 Human。 |
| 原話與 JD 接合 | 固定模型用實際收到的 source ref 作為 task 及三個成果／要求的 `basis_refs`；原生 `jd_create_task` ToolMessage 為 confirmed committed，操作身分與 SQL 原回執一致。 |
| 真 SQL 保存 | 第一輪有四筆 `jd_source_link`：一筆任務、三筆成果／要求；JD head 為第 2 版、操作數 1。 |
| 員工更正 | 經共用 ManualService 保存任務敘述，basis_refs 為空；原生對話完全不變。完整續頁讀取精確顯示任務舊依據 needs_recheck，其餘三筆仍為 current。 |
| 第二輪 AI 續編 | 模型實際讀到員工保存後的任務敘述，再依第二輪來源修改名稱；三次請求來源位址一致。第二來源包含前輪公開 AI 回覆及本輪 Human；第一來源仍回讀原文。 |
| 不遺失更正與依據 | 最終保留手改敘述、共有五筆來源關係，兩份来源均存在；JD 第 4 版、操作數 3，原消息前綴及兩個 Human 保持不變。 |
| 原請求查回 | 查第一輪原結果，以及以原 run／原起始版／原文字再次 start，均回原結果；SDK 計數仍 6，原 SQL 回執不變。 |
| 關閉後重開 | 真正關閉 owner 和 Saver connection，再建立新 connection、serializer、graph、owner、codec；讀回兩份相同原話、完整原生消息、JD 與原操作回執。新 service 的 capture 被設為必定失敗，這些讀取仍成功，證明未重新發來源或重播模型。 |

## 首敗及修正後結果

1. [首跑原始輸出](../../../../.research-tmp/jd-source-postgres-first.txt)：**1 FAIL／9.23 秒**。第一輪三次 SDK、四筆 SQL 來源及手改已成功；測試錯把 current 首頁當完整讀取，未在第一頁找到需要核對的來源，就停止在第二輪之前。
2. 原因核對：既有 ReadService 預設 32 KiB 分頁，source records 位於欄位之後。長簽章來源使本合成文件產生續頁；既有 `_last_page` helper 的「沒有續頁」假設也不適用此情境。這是新增測試的取頁假設，沒有修改 reads/domain 來迎合結果。
3. 有界修正：測試按 App 提供的 cursor 讀完整同版 records，逐頁核對 revision、start index、總筆數；第二輪固定回覆只使用首頁已取得的名稱／敘述，不假稱已讀完其他來源。未放寬來源數量、內容相等、needs_recheck 或保存斷言。
4. [修正後原始輸出](../../../../.research-tmp/jd-source-postgres-fix1.txt)：**1 PASS／8.96 秒**。完整執行表列兩輪、手改及重開回查；停止擴跑。

重跑命令（工作目錄 `experiments/jd-relational-app`，沿本專案已安装的 venv）：

```powershell
$env:PYTHONUTF8='1'
$env:JD_RELATIONAL_TEST_DB='1'
& '.venv/Scripts/python.exe' -m pytest -q tests/test_conversation_sources_postgres.py -p no:cacheprovider
```

## 限制與下一接點

- 此處「重開」是同一 Python 程序內的新 connection／serializer／owner，沒有證明 Windows 新程序或 foreign-host 恢復；既有宿主驗收另有責任文件。
- 固定 SDK 回覆證明保存及資料流，沒有證明自然訪談會選對依據、引用完整或寫出高品質 JD。
- 只核當輪原話來源，未接 Memory／案例工作區、長來源主動分頁工具、來源 UI、正式日常模型啟用或真人試用。
- 本輪由原生 Saver 保存原話；JD 資料庫只保存引用關係及其基準，没有新增第二份對話 archive 或新資料權威。
