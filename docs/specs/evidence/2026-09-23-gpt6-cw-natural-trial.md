# GPT-6 Luna C-W 自然訪談：首批真實 App 驗收

- 日期：2026-09-23
- 範圍：正式新 JD App `experiments/jd-relational-app`，隔離 PostgreSQL／Saver／Store，單一 OpenRouter credential、GPT-6 Luna Responses／OpenAI-only；不是舊 `apps/api`／`apps/web`。
- 狀態：**PARTIAL／STOPPED**。本批不構成完整 JD 或 Browser 驗收。
- 凍結程式：`c97e172f04d8ac71ddb5aed8545cfbf43dfc1e42`。

## 方法與第一個環境邊界

使用既有 P3 有界試跑入口；合成員工僅按 [C-W 扮演卡](jd-product-p3-calibration/employee-card.md)回答顧問的自然追問，沒有把卡片、oracle 或工具指令送給模型。最多 12 次員工輸入、180 次實際 provider 請求、US$1.00；沒有 fallback 或自動重試。

第一個隔離目標的 Codex IAB 在建立文件前的 `POST /api/document-creations/lookup` 出現 response-body 讀取失敗：API 端已完整送出 200 與 body，但 Browser 未取得內容，因而沒有進入 create；該目標 0 筆模型請求、0 份文件。先前同 build／API 的 Stable Chrome 成功證據仍成立，但本批 Chrome 自動控制被 Windows Computer Use 的 URL-confidence 限制擋住。Owner 允許本輪先略過 Browser，**不將 API 成功冒稱 Browser PASS**，也不為 IAB 改 CORS、retry 或建立語意。

## 真模型與資料結果

第二個隔離目標 `jd-ui-gate-e36127b671a744c4b0c8eff4ed485096`，dataset `952c7671-60c2-4af4-badc-76eecc208bd4`，文件 `45f4f177-8ecc-4e12-8791-23898de2ba7a`。從正式 App API 建立文件；7 次自然員工輸入涵蓋收貨、短少差異、出貨、庫存查核、未查證的盤點頻率及兩案差異。前 6 輪 `completed`、原話與回答可查；第 7 輪要求先根據已知內容形成一版 JD，尚未完成。

- 正式 A 自主通知背景；同一帳本觀察到 A、B1、B2 真實 provider 請求。最新 Memory head revision 3，Store 有 3 個案例、3 項工作理解與各自 guide。抽查內容保留「盤點頻率尚未查證」「差異後續責任不明」「試算表欄位／用途不明」，沒有把未知直接改寫成確定。manifest 含案例到對話的來源引用及工作理解到案例 digest 綁定；這是局部忠實度觀察，非完整來源／品質驗收。
- 第 7 輪 Saver 末端顯示 `jd_read → read_file → read_work_understanding → read_case` 均有成功工具結果；之後一筆 A Responses 請求 90.008 秒未取得可結算回覆。現行 A client 設定單次 90 秒、hidden retry 0；帳本以 `transport_unknown` 停止。這個時間吻合客戶端 deadline，**但缺原始傳輸例外與服務端完成證據，不能斷言 provider 真的執行失敗或唯一根因是模型推理慢**。
- 本批共 59 筆實際 provider 請求；58 筆已結算 US$0.031256040，最後 1 筆未知，保留 US$0.268644 的保守預留，不當成零費用。停止後沒有再送模型請求，也沒有重送第 7 輪。
- 第 7 輪 `run_status=failed`、`input_state=saved`、`jd_effects.state=settled`、無 final assistant 訊息；真實 JD writer execute 為 0。JD 仍只有初始結構，沒有任何內容 item。這是安全的 partial failure，但「產出完整 JD」未通過。
- 依既有停止入口正常關閉 App 與 Saver；另以 inspection-only 正式新 App 重開同一資料庫，查回 1 份文件、13 則已保存聊天訊息、第 7 輪相同失敗狀態與空 JD。一般中斷／重開後的已保存資料查回在此案例通過；不是未送出輸入或草稿 crash recovery 的承諾。

## 待處理與停止線

目前不重開 Memory、Working State、JD Domain、Prompt 或 provider；不為一筆 timeout 加自動重試，也不把 tool 成功誤稱 JD 已寫入。先核對 A 的 90 秒期限與 GPT-6 high 推理真實延遲、鎖定 SDK 的 timeout 行為；若調整，只改既有 model profile、保留 0 retry／同一費用及保存權責，再做受影響回歸與新一批有界自然驗收。原帳本維持 stopped，不清除未知預留。

Browser 的建立／自然訪談／改動查看／來源／撤回仍 **OPEN**；人工 JD 完稿品質、晚期更正、手改願望與來源區分、16K 長上下文及完整 B1／B2 語意也仍 **OPEN**。本記錄不覆蓋先前有限 provider smoke 或固定合成 Browser 證據。

## 後續：A 單請求期限的離線窄修正

2026-09-23 只改正式新 App 的 A 模型工廠預設 `request_timeout` 由 90 秒為 300 秒；B1／B2、同一模型／Responses endpoint、零隱藏重試、支出帳本與 JD／Memory 權責不變。測試先證明舊工廠回傳 A=90／B1=B2=300 的紅燈，再驗證 A=B1=B2=300 的綠燈；受影響集合 **44 passed／4 skipped**，完整新 App 離線 **3,172 passed／323 skipped／0 failed**。首次完整執行受 Windows 沙盒 pytest 暫存 ACL 阻擋；可存取環境重跑後沒有該錯誤，既有 warnings 為 95。

這只驗證新 client 設定已送到既有模型工廠，不把「延長等待」推論為前次根因或品質修復。前一批 `transport_unknown` 原帳本繼續停止，未知費用預留不清零；下一批必須使用新的隔離目標／帳本與明確上限。Browser 因 Codex 自動控制受限暫緩，仍獨立 OPEN，不以 API 旅程代稱通過。
