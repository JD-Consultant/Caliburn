# JD 原保存回覆遺失、重開查回與顧問接點

日期：2026-09-13；Topic：JD-R002；RS-3 局部驗收通過，RS-4 前置收斂。承接[六章手動管理](2026-09-13-jd-manual-ui-and-browser-drafts-slice.md)與[施工計畫](../plans/2026-09-13-jd-relational-app-implementation.md)。本次仍是隔離 App，ADR0075 Proposed／production ADR0060 不變，零產品模型呼叫。

## 1. 完成效果

**真正保存完成但畫面沒有收到回覆時，關頁重開後可查回原次結果，恢復編輯，不重送新增。**固定合成任務經瀏覽器送出，真 Windows 宿主／PostgreSQL 確認提交；測試閘門只延後 HTTP 回覆，沒有替換業務 writer 或製造假回執。

另外修正文件對話框關閉時的封存 fallback：原先 `dialog=null` 仍在 MUI 退出動畫渲染期間落入封存文案；更名時若名稱非空，按鈕也可能仍可用。現在關閉即卸載 Dialog，metadata 入口只接受更名／封存狀態。取消更名／建立經新 production build 的瀏覽器窄驗；取消不改文件目錄。

這次沒改 domain、資料表、HTTP 契約或保存流程；實作變更只在 [Workspace](../../experiments/jd-relational-app/web/src/components/Workspace.tsx)，其餘為測試 helper、實證與研究紀錄。

## 2. 官方依據與本案映射

| 依據（查閱 2026-09-13） | 官方事實與本次使用範圍 |
|---|---|
| [AWS 安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | caller intent／token、去重與副作用的交易關係、原結果及遲到請求。此驗收檢查本案原 operation 查回，不把網路斷線當資料回滾，也不因未知結果換 key 重送。AWS 未指定本案表名／UI 按鈕。 |
| [AWS 六角架構](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html) | 業務與 UI／資料層等外部接點分離。本案人工與 AI 共用同一命令／保存規則；測試閘門放在 HTTP 回覆出口，不在 domain 添加故障分支。這是有界映射，非新增通用 ports 框架。 |
| [ASGI HTTP 2.5](https://asgi.readthedocs.io/en/latest/specs/www.html) | 在送出 `http.response.start` 前等待，200／202 都涵蓋；disconnect／send 結果不是接收端 ACK，也不是 writer 退出證據。規範版本 2.5（2024-06-05）仍是現行契約。 |
| [MUI Dialog](https://mui.com/material-ui/api/dialog/)／本機官方原碼 | MUI 9.4.0（穩定、MIT）Dialog 使用 `closeAfterTransition`。此次從實際安裝 `Dialog.js` 核對，修法使用 React 正常條件渲染與業務入口 guard；沒有自製動畫元件。 |

ASGI／Starlette／Uvicorn 適用版本、原碼核對與操作步驟見[helper 說明](../../experiments/jd-relational-app/tests/support/ui_response_gate_notes.md)。沒有宣稱所有大廠採相同 App schema 或故障模擬方式。

## 3. 真瀏覽器與資料庫證據

環境：Windows 原生 DPAPI／host、PostgreSQL 18.6 專用 55436、FastAPI 0.141.1／Starlette 1.6.0／Uvicorn 0.52.4；Web 使用已固定 Next 16.3.5／React 19.3.0／MUI 9.4.0。無 provider、無 production 連線。

合成 fixture：`.research-tmp/jd-ui-gate-5f6c67d9efb74d9db1482648845b4137`；資料庫 `caliburn_jd_setup_test_5f6c67d9efb74d9db1482648845b4137`，只明示建立及初始化一次，資料保留。文件 `1bcd7f2a-060f-454c-97bb-06b15c7c6dc4`。

| 實際步驟 | 觀察及驗證 |
|---|---|
| 建立「保存回覆遺失驗收」 | [初始 DB](evidence/jd-relational-ui-reply-loss/db-catalog.json)：head1、0 任務、0 編輯 operation。 |
| UI 新增「定期檢查」及一段合成責任範圍，按完成 | 真 storage 已 committed；[回覆仍被暫停](evidence/jd-relational-ui-reply-loss/gate.held.json)時，另一條[唯讀 DB 連線](evidence/jd-relational-ui-reply-loss/db-held.json)確認 head2、1 任務、1 operation，current 與 snapshot/digest 一致。 |
| 瀏覽器原生 15 秒 fetch timeout | 畫面「保存結果待確認」／「查回原保存」，暫停新保存；沒有誤報已保存或已回滾。 |
| 釋放遲到回覆後，關閉 tab，開新 tab 並選回同文件 | 仍顯示原保存待確認；已保存任務可讀，但手改暫停。這次是正常關頁重開，不是 OS crash。 |
| 按一次「查回原保存」 | 畫面改成「已保存」、恢復欄位編輯，沒有殘留新增表單；[HTTP 計數](evidence/jd-relational-ui-reply-loss/gate.routes.json)為 1 POST／1 原 operation GET，[writer](evidence/jd-relational-ui-reply-loss/writer.observations.json)只執行一次。 |
| 再核對 DB | [重開後](evidence/jd-relational-ui-reply-loss/db-recovered.json)任務 ID、head、原 operation、digest 都與回覆暫停時相同。獨立 reviewer 另開唯讀連線核對 [PASS](evidence/jd-relational-ui-reply-loss/independent-db-review.json)。 |
| 對話框修正後重建，開同文件取消更名與建立 | 關閉後 DOM dialog 數為 0，沒有封存標題；[DB](evidence/jd-relational-ui-reply-loss/db-dialog.json)仍只一份文件、原名稱、未封存、metadata_version1，JD head2 不變。 |

重現所需的[唯讀探針](evidence/jd-relational-ui-reply-loss/db_readonly_probe.py)只允許此類新 fixture，輸出不含正文；`catalog → held → recovered → dialog` 分階段執行。正常 helper 停止後，[Saver close](evidence/jd-relational-ui-reply-loss/serve.finished.json)及[程序真退出](evidence/jd-relational-ui-reply-loss/process-exit-check.json)分開核對。沒有刪 DB 或清理 volume。

## 4. 測試、首敗及審查

- [23 項純 ASGI／CLI 測試](evidence/jd-relational-ui-reply-loss/gate-tests.txt) PASS：200／202、commit＋release 雙條件、有界等待、其他 GET、一次 arm、斷線、原 operation、route 計數與固定 fixture 範圍。pytest cache 有一項 Windows 存取警告，案例全部執行；未改 ACL。
- [99 項 Web 測試](evidence/jd-relational-ui-reply-loss/web-tests.txt) PASS；[新 production build 與 TypeScript](evidence/jd-relational-ui-reply-loss/web-build.txt) PASS。Python production 沒有改動，未重跑上輪 1540 項全組；本輪不把舊結果列成新執行。
- 首敗保留：helper 開發初次 import collection 錯誤及兩次 pytest 暫存 ACL 失敗；改明示 repo 測試目錄後通過。root 唯讀探針初次缺 `src` import 路徑，補明確路徑後才取得 DB 證據。這些不是產品保存失敗。
- 獨立審查發現 helper 原設定可能在核對前選到其他 DB；已改為每次真 ConfigFile read 先核 fixture，包含兩讀間換檔反例，窄複核 CLOSED。此修正只在測試 helper。
- Workspace 關閉修正已由非實作者獨立 diff 審查 PASS，無剩餘 P1／P2；其畫面與 DB 效果由 root 上述瀏覽器窄驗。

**通過限制：**真瀏覽器本次實際攔截 HTTP 200；202 只有控制流單測。沒有驗證斷電、瀏覽器程序 crash、儲存損壞、所有網路故障、實體 IME、真模型或真人。此結果不代表完整 RS-3／成品交付完成。

## 5. 下一施工單位

[顧問 context 前置](evidence/2026-09-13-jd-consultant-context-preflight.md)已核 OpenAI、Anthropic 及 LangChain／LangGraph 官方接點，停止同層廣搜。保留原話、request-only notice、完整回覆及通知邊界共同保存；SDK 缺終端事件仍回 snapshot 的[離線反例](evidence/jd-relational-context/anthropic_stream_closure_probe.py)已保存，不能只凭 SDK 方法名稱宣稱回覆完整。

**下一單位：**閉合實際 `create_agent`／provider adapter 相容版本及 wire，將人工通知與模型回覆接到原生 graph／Saver；先以固定回應驗 AI 改→人工改→AI 續改、純訪談不改、回覆／保存失敗及重開。不新增第二份 Memory／原始來源權威，不把本前置文件當成 AI 已接好。選區、來源原文、還原／整輪撤回及日常維護沿既定計畫續作，Excel 延後。
