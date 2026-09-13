# 整輪差異畫面獨立審查

- 日期：2026-09-13；JD-R002／CV-01。審查者未撰寫本輪 UI 修改；作者停止寫入後核對。`api.ts` 是本審查者的前一項實作，因此不把它列作獨立審查證據。
- 依據：[CV-01](../../2026-09-12-jd-change-visibility-design.md) §4–5／7、目前決策及 App 計畫的最新路由。已讀局部 `web/AGENTS.md` 與此版本 Next bundled Server and Client Components 指引；不重新研究框架。
- 範圍：`RunChangesPanel.tsx`、`DocumentWorkspace.tsx`、`JdEditor.tsx`、`run-changes.ts`、`ChangeDetails.tsx`、共用後的 `HistoryPanel.tsx` 及兩個新 UI 測試。零服務／DB／provider，沒有修改產品或作者測試。

## 1. 審查項目與本輪範圍更新

### RCV-UI-R01：進入下一輪後，舊輪整體比較缺少畫面入口

- 狀態：**SUPERSEDED_BY_OWNER_SCOPE**。Owner 在本輪審查後明確表示不用從舊對話查看該輪改動，只需知道當輪 LLM 改了什麼；除非簡單順便才做。主代理據此不採新增歷史 run 檢視。本項保留早先基線的缺口紀錄，並非已修好，也不再阻擋本輪。
- 定位：[DocumentWorkspace](../../../../experiments/jd-relational-app/web/src/components/DocumentWorkspace.tsx) 34–36、50–73 只依目前 `chat.runId` 的狀態載入整輪比較；[ChatPanel](../../../../experiments/jd-relational-app/web/src/components/ChatPanel.tsx) 37–41 的已保存訊息沒有原 run 比較入口；[HistoryPanel](../../../../experiments/jd-relational-app/web/src/components/HistoryPanel.tsx) 39–42 只有逐 operation 歷史。
- 反例：A 先將同欄改掉再改回並完成，畫面正確顯示「沒有淨變更，但曾有保存紀錄」。接著送出 B，即使 B 只是訪談，畫面也只能查看 B 的整輪狀態；使用者無法再從 A 的已保存訊息開啟 A 的整體比較及改回摘要。逐次保存歷史保留，不能取代原輪的固定比較入口。
- 影響：CV-01 §4.2／§5 要求下一輪後仍可找回該輪入口與整輪／逐次差異。此處是現有畫面路徑缺失，不是 API 無法查到。
- 原修正提案（已不採用）：利用已保存訊息的 `run_id` 提供原輪歷史比較入口。新增狀態與 capture UI 超過 Owner 最新所需範圍，作者已撤去該追加；停止寫入後核 `ChatPanel` 相對 HEAD 無差異，`DocumentWorkspace` 只取目前 matching run，沒有歷史選輪狀態或新查詢入口。本輪只保留當輪比較及原有逐次歷史，不再提議此能力。

### RCV-UI-R02：刪除成果／要求時，原所屬只顯示同名任務，缺少可辨識的職責

- 狀態：**CLOSED，作者修正後獨立窄複核 PASS**。
- 原缺口定位：[ChangeDetails](../../../../experiments/jd-relational-app/web/src/components/ChangeDetails.tsx) 13、33 呼叫 `referenceName(container_ref)`；[run-changes](../../../../experiments/jd-relational-app/web/src/lib/run-changes.ts) 原 43–45 解析到 owner 的名稱即停止，不繼續顯示其祖先職責。
- 反例：職責 A、職責 B 各有名稱同為「驗證」的任務，且各自有要求「完成檢查」。分別刪 A 的要求或 B 的要求，實際 `ChangeDetails` 的完整 HTML 相同，只有「要求：完成檢查」「原所屬：驗證」，連展開內容也看不到原職責。
- 獨立重現：Node 24.19.0 stdin probe 載入現版 TSX，使用 Next bundled Babel 與真 React／MUI `renderToStaticMarkup`；before／after 均由實際 `projectView` 核對關聯。兩個不同刪除情境的 HTML（僅移除 style 標籤）相等，且皆不含職責 A／B 名稱。這是合成靜態渲染，不是假稱瀏覽器點擊。
- 影響：CV-01 §4.3／§7 要求刪除原文與原所屬可辨識；名稱可重複時，現有直接可見的原位置不足以辨認被刪項目。
- 最小修正：沿既有固定歷史 view 的 container→owner 關聯顯示可讀的完整所屬路徑，例如「職責 A → 驗證」；用於刪除直接清單與完整對照。無需新欄位、Web diff 或解析 opaque refs。新增不同職責／同名任務刪成果或要求反例。
- 實際修正：[run-changes](../../../../experiments/jd-relational-app/web/src/lib/run-changes.ts) 43–57 沿已提供的 owner／container 取得完整職責／任務路徑，缺鏈或重複關係明示無完整所屬；沒有推導 domain 或改模型參數。作者新增 `deleted identical requirements under identical tasks remain distinguishable by their duty path`，先 1 FAIL 重現兩個 HTML 相同，再修成可見原職責；本審查者獨立重跑同反例與原 scope tests 通過。

## 2. 已核對且未見新增 P1／P2 的接點

| 接點 | 實際核對 |
|---|---|
| 晚回覆與範圍 | effect cleanup 的 `live` 與最後 render 的 API／dataset／document／key gate 都存在；matching run 同時核目前 run 與尚未閉合的原請求。舊 capture 不供新輪 marker |
| 同版與人工候選 | `visibleRunMarkers` 要求目前 revision ref 等於 E，且無 dirty、文字／表單候選或待比較狀態；端點讀回另核 S／E refs。較晚版本保留歷史並清目前 marker |
| 欄位與項目 | 用既有 stable item ID／field key，不依名稱或解碼 ref；profile 只標真正改欄位；move／reorder 不標成正文重寫；已刪項目無假目前編輯入口；共用定義影響任務、解除引用與 source target 有標記 |
| 刪除內容 | 完整多行原文及原所屬位於收合 details 外；RCV-UI-R02 修正後也能直接辨識不同職責下同名任務的刪除 |
| 差異事實 | none、改回無淨差異、discontinuous、unconfirmed 話術分開；不連續不冒稱單一 S→E；現有聊天仍列各次 committed 差異 |
| 讀取與副作用 | key 只隨 committed operation set／settled 證據與範圍改變；相同狀態觀察不反覆讀 capture。查看只沿唯讀 API、展開及頁內連結，不提交 command，不新增接受／核准狀態 |
| 可及性靜態接點 | 標記有文字，不只顏色；實際 Button anchor 與原生 details／summary 可用鍵盤，loading 有 status。沒有以無障礙程式碼核對代替實體鍵盤／焦點／捲動驗收 |

## 3. 本審查者實際執行

作者停止寫入後，執行 [run-changes-view](../../../../experiments/jd-relational-app/web/tests/run-changes-view.test.ts) 與 [run-changes-render](../../../../experiments/jd-relational-app/web/tests/run-changes-render.test.ts)：**17 PASS，3464.0243 毫秒**。Node 實際版本 **24.19.0**。其中有真 React／MUI 靜態 HTML，沒有執行 React effect、點擊、捲動、網路或瀏覽器。

RCV-UI-R02 修正、RCV-UI-R01 追加撤除且作者再次停止寫入後，獨立執行同兩檔：**18 PASS，2558.4723 毫秒**。這次核對限定完整所屬、當輪 matching scope／版本與人工候選 gate 保留、無新增歷史選輪入口；沒有重跑全 Web 或擴張需求。此 18 與先前 17 是不同時間的執行結果，不相加。

另以唯讀 stdin probe 重現 RCV-UI-R02；未留下新的程式／測試檔。首次讀取命令曾因已在 web 目錄卻重複路徑前綴而找不到兩個檔案，隨即用正確相對路徑讀回；此為審查命令錯誤，不計產品首敗。

作者報告的初版全 Web 289 PASS、最後新增三案後 17 PASS／TS PASS 是作者證據，沒有重算成本審查者全組結果。[契約與 client 結果](contract-client.md)獨立記錄 157／42／98 與生成／scoped TS，不把這些執行數字混加。

## 4. 完成界線

**本輪指定範圍獨立窄審 PASS，無剩餘 P1／P2。** RCV-UI-R01 已被 Owner 最新範圍覆寫，不列未修阻擋；RCV-UI-R02 已實作修正並獨立複核 CLOSED。本報告不宣稱原 CV-01 所有歷史能力通過。未啟服務、未跑真瀏覽器、未驗讀取 HTTP 的真網路競爭、來源原話回查、整輪撤回或自然模型品質；上述項目不能從靜態 UI 或純投影 PASS 推得完成。
