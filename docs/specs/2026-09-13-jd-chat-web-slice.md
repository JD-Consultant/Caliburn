# JD 同頁聊天、原話保護與已保存改動

- 日期：2026-09-13；JD-R002／RS-3、RS-4 局部；**同頁接線及有界修正完成，瀏覽器連線驗收仍有未解事項**。不是完整 App／自然顧問交付。
- 有效需求及完整交付沿[總計畫](../plans/2026-09-13-jd-relational-app-implementation.md)。Excel 延後；ADR0075 Proposed，production ADR0060 不變；本片零產品 provider 呼叫。
- 前置：[同頁互動與官方來源](evidence/jd-relational-chat-web/ui-preflight.md)、[瀏覽器草稿交接](evidence/jd-relational-chat-web/draft-handoff-preflight.md)、[上一片 HTTP](2026-09-13-jd-chat-http-slice.md)。

## 本片使用流程與範圍

同一畫面左側訪談、右側唯一六章 JD。使用者送出前，App 先確認手動文字真正保存成功；未完成的新增／管理表單保留，先完成或取消表單再送出。AI 整理期間可看稿、看已保存的改動及輸入下一段，下一段不自動送出。Enter 保持換行，送出用明確按鈕，組字事件尚未結束時不能送出。

聊天原文／原請求先存於本機瀏覽器候選，再發 HTTP。重開只查原回合，不自動發新身分重送。AI 回覆是否完成、原話是否保存、JD 實際修改是否保存分開呈現。已確認的每次修改可在同畫面查看完整前後內容；沒有逐项接受流程。

模型未啟用時，明確顯示服務的 `ai_unavailable`，原話取回輸入區供修改，手動 JD 仍可用。這個取回只承接**原 start POST 的明確未啟用回覆**；逾時、一般錯誤或 GET 查無資料都不能當作未保存。若原話確定未存而後面已打新文字，保留兩者，不能用取回動作覆蓋新文字。

**完成界線：**逐次已保存差異是施工中的可用接點；[CV-01](2026-09-12-jd-change-visibility-design.md)完整整輪 S→E、目前稿欄位標記／刪除清單與[整輪 JD 撤回](2026-09-12-jd-ai-turn-undo-design.md)仍須完成。此片不以聊天摘要或歷史按鈕取代已選需求。Memory、來源原文與自然模型品質仍按總計畫接合。

## 框架與有限接線責任

| 責任 | 本片做法及界線 |
|---|---|
| Python App／原生 Saver | 沿已驗 ChatService 與 LangGraph root/source 保存；訪談不是另一張新聊天表。App 回真實 run、input 與 JD receipt 事實。 |
| 正式 HTTP schema | 新增固定歷史頁 `anchor_run_id`，直接指向該 snapshot 的原回合；不是永遠最新的 run。由原 SSOT 生成 Python／TS，不交模型填。 |
| 歷史視窗 | 初頁為最新最多 50 則，頁內按先後呈現；同 anchor 的 cursor 向較早訊息翻頁。Web 前接較早頁，明示刷新新視窗時整體替換，不跨 anchor 猜合併。私有簽章格式及 salt 升 v2，舊 forward token 明確拒絕，不把相同 offset 靜默改義。原生已存訪談不改寫。 |
| Browser owner | `JdSession` 是同文件唯一 Web Lock／候選交接責任；手改、聊天原請求共用短 IndexedDB 交易佇列，HTTP／provider 不放入該交易。 |
| 瀏覽器候選 | 同 row format 2 增聊天文字與 exact 原請求，與手動表單分開。原 v1 嚴验，在取得 owner 的 claim 短交易中補空聊天欄位；不批次重寫舊列。IDB database version 2 以原生 versionchange／blocking 關閉舊連線。原人工候選與未知 operation 保留。 |
| 只讀觀察／控制 | `ChatController` 不另取 owner 或建立持久資料；消費同一生成 API、依原 ID 查回。正常 running/closing 每 2 秒單飛 GET，單次請求沿 15 秒期限；首次錯誤／需人工恢復時停自動觀察。關頁停止觀察，不等於取消服務。秒數是本案起始設定，非大廠統一規定。 |
| UI | React／Next Client Components、MUI 免費 Core 元件；只顯示原生已保存 user／assistant 公開文字，不顯示 tool／thinking。欄位格式、scope、保存及差異規則仍由 App 決定。 |

未新增 Query 庫：目前是一份文件、一個觀察者，其餘元件接收相同結果；沒有多個獨立讀者共享 cache 的需要。[Next 現行指南](https://nextjs.org/docs/app/guides/client-side-data-fetching)把新增庫與共享 cache／refetch／dedupe 需求相連，而不是要求所有互動都安裝。若後續出現這些真實需求再評估，並非框架不可替換。

最新對話先顯示的頁面選擇，參考官方 Conversations list 的 order／cursor 能力，查閱、適用限制見[API 審查](evidence/jd-relational-chat-web/api-review.md)；本案頁內順序與 opaque token 是本案映射，不能稱 OpenAI／Anthropic 共用本格式。整體 UI 研究也記錄 Canvas 可用性更新，未把舊版產品行為冒稱現行共識。

## 驗收紀錄

- 最後前端完整純測 **233 PASS／0 FAIL**，558.2858 ms；TypeScript 與 Next production build 通過。前次 229 項完整原輸出保留，最後四項新反例及最後摘要另記。這些不等於 TSX 真瀏覽器或實體輸入法已驗。
- 固定歷史新語意：後端 history／schema／service／HTTP **184 PASS**；生成檢查及生成 TS／consumer 通過。最後加兩個 test-helper 檔共同跑 **219 PASS**（184＋35）、1 個既有 AnyIO deprecation warning，13.90 s；[實際輸出](evidence/jd-relational-chat-web/backend-tests.txt)。未改寫原生歷史或資料表。
- 已修並留反例：舊回合慢查詢覆蓋較新人工畫面、聊天 RAM 原話無法重存、初次 history 讀取失敗後刷新无效、刷新停在舊 terminal run，以及新 B 回覆未知時沿用 A 已完成狀態。對應 controller／交接窄組由 34 增至 **38 PASS**。UI 另依同回合的 `input_state` 呈現原話是否保存，不用「目前頁看不到」推斷未保存。
- [暫存獨審](evidence/jd-relational-chat-web/draft-review.md)、[API 獨審](evidence/jd-relational-chat-web/api-review.md)、[controller／UI 審查](evidence/jd-relational-chat-web/controller-ui-review.md)及[最後 run 標籤窄審](evidence/jd-relational-chat-web/final-run-label-review.md)分別記範圍與反例來源，不把自修當獨審。最後窄審另直接用實際 React／MUI 靜態呈現驗 **7 PASS**；靜態 HTML 不代證瀏覽器事件。
- [第一組真瀏覽器](evidence/jd-relational-chat-web/browser-first.md)完成送出前原話重開、第一輪 AI 新增完整任務、查看確切修改、人工職稱保存、第二輪純訪談不改 JD、下一段未送出文字及兩輪對話關頁重開。第一輪 fetch 曾中斷，明示查原回合後恢復；**不是首次無故障通過**。
- [獨立真 PG 唯讀核對](evidence/jd-relational-chat-web/db-browser-first.json)：head 3、revision 3、operation 2（AI／manual 各一）；1 任務、2 成果、1 要求；current／snapshot／digest 及完整 invariant 一致。原生 Saver 為兩筆 Human／兩筆完整公開 AI，兩輪 completed／closed，第二輪無 JD 保存；2 次 start、4 次固定 SDK 回覆、writer 2 次，沒有重播。
- [限定重現](evidence/jd-relational-chat-web/browser-second.md)在建立文件階段重現 fetch 拒絕，尚未進 AI。服務端 200／send-end／CORS 對照與獨立 localhost GET 正常，仍不足確認瀏覽器失敗原因。沒有調寬 CORS 或加入自動重送；此項維持 OPEN。過程找到對話框遮住錯誤的獨立缺口，已小修並在真瀏覽器驗更名失敗提示與原輸入保留；原建立 identity 四項回歸通過。
- Node 測試 worker 曾遇 sandbox `spawn EPERM`；用獲准原生 worker 或官方 `--test-isolation=none` 執行後才計 PASS。首敗與最後結果分開，沒有以執行器失敗當產品反例。

## 下一步及未驗範圍

下一個有界單位先取得足以定位上述 fetch 拒絕的安全傳輸診斷；已有證據不能判定時保存現場，不能為通過而弱化驗證或反覆重送。這不阻止按已定設計完成 CV-01 整輪淨改動與其同頁呈現，但兩者的完成證據分開。

CV-01 完整標記／刪除清單、HR-02 整輪 JD 撤回、Memory／來源、原 run 深歷史查找、實體 IME、真 v1 升版競爭、其餘取消／故障旅程、日常 AI 啟用、自然模型與真人驗收仍待完成。原付費批次授權要求不變；本輪沒有自然模型費用。測試宿主及臨時 Web 已停止，兩個專用測試 DB 保留，沒有動正式產品。
