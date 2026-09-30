# 2026-09-30 安全點暫停交接

Owner 明確要求暫停 Goal；本記錄是恢復入口，不是另一份產品規格或完成宣告。任務唯一狀態在[任務表](../tasks.md)。**收到明確恢復指示前，不繼續施工、付費測試或背景開發。**Demo 程序留給使用者試用，不等於 Goal 持續執行。

## 現在可用到哪裡

[開啟本機全合成 Demo](http://127.0.0.1:5173/job-files/b6e76e87-817c-4c9e-8c82-3564b329c7f2)。可以查看已保存內容、匯出 PDF，或由使用者自行開始下一次訪談。

| 能力 | 已有證據與限制 |
| --- | --- |
| 訪談 → AI 編輯 JD → 正式保存 | 四次真 `gpt-6-luna` 訪談完成，正式序號 1–9；三項工作由訪談產出，未人工代寫。重開能讀回同一正式稿及答覆。 |
| 背景 Memory | 三批 B1→B2 已共同發布；處理邊界分別 4、6、8。A 第三輪實際固定已發布 Memory、讀兩層資料，依員工更正修 JD。 |
| 暫停／接續 | 第三輪真 A 曾停妥、重開並續同一 execution，保留原 Memory；不能擴大為所有 crash 位置都已驗。 |
| 公開中間訊息 | 真 A 的 commentary 已保存、可歷史回看；不進正式訪談序號。尚未捕捉真模型完成前 delta 與斷流恢復的完整視覺證據。 |
| 來源回查 | 正式來源 UI 已接線，瀏覽器讀回序號 8 原話；Memory 固定鏈與差異有 HTTP／PG／component 證據，尚缺該路徑真瀏覽器驗證。 |
| PDF | 已實際渲染中文長短稿；暫停前再次從 UI 成功下載正式 JD，615,045 bytes。不匯出候選、不含姓名。 |

真旅程／費用／限制沿[T08 §5](t08-consultant-turn.md#5-顧問--背景整理的整合2026-09-30-1057-台北)與[T13](t13-pdf-export.md)，新唯讀来源沿[T09 整合證據](t09-source-viewer.md)。資料全為合成，不能據此宣稱一般長訪談或專業 JD 品質已全面達標。

## 暫停時安全狀態

- 分支 `target-rebuild`；本次來源切片以前的提交為 `1198509f`（公开串流）、`29b83bb1`（整合證據）。本記錄及來源切片一同作本地安全提交；恢復時先用 `git log -3`、`git status` 核對实际提交，不猜 commit hash。
- Demo DB `caliburn_target_demo`，loopback 55439、schema `caliburn`、migration 0018。只作唯讀核對：`executions` 為 **consultant_turn completed 4、failed 1；memory_batch completed 3**，無 active／paused；`memory_snapshots` 共 3 筆。歷史 failed 仍保留，不清掉它掩蓋失敗。
- 最新發布 snapshot `48c31c96-f1db-4fc2-a099-89c6a23103e6`，F=8；最後成功 A `e1178998-0df0-44da-929d-bbef0ce33ae0`，B `07be6b4c-d230-4c93-beb9-2d5fd1f710d5`。沒有半途候選需手動轉正式。
- 自有後端 loopback 8100，launcher PID 33124；前端 loopback 5173、PID 24936。這是觀察值，不可在後續不核程序身分就據 PID 停止；目前保留運行。啟動方式沿[backend README](../../../../apps/api/README.md#本機-ai-demo-啟動)，不動舊正式產品。
- 本機暫態 log：`.research-tmp/target-demo-backend-live8.{stdout,stderr}.log`、`target-demo-vite-source.{stdout,stderr}.log`。憑證只由既有 loader 載入 `apps/api/.env`；不複製到文件、命令或版本控制。
- 收到暫停後沒有發送新模型訪談／背景整理；最後只做唯讀 UI／DB、PDF 匯出及離線回歸。完整資料與程序保留，不刪 DB、volume 或 secrets。

## 尚未完成：恢復後從這裡續

1. T06／T08／T11／T12：已保存原件和已提交工具可承接，但跨程序 **未明 outbound attempt 的 production 核對／恢復接線**與完整故障競爭矩陣尚未完成。不要盲重送模型、重複業務效果或宣称任何中斷都自動恢复。
2. T09：真串流完成前呈現、斷流重連與跨 tab；來源的 Memory 鏈／diff 真瀏覽器驗證。獨立 reviewer 建議把「列表後再發布」的臨時探測補成永久 HTTP 回歸；不阻擋本次唯讀切片交接。
3. T14／T16／T17：分析指南／Prompt／工具共同品質校準、長訪談、更正及來源變動的代表情境，真 Compaction／容量門檻與成本驗證尚未全過。既有 11 種情境與 rubric 可沿用，不另造評測平台。
4. T15：完整安全／容量／大集合查詢和 context 量測；目前前端 build 的主 JS 約 907.80 kB、gzip 271.11 kB，仍有 chunk 警告，不調高門檻掩蓋。
5. T13／T18：乾淨環境安裝、PDF 字型／Chromium 交付、完整操作驗證與正式入口切換／精確舊碼退役未完成。未 push／merge／對外部署，旧正式 authority 未切換。

**恢復次序：**先讀本頁、tasks、相關 evidence，核分支／dirty／Demo 是否被使用者继续操作；不得以此快照倒回後續資料。先補原件／未明結果恢復接縫，再做受影響故障回歸與真旅程／品質 gate；沿原 T01–T18 推進，不從頭重做。

## 參考資料審核與本次驗證

Owner 新提供的 OpenAI Compaction 參考，已對照本機 SDK／接線與[官方 compaction 指南](https://developers.openai.com/api/docs/guides/compaction)：目前手動完整 `compacted.output` 取代旧接續視窗、不解析密文，保存／採用後才追加新資料，未啟用 server-side automatic compaction。33 項相關離線測例通過，**不是新增真 API compaction 驗證**；不因附件新增雙摘要或永久 event store。

來源差異仍是「所見新基準對原引用舊基準」，不要求追遍中間每次修訂，不增設「改回原文」特殊流程；既有明確確認引用對齊規則不變。

本次完整 unit／contracts **946 passed**、來源相關真 PG **13 passed**、來源 UI **20 passed**、Ruff／mypy 246 files／tsc／codegen check 通過。完整 web 115 項與 build 證據在[T09 UI](t09-source-viewer-ui.md)；不加總重複執行測例。新 sequence 圖實際渲染視檢。完整 PG suite 沒有在本來源切片重跑，不把較早 725 項全套冒稱本次全面回歸。
