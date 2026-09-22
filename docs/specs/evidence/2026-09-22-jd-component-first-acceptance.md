# 新 JD App：先驗元件、再驗整體（2026-09-22）

- 範圍：隔離的合成訪談與測試 PostgreSQL；正式 A／B1／B2 Luna／OpenRouter 角色模型，既有 App-side compaction。未改 Prompt、Memory 分層、JD 業務規則、provider 或正式 compaction 門檻。
- 本輪先分別驗證元件，再執行既有 managed App／背景發布／聊天接合回歸；這些證據不能取代完整真模型＋瀏覽器產品旅程。

## 元件結果

| 元件 | 實際證據 | 判定與界線 |
|---|---|---|
| A 主顧問 | 隔離新文件的真實 Luna 回合完成，員工輸入及自然回答均保存；工具實際讀取訪談原話與 Working State。首回合的 `read_file(/skills/work-scope-interview/SKILL.md)` 回「找不到」，依既有 Skills 設計修復 model-facing 檔案路由後，同文件下一回合讀到該 Skill、自然追問完成。 | A 的訪談與 Skill 讀取通過；不表示 JD 來源或長訪談品質已驗。最初一次執行所在 sandbox 無 OpenRouter 網路，當輪保存原話後失敗；沒有重送該輪，也沒有模型費用。 |
| B1 案例維護 | 真實 Luna 在兩段合成問答上完成一份案例，案例保存兩個來源引用與導覽；原話與權責界線經人工查回相符。 | B1 stage 通過；不是背景 publication 或多案例語意驗收。 |
| B2 工作理解 | 緊接同一案例 stage，真實 Luna 完成一份工作理解及導覽，綁定該案例；未確認的適用範圍沒有擅自宣稱確定。 | B2 stage 通過；本隔離 probe 沒有發布正式 Memory head。B1＋B2 共 7 次實際 OpenRouter 請求，沒有 hidden retry。 |
| App-side compaction | 既有 A／B1／B2 離線邊界測試 19 passed。另以真實 Luna 在低門檻合成對話作元件 probe，2 次實際請求成功：摘要涵蓋至 `a2`，下次 request view 為摘要＋最新 `h3` 原話，canonical 五則對話訊息不變；模型仍能正確回答更正後的權限。完整 App 後續暴露一個 projection 缺陷並已窄修，見下節。 | 元件傳輸及 request-only 語意通過；低門檻只是 test-only 觸發，不宣稱正式 16K 門檻下的自然長訪談已通過。摘要不是原話、案例或工作理解 authority。 |
| 角色化 compaction 真 Luna 驗收 | 以現行唯一 `ContinuationCompactionMiddleware`、三角色 retention instructions 與合成資料各執行一次摘要＋續作，共 6 次外送，全部 HTTP 200；provider `OpenAI`、實際模型 `openai/gpt-5.6-luna-20260709`，usage 為 2,293 input／1,948 output tokens，OpenRouter 回報總 cost **US$0.0027962**。三者 canonical history 均未改，近期未處理輸入逐字保留；B2 固定任務也逐字留在 request view。 | A 的更正、通知 receipt／未完成 Memory 邊界及未解問題都保留；B1 只摘要已處理 CASE-ALPHA，未把尚未處理 CASE-BETA 放進摘要；B2 保留 CASE-A／B 支持與 CASE-C 反證／例外。**但本輪不是全綠：**B2 摘要仍改寫重述了已逐字保留的 fixed task，造成重複 context；A／B1 也出現從「沒有提供」延伸成「未完成／沒有待辦」的輕微負面推論。前者列為 prompt 品質問題，未先改 production。此低門檻 probe 不代表正式 16K 長上下文驗收。 |
| B2 prompt 窄修與真 Luna 重測 | 根因是共用摘要指令要求保留「目前目標」，但後段又要求 B2 不重述 `protected_orientation`，形成互相拉扯；同時沒有明示「未提及不能推論成未完成／沒有待辦」。只收緊既有 system／B2 retention instructions，沒有新增 validator、後處理器、重試或狀態。相鄰離線回歸 **81 passed**；排除兩個既知 Windows ACL 模組後，新 JD App 全套 **3061 passed／322 skipped／0 failed**。 | 同一 B2 反例以真 Luna 重測 2 次外送，均 HTTP 200；846 input／393 output tokens，OpenRouter cost **US$0.0006408**。摘要只保留 CASE-A／B 支持、CASE-C 反證／例外與待解事項；未再重述 fixed task，也未新增「未提供／沒有待辦」等負面推論。固定任務、未處理尾段逐字保留，canonical history 不變。此結果關閉本次 B2 prompt 品質問題，但仍不是正式 16K 長上下文驗收。 |
| JD 寫作 Skill／tool description 真 Luna 與 A 同回合 compaction 反例 | 一個全新隔離文件由真 Luna 自然讀取 JD 寫作 Skill、目前 JD、工作理解、案例與原話，完成 duty、task、O／P／K／S 及 task↔K／S 關係；六筆 JD receipt 均 confirmed／committed，final 為自然繁中且明列尚未知的班別與 KPI。25 次 provider response 全為 HTTP 200，實際 provider `OpenAI`、模型 `openai/gpt-5.6-luna-20260709`；首次錯誤 ref 經新 tool error 指引重讀後成功自修。 | JD 成文方法與 prompt gate **PASS**，但同一員工回合的 request 最後達 177,108 input tokens；25 次累計 2,085,926 input／9,874 output，cost **US$0.37018134**。durable history 下界約 78,816 tokens，`continuation_compaction=null`：現行 A boundary 把最新 Human 之後所有 completed waves 一併鎖住。TDD successor 只讓 Runtime 逐字保護最新 Human、摘要其後已完成舊 wave；舊 v1 state 可讀，v2 加 Runtime-owned `protected_message_id`。真實舊 checkpoint 的 safe boundary 從 `None` 變為 **41**；compaction／A／B1／B2／wire 相鄰離線 **201 passed**。這仍不是修後正式 16K 真模型 gate；在該 gate 前不再以 64 次上限代替 context／費用護欄。 |
| A 正式 16K compaction／JD Prompt 真 Luna | 以 production A middleware／profile、正式 guidance 與 JD Skill 建立 17,467 approximate-token 脈絡；當輪員工原話在首則，後接八組可壓縮 completed waves，最近八則是 Skill、寫作參考、工作理解及目前 JD。正式 `medium／8192` 執行 summary＋main 各一次，均 HTTP 200；provider `OpenAI`、模型回傳 production 穩定別名 `openai/gpt-5.6-luna`。summary 12,255 input／1,543 output，main 4,867 input／1,960 output，cost **US$0.00811258**。 | **PASS。**v2 逐字保留最新 Human 且不把原話複製進摘要；summary 涵蓋至 `tool-8`，最近八則與 canonical history 不變。摘要保存共同工作、權責界線及未知事項，main 自然完成 O／P／K／S，無工具格式、虛構數字或越權責任。較早 test-only `2048` 輸出上限因 main 截斷而安全失敗，cost US$0.01924770；兩次 body preflight 均未送出。整個 gate paid cost **US$0.02736028**。原報表唯一 false 是 evaluator 硬寫日期 snapshot，離線改用 production route 精確比對後全綠，未重送模型。 |

## 發現與窄修

1. A 實際模型選擇 `read_file` 讀訪談 Skill，但 App 在綁定 Memory reader 時覆蓋了已有的 `/skills/` 唯讀路由。按原 [Skills 設計](../2026-09-14-jd-consultant-guidance-and-skills-slice.md)與現有 `analysis_files` CompositeBackend，僅將 Skills 掛回同一 model-facing `read_file`。新 ToolNode 紅燈反例在修正後通過；分層 Memory 通用檔案讀取仍拒絕，原 typed reads 不變。相鄰 App 測試 116 passed。
2. 真實 A active run 的唯讀狀態查詢曾短暫回 `503 service_unavailable`，同一 run 稍後仍完成；Web 原本遇此錯誤就停止自動查回。新增「只對已有 active run 的此種狀態讀取失敗，自動再查一次」；連續失敗後停止並保留錯誤，從不重送原始 POST、模型或 JD 工具。兩項新測試先紅後綠；Web 全套 310 passed、TypeScript 檢查通過。現有 Web package 沒有 `lint` script，因此不能宣稱已跑 lint。後端暫時 503 的精確時序仍未解，不把 Web 保護誤稱為後端根因修復。
3. 完整 JD 回合首次觸發 compaction 時，摘要 prompt 將 canonical `BaseMessage.model_dump()` 整包傳給 Luna，連同私有 `ToolMessage.artifact`、provider opaque reasoning、response／usage metadata 一起送出；實際 prompt 約 63,841 字、35,124 input tokens，2,048 output token（含 reasoning）耗盡後回 `incomplete/length`。Runtime 正確拒絕不完整摘要，JD mutation 尚未發生。最小修正只新增 model-visible projection：保留可見 user／assistant／system／tool 文字與 tool name／args／call ID／result pairing，排除私有來源 artifact、opaque reasoning 與 provider metadata；canonical conversation、完整來源及 digest 不改。投影後同一材料約 8,823 字，真 Luna 在原 2,048 上限完成（5,351 input、1,668 output，其中 reasoning 516）。新增反例後相關集合 138 passed；未新增摘要系統、重試或較高 token 上限。
4. 角色化真 Luna probe 的機械 gate 最初要求 A 摘要逐字保留 `A-FACT`／`A-CORRECTION`／`BG-NOTICE` 測試標籤，因模型保留語意但移除標籤而誤報 A failure；人工核對確認門診故障初判、不得核准 `DB-CHANGE`、背景只取得 receipt 且不代表 Memory 完成、`FOLLOW-RECOVERY` 未知均存在。此為驗收規則過嚴，不是 A 資料遺失，probe 的後續規則已改查產品語意。相對地，B2 雖通過原本只檢查 `B2-TASK` 字串的機械 gate，人工核對發現它把 fixed task 改寫成摘要的「目前目標」；這才是實際未通過項目。沒有為了讓報表變綠而重送模型或修改原始結果。
5. B2 prompt 修正不靠新增架構：共用規則現在要求只記錄輸入明確支持的狀態，缺席資訊直接省略；B2 規則明確要求只寫相對於 fixed task 的進度／差異／未解事項，不另列目標重述 orientation。真 Luna 重測的摘要為四項實質進度，沒有 fixed-task 重述或缺席推論；main response 仍能正確延續比較。沒有改 boundary、digest、checkpoint、request view、Memory、JD 或 provider。

## 完整 App 旅程接續

- 在同一隔離新 JD App／PostgreSQL fixture 中，修後真 Luna 依已發布工作理解與案例按需讀取，完成 `read_case`、兩次 `read_evidence`、JD task create、工作理解讀取及自然 final；provider request 共 13／14 上限，未再追加請求。JD 寫入正確區分本人負責的影響確認、紀錄蒐集、備援測試、交接後監看，以及值班主管的資料庫變更決定權，沒有把夜間備份告警推定成已確認職責。
- Browser 畫面顯示自然 final、1 次已保存 JD 修改與 11 筆實際 change record；兩個來源入口均能回到對應的 canonical 訪談原話。一次唯讀 changes 查回曾暫時顯示連線錯誤，使用既有「重新查看改動」後成功，沒有重送 JD mutation。
- Owner 在畫面確認後執行「撤回這輪 JD 改動」。撤回後目前 JD 不再含「門診掛號系統異常初判與交接」及其成果／要求；畫面仍保留完整對話與該輪歷史。HTTP 查回仍有 14 則訊息，最後 user／assistant 配對與自然 final 均存在；Memory publication head 仍為 revision 1，且既有 publication receipt 仍在。這證明撤回只作用於當輪 JD，不撤回 conversation、來源或 Memory。

## 串接狀態與下一關

- 既有 managed App、真 PostgreSQL 背景 dispatcher／publication、聊天服務接合測試本輪重跑：45 passed。它證明固定模型下，一通知可產生一份正式 publication、B1 完成後 B2 失敗可恢復，以及回執遺失不重複發布。
- **本輪已驗成：**A 發出非等待式背景整理通知、B1／B2 publication、A 下一輪按需讀到案例／工作理解／原話、產生可用 JD，以及 browser 的來源查看、當輪改動查看與整輪 JD 撤回。此證據限於這份隔離合成資料，不等於長期實務訪談品質、所有錯誤恢復或正式 16K compaction 門檻均已驗畢。
- **後續仍需：**依時間優先處理會妨礙實際產出完整 JD 的明顯缺陷與更廣完整 App 旅程。JD 可見來源目前仍指向 canonical 原始訪談；若要新增直接顯示工作理解來源，另依 Owner 已提出的語意問題討論，不由本輪驗收擅改。
- 較早的元件／整體 probe 有實際請求上限但沒有一致的總金額讀值；本次新增的角色化 compaction probe 已由 OpenRouter 六個 response usage receipt 取得 **US$0.0027962**。兩者分開記錄，不用後者回推較早呼叫成本。

## 冷啟動、durable ref 相容與 browser 來源驗收

- 使用同一新 App production build、已初始化 PostgreSQL、正式 API／Web 與 Windows Credential Manager OpenRouter key，在文件 `e4336ddd-65e7-4df4-8d4e-79832e5b03e4` 執行真實 Luna 回合 `0363ee6b-5b87-439a-98f1-0934bfcc0bdd`。模型實際完成 `jd_read → read_evidence → jd_create_task → natural final`；建立「每日巡檢產線設備並處理異常通報」task、兩筆成果、兩筆要求及五筆 source-link change，root run 為 `completed`。
- 前一個反例顯示 model-facing 說明沒有充分區分 `type=container` 的 child target 與 `type=item` 的 durable `container_ref`，模型選錯建立位置。曾嘗試把 item projection 欄位改名，但既有 checkpoint／digest 會把 model-visible projection 當作 durable 讀取內容；舊 checkpoint 因 shape 改變在 provider request 前即被正確拒絕。這證明該 projection shape 已是持久相容界面，不能為了提示模型而任意改名。
- 最終修正撤回欄位改名，只補既有 create tool／transport／contract description：建立 child 必須從 `type=container`、正確 `child_kind` 與 `owner_ref` 選 Runtime 發配的 target，不得把 `type=item` 的 `item_ref`／`container_ref` 當 child target。沒有新 adapter、registry、ref 格式或兼容層。
- Browser 顯示自然 final、已保存 JD 修改與來源入口；「看第 1 段原話」回到正確 canonical 員工訪談。本次沒有再次執行撤回；撤回的 conversation／source／Memory 不受影響證據沿用上節已完成旅程，不能冒稱同一 run 又重做一次。
- 真實 final 曾把內部 `evidence key` 顯示給使用者。來源資料與導覽本身正確，這是對外表達缺口，不是引用或 Memory 錯誤。最小 prompt guard 只要求 final 自然說明依據已保存的訪談原話／案例／工作理解，細節由 App 顯示，不公開 evidence key、ref、UUID、operation ID 或其他 Runtime 代號；未新增前端清洗或第二套引用。focused guidance **9 passed**，尚未為這句文案另送付費模型，故只標離線護欄完成。
- durable-ref 修正後的離線證據：受影響集合 **147 passed／13 skipped**，codegen check 通過；加入上述對外表達護欄後，排除兩個既知 Windows ACL 模組的新 App 全套為 **3,075 passed／322 skipped／0 failed**。Web 為 **310 passed**、typecheck 通過；production build 在一般 sandbox 因 child process `EPERM` 中斷，於允許建立程序的相同 lock 環境重跑後通過。這些環境差異分開記錄，不把首次基礎設施限制寫成產品失敗。

原始合成 probe 結果保存於本機 `.research-tmp/jd-ui-gate-20260922000000000000000000000002/component_*.json`、`role_compaction_live_probe.json` 與 `b2_compaction_live_recheck.json`，不含 credential；本檔保存可查的結論與限制。未 push。
