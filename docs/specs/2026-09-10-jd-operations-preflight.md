# P5 日常使用／備份還原施工前置核對

日期：2026-09-10。範圍：既定要求與驗收映射；**P5 未施工、未驗收，以下 PASS/FAIL 均為未執行的判準**。本次 0 付費、未讀 `.env`／key、未安裝、未操作 DB／Job／活程序、未執行模型、未修改 runtime／決策／plan；未讀施工中的 Task4 code。

## 依據與階段

- `docs/plans/2026-09-10-jd-product-delivery.md` §5.6 與 P5：日常操作及全資料備份／還原，不能以核心測試代替。
- `docs/specs/2026-09-10-jd-production-adoption-design.md` §2（authority）、§3.2（新 DB／maintenance）、§3.3（日常 lifecycle／缺設定）、§4（備份還原）、§5 A1–A7。
- `docs/specs/2026-09-10-jd-employee-journey-design.md` §3–8：dirty／已送出 cache／server saved 的區分、archive 保留資料及 terminal receipt 優先。
- Proposed ADR `docs/adr/0074-tested-consultant-runtime-source-and-memory-adoption.md`，及已採 native lifecycle 設計 §6 與既有 review：Job／mutex、停止證據與對帳沿既定設計，不在本材料另選方案。
- 現行 `docs/runbook.md`、`apps/api/.env.example`、`apps/api/app/config.py`、`docker-compose.yml` 僅作接手差異盤點；config 只讀原碼，沒有載入 Settings。現行 ADR0060／0018／OpenRouter 配置不是新正式接手完成證據。0074 仍 Proposed；正式施工須遵循既有 G6／接手 gate。

## 六項要求 → owner／接點 → 可觀察驗收

|要求|既有 owner 與接點|PASS 的可觀察證據；否則 FAIL|尚待施工閉合|
|---|---|---|---|
|日常啟停|API composition root／FastAPI lifespan；Task5 App 專用 Windows named mutex＋Job；前景／背景／native owner 各守既有責任；PG 為既有基礎服務|單一入口完成 loopback、port、PG、資產、版本／設定檢查；Job membership 在 DB／executor／native／admission 前成立。正常停機先停止接單及 scheduler，再等待前背景與 Node cleanup，最後關 HTTP／DB。僅停止自己擁有的程序；重啟不自動重播付費前景，已收背景工作依原 admission 恢復。健康檢查本身 0 模型請求。|P5-O01／O02；實際產品入口與 Task5 bootstrap 證據，不能用 harness 注入 owner 宣稱產品成立。|
|缺設定／斷線|typed config 與 composition root；既有 AI unavailable／錯誤投影；durable admission 不變|缺模型 key／模型設定時可讀文件、做本地手改；AI 明確不可用，沒有 fallback 或外部呼叫。缺 DB／必要 assets／schema 的啟動錯誤可辨識且不自動建表／清資料。失敗不假稱已存；既有背景 target／source／status／recovery_count 不被清空或任意加重試。|P5-O03；具體 typed 狀態與本地可用範圍須由產品實作證明。|
|純本地手改|JD service／Python JdStore 唯一寫入；root-only manual descriptor 只綁 identity；terminal receipt 唯一結果；瀏覽器 cache 非 authority|無模型設定仍能讀取、手改、保存與再次讀到同一權威版本；沒有 provider 請求、假 input／AI run。lost reply 查回原 receipt，不另造 operation。cache 遺失不能重建 candidate；descriptor 不儲存 candidate／不充當 terminal。archive 之 terminal receipt 查詢仍優先，不能被 archived 判斷遮蔽。|P5-O04；與 Task5 已有對帳接點接合，不新增第二手改資料庫。|
|全資料 PG 備份／還原|單一產品 DB 的官方 pg_dump custom archive＋pg_restore；各表 owner 保留；manifest 是備份識別資料|同次完整 DB archive 包含下表全部 durable 資料；先依既定維護流程停止新工作、完成安全停止／記錄未閉合狀態。archive checksum／版本 manifest 成立後，先還原到新、明確且空的測試 DB；遇錯整次停止。逐項內容與關聯核對成功才能稱可還原；原 DB／既有 archive 未被改寫／刪除。|P5-O02／O05／O06；一個 SQL 一致快照不等於所有產品 operation 已 terminal。|
|版本不合停止|startup version／profile／schema availability check；explicit maintenance 唯一 setup 接點|故意不相容版本時，在接單／寫入前可辨識拒絕；無 create_all、官方 setup、migration upgrade、重建 volume 或自動抹除。保留原資料及 pending 訊息，不能將不相容解讀為空資料。|P5-O01／O07；freeze 實際版本／profile／migration 判定資料。|
|更新前備份|既定 maintenance 更新流程＋上述備份 archive／manifest；未另設 migration authority|變更前保留可驗證完整 archive；未備份或備份失敗則不進更新。需要資料格式轉換時明確轉換、驗證、失敗還原，不以刪歷史換過關。切換已驗證還原 DB 是明確 maintenance 動作，舊 DB 保留。|P5-O02／O07；尚無此輪通用 migration engine，不能默認舊 binary 可打開新版 DB。|

## 同次備份的完整性清單

禁止依表各自獨立 dump 後拼成一份「同次」備份；禁止只輸出 JD JSON。備份採單一產品 DB 的完整 archive，包含 schema、資料及必要序列／索引／constraints 等資料庫物件；不靠少數 table filter 表達全資料。

|durable owner／內容|還原必核對的關聯與值|
|---|---|
|catalog／document／run|文件 identity、title、建立資訊、archive state、建立冪等資訊及 run identity／關聯；不是只比文件數。正式設計表名含 consultant_document、consultant_run，不能拿舊 consultant_documents 當完成清單。|
|官方 PostgresSaver 全套 tables|root／child checkpoints、blobs、writes、migration metadata；原始 employee／AI／Tool messages、exact source checkpoint、pending binding／ToolMessage、manual root descriptor 及 manifest 閉合狀態原樣存在；不自行重建 Saver schema。|
|官方 PostgresStore 全套 tables|Memory 內容、navigation、版本及 migration metadata；namespace／文件隔離與逐字来源 lineage 不改、不移成檔案 authority。|
|publication head／receipt|有效 Memory head、receipt、source progress 與 Store、Saver 的 exact source 關聯；raw Store row 不能直接當成已發布。|
|JD head／revision／operation|完整文件各版本、current head、operation identity／digest／base／terminal receipt；lost reply 還原後仍是同一結果，不能重播成新版本。|
|background admission|queued／partial／blocked 等狀態與 target、source、error、recovery_count；run／checkpoint／publication 關聯保留，恢復不能把 count 歸零或新造 admission。|
|archive 中的上述全部資料|archive 不是刪除或另一份文件；既有已收背景工作仍按原規則处理，恢復封存狀態不自動產生新 AI 工作。|

瀏覽器尚未保存 dirty buffer、已送出 cache 中 candidate、OS Job／Popen handles 不在 DB archive 內，不能承諾由 PG 還原。DB 中已存在的 descriptor／pending／receipt 必須保留，重啟需走真實 bootstrap 停止證據及對帳；備份 metadata 不接管 operation 結果。還原內容驗證與執行恢復是不同階段：本次前置沒有授權任何恢復模型請求。

## 定點官方事實

- PostgreSQL 16 說明單一 pg_dump 取得一致快照，但仍允許其他交易寫入；它不替應用判定工作已完成。單 DB dump 不含 cluster-wide roles／tablespaces；還原所有者／授權須具備對應角色。[SQL Dump](https://www.postgresql.org/docs/16/backup-dump.html)
- Custom archive 是 pg_dump 支援並交由 pg_restore 還原的格式；應查退出狀態與診斷，不能只看檔案存在。[pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)
- 新 DB 還原直接指向明確空 target，避免 `--create`：該旗標會用 archive 內 DB 名，`-d` 只作初始連線。`--single-transaction` 包含 exit-on-error，不能搭配 parallel jobs；`--clean` 會 DROP 物件。本流程不應把官方覆寫範例照搬成測試還原。[pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html)
- API init／cleanup 沿已採 [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/) 接點；Saver／Store schema 由已採官方 setup 管理。這些是設計既有來源，本次沒有重新擴大框架研究。

## 明確未閉合問題（供施工者回答，不是新候選）

|ID|必須落地的具體問題|關閉證據|
|---|---|---|
|P5-O01|正式入口、設定欄位／profile／版本與 A1 資產清單尚待接手落定。現行 runbook 的 0018 setup、OpenRouter 範例、按 port 清孤兒與開發用 down -v，不能作 P5 日常／還原方案。|正式接手 BASE 之命令／範例／runbook 一致；產品使用路徑不含清 volume、port 擴散終止或 daily setup。|
|P5-O02|backup／update／restore 的 maintenance exclusion 如何持續到操作結束，避免停止 API 後又被日常入口重啟接單？沿既有 mutex／Job 和 maintenance 設計明確交接，不把 Job active=0 誤當 DB operation 全 terminal，也不暗設新 supervisor。|完整生命週期觀察：maintenance 期間新啟動／新接單被排除；未結工作安全保存與分類；結束後才釋放入口。|
|P5-O03|缺模型配置時既有背景 admission 如何保留且不嘗試付費恢復？|無 key 情境 provider 計數為 0、前景 typed unavailable；背景 durable 欄位不被丟棄／重置，補配置後仍沿原規則處理。|
|P5-O04|操作文案如何區分 DB 已存、傳送中 cache、未送 dirty 與備份可保留範圍？|cache 消失案例無候選杜撰、無假 input／run；DB pending／receipt 可對帳，UI 不承諾復原未保存文字。|
|P5-O05|正式 guard 僅允許預期 caliburn_jd，首次還原卻必須用新明確測試 DB：哪個明確 maintenance 入口承載有界 target 設定與測試 owner identity？尚未指定測試 DB 名，不由本材料擅定。|原 DB 身分與新 target 可比對；拒絕相同／非空／非預期 target；只在已授權測試 target 驗證，不鬆綁成任意 DSN，不讓原／還原兩份服務意外同時寫同一 live DB。|
|P5-O06|同機 PG 角色／ownership／extension／版本前提，以及備份 manifest 具體格式／輸出路徑／失敗檔處理尚待明列。單 DB archive 不提供 cluster globals，不能默默改為整 cluster 備份。|記錄實際 server／dump／restore 版本及必要角色／extension；manifest 包含 app 版本、lock hash、migration head、JD profile、時間、checksum，不含 key／敏感 log。不默選 no-owner/no-acl 改語義。缺前提時明確停，不覆寫舊 archive。|
|P5-O07|更新／不相容拒絕／還原切換的確切版本矩陣與失敗路徑需由接受後資產決定。|不相容 fixture 拒絕且資料未變；失敗更新留完整備份與舊 DB；驗證新 DB 內容後才允許明確切換，沒有自動清舊歷史。|

## 後續驗收應保留的證據

1. 記錄實際接受 BASE／app、lock、migration／profile，以及明確來源 DB 與新測試 DB 身分（不輸出 credentials）。
2. 用固定、不需模型的 durable fixture 覆蓋上述所有 owner、archived、pending、lost reply、背景 queued／partial／blocked；保留期望 exact identity／head／receipt／checkpoint 關聯，不只數量。
3. 分開記錄真產品 startup／shutdown／maintenance gate、備份 archive／checksum／exit status、還原 transaction outcome、還原後內容比較及原 DB 未受還原影響證據。harness 可以觀測，不能取代產品接點。
4. 各核缺設定、本地手改、版本不合、備份失敗、錯 target／非空 target、更新前備份 gate；每項列 PASS／FAIL／未執行。不得以健康回應、檔案存在或 dump 成功代替可還原。
5. 不為本前置重跑 Task1–3 基底；後续依實際跨 seam 變更選必要回歸。固定驗收不代表自然品質、真人採用或 P5 已完成。

本次只新增本報告；未產生任何備份／還原結果，也沒有實作 verdict。

## 2026-09-11 O02 有限接點補核

[同安裝 mutex 候選](2026-09-11-jd-maintenance-exclusion-preflight.md)與[獨立文件審查](evidence/2026-09-11-jd-maintenance-exclusion-review.md)一致性 PASS；正常存活時可沿現有 OS 物件排除日常啟動，競爭輸掉則維護返回忙碌、不開始工具。**O02 仍 OPEN、未採用、未實測**：maintenance crash 後子程序、部分更新資產與受控 stop 仍需正式設計及完整生命週期驗證。停止廣搜相同同步原理；不改 Task5／6 或 production。
