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

## 第二批獨立 C-W 自然試跑：A 摘要輸出截斷

第二批使用另一隔離目標 `jd-ui-gate-c13dd32e24bc475183473cca696db82c`、dataset `3ffc3327-9a8c-4835-860d-6f2df35d86d7`、文件 `7ad1cc29-9f1d-492c-bd9b-ea3143560eae`，凍結程式 `ae93fd3c9bdc01af4f19a4ae8ef3a0c2044f30b8`。仍限最多 12 次員工輸入／180 次實際 provider request／US$1.00，GPT-6 Luna Responses、OpenAI-only、`store=false`、零 hidden retry；沒有使用前批未知請求或重送前批第 7 輪。正式新 App API 建立文件；初次請求漏帶正式 dataset header 得到 `409 dataset_changed`，依既有契約補上後才進入自然訪談，未改產品。前 6 輪均有 final，A 自主通知背景 B1／B2；第 7 輪要求依已確認事實形成暫定 JD，未確認的盤點頻率維持待查。

第 7 輪正式 JD writer execute 為 **0**，`run_status=failed`、員工原話 `saved`、JD effects `settled` 但結果空、無 final。第 49 筆實際模型請求是 A 的 continuation summary，wire 的 `max_output_tokens=2048`；服務端 HTTP 200 卻回未完成。P3 test-only 帳本按既有 fail-closed 規則停在 `provider_response_incomplete`，48 筆已結算 **US$0.027235260**，末筆保留 **US$0.264036** 的保守未知額度，不當成零費用或逕自解除停止；App 與 Saver 依既有 stop 流程確認關閉。

只針對該筆 OpenRouter generation ID `gen-1790128923-QJZK4Si2WZ9VwME2iJ8Q` 做一次唯讀 metadata 查詢，回報實際模型 `openai/gpt-6-luna-20260922`、provider `OpenAI`、tier `default`、`finish_reason=length`、`native_finish_reason=max_output_tokens`、completion 上限 2,048，其中 reasoning 1,611、可見輸出 458 tokens，`total_cost=US$0.0013058`、未取消。這是獨立的服務端費用與截斷證據，**沒有回寫或結清原 P3 帳本**。與首批 90 秒 `transport_unknown` 不同，本批失敗是已證的摘要輸出額度不足，不能把兩次都歸因於 timeout，也不能宣稱 JD／Browser 通過。

官方 [OpenAI Reasoning 指南](https://developers.openai.com/api/docs/guides/reasoning)（查閱 2026-09-23）說明 `max_output_tokens` 同時涵蓋 reasoning 與可見輸出，耗盡時可能回 `status=incomplete`／`incomplete_details.reason=max_output_tokens`。本案沒有因此新建摘要引擎或降低 A 推理等級；只把正式 A summary 的有界上限從 2,048 提高到 B1／B2 已使用的 **8,192**，通用 profile default 仍 2,048。與前批相同，必須在另一個新隔離目標以現行費用閘門再次自然驗證；原失敗回合不重送。

## 第三批獨立試跑：8,192 摘要越過首敗，但 JD 仍未產生

隔離目標 `jd-ui-gate-679488ebeae946ae904bfb60102b74fe`、dataset `ad97e073-6599-4c36-85d6-714a5b04c893`、文件 `6fbd6142-73ff-4286-8285-73e7257a1170`，凍結程式 `ae9cc2eb7f40753660aedbd7cad135bfaa523f6e`。同一 C-W 扮演卡、正式新 App API、12 輪／180 模型請求／US$1.00 獨立閘門；開場照卡片，後續只按實際追問回答。前六輪 `completed` 且原話與回覆保存，A／B1／B2 均有真模型請求；第七輪請求先就已確定工作形成暫定 JD，未查證盤點頻率維持未知。

第七輪多筆 A `max_output_tokens=8192` 請求已正常結算，確實越過第二批原本的 2,048 摘要截斷點。然而顧問在同一輪的 Saver 中呼叫 `read_file` **6** 次、`jd_read` **3** 次、`read_work_understanding` **6** 次、`read_case` **4** 次及 `read_evidence` **5** 次，JD writer 工具 **0** 次。inspection-only 查得最新已保存摘要有工作事實、未知、JD／Memory 讀取及引用線索；同樣資料反覆讀取是真實觀察，但**不能據此斷言唯一原因是 compaction、Prompt 或模型品質**。JD 編輯 Skill 明文允許已足夠理解的部分先寫、未知留空，因此這是待定位的「使用者要求暫定 JD，卻未進 writer」語意／進度缺口，不以修改 Skill 或新增 Agent 猜測修復。

第 **110** 筆實際 provider 請求（A、8,192 上限）HTTP 200 但回覆未完成，P3 閘門以 `provider_response_incomplete` 停止，109 筆已結算 **US$0.075124560**、最後一筆保留 **US$0.268644** 未知額度。第七輪 `failed`、員工輸入 `saved`、JD effects `settled` 但結果空、無 final；JD writer 仍 0。依既有停止入口確認 App／Saver 關閉，原帳本不重送、不清零。對最後一筆 generation ID 的唯讀 metadata GET 回 **404**，相鄰成功第 109 筆同端點／同 credential 回 **200**，所以不能由此次 404 推定錯誤 key 或憑空推算末筆費用，也不能把這次 8,192 未完成再歸因於 `max_output_tokens`；服務端具體 `incomplete_details.reason` 尚缺。

官方 [OpenAI Reasoning 指南](https://developers.openai.com/api/docs/guides/reasoning)與 [OpenRouter Responses 契約](https://openrouter.ai/docs/api/api-reference/responses/create-responses)（查閱 2026-09-23）都描述 `incomplete_details.reason`；本次 test-only P3 閘門原先只保存概括的 incomplete 狀態，未保存該安全枚舉。離線反例先紅後綠後，僅補記受限的 `observed_status`、`observed_incomplete_reason` 和已回覆的 `observed_cost_usd`，**不保存回應內容、不把 observed cost 當成 settled、不解除未知預留或增加重試**。本批原帳本無法回填缺失原因；後續先從此證據缺口和重讀路徑作定向診斷，再決定是否需要產品變更。Browser、JD 初稿與最終成品質量仍 OPEN。

### 第三批 Saver 的唯讀續查：摘要頻率與工具可見性

在同一隔離庫以 `unavailable_consultant()` 開 inspection-only App，唯讀回查第七輪 child checkpoint 歷史，未恢復執行、未送模型或寫 JD。該輪共觀察到 **20 次**已保存的 A continuation summary 更新；後段每完成一組工具呼叫／結果便推進一次安全摘要邊界。現行 A profile 的觸發點是**完整 request 約 16,000 input tokens**、保留最近 8 則 canonical 訊息，不是 GPT-6 Luna 服務端 context 已滿的證據。對應 P3 帳本的 A 主請求有約 20k–23k input tokens，A 摘要請求另行結算；這是可量測的額外模型往返與成本，不表示摘要內容必然不正確。

同一 Saver 工具序列顯示第七輪 `read_file` 6、`jd_read` 3、`read_work_understanding` 6、`read_case` 4、`read_evidence` 5，**24 筆 ToolMessage 均為 success**；現有 execution guard 的「修正同一失敗」規則因此沒有觸發，不能把這些讀取稱作工具錯誤重試。摘要曾把較早 `jd_read` 的完整結果移出 request tail，模型後來重讀是可觀察事實；但最末 `build_request_view` 仍逐字包含當輪員工「先寫暫定 JD、未知留待確認」的輸入，並包含最近一次 `jd_read` 結果與兩筆工作理解結果。故**沒有證據說當輪要求或所有 JD refs 已被壓縮掉**；摘要頻繁和未使用 writer 有關聯，不足以證明單一根因。

[OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction)、[Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)與 [Anthropic keep-recent-turns](https://platform.claude.com/docs/en/build-with-claude/compaction-keep-recent-turns)（查閱 2026-09-23）支持按實際 context 管理長任務、保留必要近期工具往返；**沒有一家規定本產品必須用 16K 或改用其原生 compaction**。本案仍沿既有 App-side compaction／canonical 保存權責；下個診斷 gate 應先辨明新 P3 `incomplete_details.reason`，再用同一正式 request 的摘要頻率、近期 tool-result 保留及 writer 選擇作窄比較。不以本次觀察直接提高 trigger、改 Prompt／Skill、加入成功讀取防迴圈或重跑已停止的第七輪。

### 第 110 筆請求定位與下批帳本欄位

沿同一隔離庫的唯讀 Saver／P3 response ID 對帳：第 109 筆已結算 A 請求對上 canonical AIMessage 的 `read_work_understanding` 呼叫，後接成功 ToolMessage；第 108 筆已結算 A 請求沒有對上 canonical AIMessage，且使用 1,831 input／2,275 output tokens，符合摘要呼叫特徵。第 110 筆在該工具結果之後失敗。按當時摘要安全邊界及 request 門檻推論，它**很可能**是下一次摘要請求，但原帳本未保存請求工具數量或明確種類，也未保存 `incomplete_details.reason`；故仍不能確認第 110 筆種類與失敗原因，更不能由此直接改 16K／8,192 設定。

為讓未來批次不再靠 Saver 間接猜測，僅在 **test-only P3 spend ledger** 的每筆准入紀錄加入 `declared_tool_count`：經既有 wire 檢查後，無 `tools` 記 0，有工具只記數量；不保存名稱、定義、參數、對話或新狀態，也不更動費用保留、拒絕、重試或 production request。先用 0／1 工具且服務端 `incomplete` 的持久化反例取得紅燈，再以一行紀錄修正取得該測試檔 **45 passed／0 failed**，沒有外送模型請求。此欄位僅輔助區分未來的摘要與工具主請求，**不是精確 request-kind 權威**；第三批舊帳本無法回填，仍維持 stopped／未知預留。下一個產品決策仍應依新的具體請求／回覆證據，而非把重讀、摘要頻率或未使用 writer 單獨當成根因。

### 針對長工具迴圈的官方做法複核（不改設定）

查閱 2026-09-23：[OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction)以實際渲染的 request tokens 觸發，並將延續狀態帶到後續請求；[Anthropic keep-recent-turns](https://platform.claude.com/docs/en/build-with-claude/compaction-keep-recent-turns)明示最近訊息逐字保留，切點不能拆開工具呼叫及結果；[Anthropic threshold compaction](https://platform.claude.com/docs/en/build-with-claude/compaction-threshold)明示壓縮本身有額外推理／計費，門檻由工作負載配置。這些是不同服務的公開做法，**共同原則**是依有效上下文量測、保留近期工作及完整工具配對、把額外壓縮成本算入驗收；它們沒有共同指定 Caliburn 應用 16K、32K 或改用某個服務端 API。

[Anthropic tool design](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)建議工具回覆只帶下一步判斷所需的高訊號資訊；[OpenAI deployment checklist](https://developers.openai.com/api/docs/guides/deployment-checklist)建議用代表性任務比較品質、延遲與每次成功成本，不能只看請求 200 或單次 token。這提供診斷順序，**不證明**本案的工具回覆過大、Prompt 不佳或模型選錯。OpenRouter 的[message-transforms 插件](https://openrouter.ai/docs/guides/features/message-transforms)會從 prompt 中間移除／截短訊息，與本案不可丟未處理訪談及引用的規則不同，不作直接替代；OpenAI 原生 compaction 在目前 OpenRouter 目標路徑仍未驗證，不因 OpenAI 官方支援而宣稱已可切換。

下個最低成本、高區辨力的驗收問題是：**在上下文尚短、已有足夠已知工作且使用者明確要求先寫暫定 JD 時，同一 GPT-6／正式工具接線是否會選 JD writer？**正式組裝的兩個零付費定向測試已確認 `jd_create_task`／`jd_insert_item` 等工具在 A graph 中、A 的 compaction middleware 仍用原 profile（**2 passed**），但只證明可用，不證明模型自然選用。若短上下文仍不寫，先查 model-facing 工具／Skill／指令和實際 tool result；若可寫，才用長上下文的 request view、摘要頻率及 reader 結果比較。任何調門檻、改 Prompt 或加防重讀規則都須有該對照證據，不能由本批 20 次摘要與 0 writer 直接推定。

### 新文件、單回合 GPT-6 寫入診斷（非 C-W 自然 trial）

另以全新隔離目標 `jd-ui-gate-64548b4215564bec809f29809260301a`、正式新 App／PostgreSQL／Saver／Store、同一 OpenRouter GPT-6 Luna Responses／OpenAI-only 接線執行一次合成倉庫收發工作輸入。員工在該回合描述收貨、短少處理、出貨與責任邊界，明確要求先寫有根據的暫定 JD，並保留盤點頻率與 KPI 未知。這不是 C-W 的自然扮演，也**沒有預先發布 B1/B2 工作理解**；只回答「資料足夠且明確要求寫時，正式 A 是否真的能選寫入工具」。依現行[JD 品質規則](../2026-09-10-jd-product-quality-acceptance.md#3-單一顧問的寫作修訂與收尾規則)，不要求每輪寫 JD，背景 Memory 尚未發布也不是對已知部分一律禁止寫稿的硬門檻。Memory→JD 的完整按需回查／品質另驗，不能由本次替代。

測試重用既有 P3 test-only 逐筆支出閘門，獨立 ledger 限 **40 筆實際 provider 外送／US$0.75**、零 hidden retry／fallback；沒有修改 production 或使用正式員工資料。Windows 配置首次初始化在 `initialization_pending` 留下 candidate，經唯讀確認 phase 後以既有 `resume=True` 在隔離目標完成初始化；沒有刪除舊資料或重建已存在的測試庫。模型 40 筆均完成並結算，合計 **US$0.107812515**、未知保留 0；其中 22 筆帶正式 20 個工具，18 筆沒有宣告工具。後者可協助辨識摘要／收尾路徑，**不能單靠工具數將每筆精確定性**。最後幾筆帶工具的請求顯示約 53k 實際 input tokens，已高於 profile 的 16k *approximate* trigger；這是計數與 wire 的觀察差異，不足以斷言唯一根因。

隔離資料庫唯讀查回 **5 筆 JD 修改均 committed**，目前 JD revision 6：已寫收貨核對、短少／破損隔離與採購通知的 1 項 task、1 項 outcome、1 項 requirement；索賠權責沒有錯放給員工。Saver 工具序列含 `jd_set_text`／`jd_create_task`／`jd_insert_item`，證明「GPT-6 完全不會使用 JD writer」不成立。出貨部分尚未寫入；40 筆額度用盡時本輪 `run_status=failed`、`input_state=saved`、5 筆 effects 已提交、無 final assistant。第 41 筆未外送；公開 run state 未提供精確內部 exception，故只將**外送上限耗盡與未能收尾**列為直接觀察，不把它寫成模型或 compaction 的唯一故障。App／Saver 已正常關閉，沒有自動重送或補造回答。

這次暴露的真正下一個診斷是：單回合 JD 撰寫為何消耗 22 筆帶工具請求與 18 筆無工具請求、實際 request 如何從約 9k 增至約 53k input tokens，以及哪些讀取是成功保存後取得新 ref 所必需。先核對既有 compaction counter、正式 request view 與實際 usage，再決定是否需要最小設定／接線修正；不能因這次 40 筆上限過低就盲目加 cap，也不能把尚未實測的 Memory→JD、完整 JD、自然 C-W 或 Browser 宣告通過。
