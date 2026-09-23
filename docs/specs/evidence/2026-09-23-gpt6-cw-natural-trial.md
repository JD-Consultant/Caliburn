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

### 同一隔離回合的零付費 checkpoint 診斷（不改產品）

唯讀檢查該文件的子 graph Saver：45 則 canonical messages、17 個不同的已發布 A `continuation_compaction` v2；發布後的 request-only view 各為 12 則，內容字元數由約 43k 漲到約 113k。末次 view 仍留有三筆約 31k 字元的 `jd_read` 結果；現行 `keep_messages=8` 的安全切點，在末次狀態留下 8 則、其中工具內容約 75k 字元。只作離線比較時，保留 4 則的安全切點約 38k 字元、保留 2 則約 33k 字元；**這不是批准修改正式 8 則規則**，也沒有證明 2／4 則已足以維持來源／JD ref／reasoning 延續品質。原始員工 HumanMessage 仍由 v2 獨立逐字保護，canonical 對話與資料庫沒有被此檢查改寫。

10 次 `jd_read current` 中，前三次隨成功保存的 revision 前進；任務建立後，39 筆記錄的 current 投影依既有 `page_bytes=32768` 分成第一頁約 31k 字元及第二頁約 5k 字元，模型正確沿 cursor 續頁。成功保存後若繼續編輯，現行主顧問明文要求再讀最新版 refs，這些重讀不能直接標成多餘。後段在同一 revision 上有再次全讀、重讀 Skill／evidence 的實際序列，需與 compaction 對照，不以模型動機猜根因。6 筆 JD writer call 中 5 筆 `committed`、1 筆 `invalid_input`；`jd_create_task` 已在同一呼叫帶入一筆 outcome 與一筆 requirement，不能誤稱模型完全沒用既有複合能力。

鎖定 middleware 用 LangChain `count_tokens_approximately`，其 [官方參考](https://reference.langchain.com/python/langchain-core/messages/utils/count_tokens_approximately)明說預設 4 字元／token、只是估算，並計入宣告的工具 schema；[OpenAI token counting](https://developers.openai.com/api/docs/guides/token-counting)則說工具與訊息結構都佔 context，精確計數需對實際 OpenAI request。後者是 OpenAI API 能力，**未證明**可直接套目前 OpenRouter credential／route。[Anthropic keep-recent compaction](https://platform.claude.com/docs/en/build-with-claude/compaction-keep-recent-turns)指出逐字保留近期越多，可釋放的空間越少，且切點不可拆工具呼叫／結果；它沒有指定本產品應保留幾則。這些公開原則加上本地 trace 支持「近期大型 JD tool results 造成反覆摘要」的局部診斷；仍不把模型未收尾的所有原因歸給單一 token counter。

**需先對齊的正式規則：**[既有 compaction 設計](../2026-09-16-openrouter-continuation-compaction-design.md) §8／§9 要求至少保留最近 8 則原樣；不能只為減少 17 次摘要便擅自降成 2／4。最小候選先限既有 A middleware／JD read 契約：比較在保持員工當輪原話、最新未完成工具 wave、正確 JD ref 與來源回查的前提下，是否可讓「已完成且已失效的舊 JD 讀取結果」更早離開 model request；若需改動 8 則硬規則，先請 Owner 裁決。另一候選是維持 8 則、改觸發／節流策略，但須以相同保存與實際 provider usage 證明不會只把大 request 與成本推高。此處只記診斷及候選；**沒有 production diff、沒有額外付費請求，也沒有重跑已停止的 C-W trial**。

再用末次 checkpoint、相同 20 個正式工具與靜態顧問 guidance，對既有安全切點作**零付費估算**：保留 8／6／4／2 則時，`count_tokens_approximately` 分別約 **31.7k／30.7k／22.3k／21.2k**。這些值未加當次 App notices／Skills 注入，也非供應商精確計數；但連 2 則候選都高於 16k trigger，足以否定「只把 8 改小就能使本回合摘要後低於觸發值」這個簡單修法。正式 8 則規則維持不變。下一個可證偽重點是：既有 middleware 能否在保存安全邊界下避免**無法把有效 request 壓到門檻以下時，每完成一個工具 wave 就再花一次摘要呼叫**；同時不得以跳過摘要讓真 provider request／費用無界增長。可調節的 trigger、最小收益判斷或縮小 JD read payload 均僅為候選，先離線比較再定方案。

### 首批 C-W 的 Memory→JD 基礎唯讀核對（不改產品）

同日另以 inspection-only 正式新 App 開啟**首批已停止**的隔離文件；先核對原 `serve.finished.json` 已記 App／Saver 關閉且支出帳本 stopped，再讀 PostgreSQL publication、Store 與 Saver，未啟用聊天／背景、未恢復第七輪、未送模型或改 JD。停機後目前 head 為 revision 3：三份案例、三份工作理解、各三條案例→原話與工作理解→案例關聯；兩份 guide 可導覽這三項工作。

將目前 Memory 正文與已保存的前六次員工原話逐項比較：收貨包含到貨單／品號／數量／外箱與條件式批號核對、短少標記及交採購、入庫與追溯要求；出貨包含核准揀貨單、包裝／交運、缺件回報與不自行換料號；庫存查核包含實物／記錄比對、複點、查出入庫及交主管決定調帳。盤點頻率仍寫作「印象中、未查證」，差異後續責任與試算表用途維持未知。這是**局部內容對照**，支持三個主題已有可供暫定 JD 使用的材料；沒有檢驗每條來源引用的完整語意支持，也不宣稱六章 JD 或全工作範圍已完整。

第七次員工原話明確要求「先把目前已說清楚的工作整理成一版職務說明書，不確定的先標明」，並新增 A／B 兩案差異。從該輪最新 consultant 子 checkpoint 可獨立確認 `jd_read`、`read_work_understanding`、`read_case` 已呼叫；其中成功的工作理解正文讀取為**收貨**一項。其餘兩項已在停機後 Memory head 中，但此 checkpoint **不能證明**顧問在該輪逐項讀完。兩案差異是第七輪才說出的原話，不要求已在此前發布的 B1／B2 中。結合既有帳本的第七輪 timeout／0 writer，結論限於：**Memory 並非完全空白；至少收貨主題已有局部可寫依據且顧問確實讀到，惟第七輪在寫入前停止。**不能由此推定顧問「拒絕寫」、三項都已完整讀取，或唯一根因是 Memory／compaction／Prompt。自然 Memory→JD、完整暫定稿與最後回答仍 OPEN；不引入每輪必寫 JD 的規則。

### JD 撰寫回合的 context 膨脹與反覆摘要：分項唯讀診斷

2026-09-23 仍用已停止的 `jd-ui-gate-64548b4215564bec809f29809260301a` 子 graph checkpoint，僅離線重建 request-only view 與計數；不改 canonical、資料庫、工具契約或產品碼，也不送模型。所有 token 數是鎖定 LangChain `count_tokens_approximately` 的**估算**，包含 20 個正式工具與靜態顧問 guidance，但未重現每次動態 JD／Memory／Working State notices，也不是 OpenRouter 供應商精確分項計費。既有帳本顯示末段真 provider 主請求約 53k input tokens，與估算口徑不可相減作精確歸因。

| 已發布摘要次序 | 摘要前估算 | 摘要後估算 | 本次少送的估算 | 摘要後是否仍達 16k trigger |
|---|---:|---:|---:|---|
| 1 | 24,183 | 23,347 | 836 | 是 |
| 9 | 26,970 | 25,776 | 1,194 | 是 |
| 17 | 43,211 | 40,837 | 2,374 | 是 |

全部 **17／17** 次發布後的估算 request 仍高於 16k，單次節省範圍約 **440–8,475**、中位約 **1,293 tokens**。現碼只檢查「本次 view 達 16k、且有向前的安全切點」便再呼叫摘要模型；沒有摘要後低於 trigger 或最小淨收益條件。故在已保存的逐 wave 進展中，每次新 wave 都可能再花一次摘要呼叫。A profile 的 `hard_input_tokens` 目前也是 `None`；**不能**只加「少摘要」而沒有經驗證的安全容量／失敗路徑，否則只是把成本問題移成過長 request。這足以解釋**為何反覆觸發**，不單獨證明顧問未收尾的語意根因。

| 摘要後 view 組成（估算） | 第 1 次 | 第 9 次 | 第 17 次 |
|---|---:|---:|---:|
| 完整 request（不含動態 notices） | 23,347 | 25,776 | 40,837 |
| 20 個工具 schema | 11,541 | 11,541 | 11,541 |
| 靜態 guidance | 935 | 935 | 935 |
| `jd_read` ToolMessage | 7,799 | 9,129 | 23,555 |
| 延續摘要文字連同訊息開銷 | 47 | 223 | 308 |

分項為逐訊息粗估，非完整計數的嚴格可加拆帳。末段的主要來源是**近期 JD 讀取結果和固定工具定義，不是摘要本身或本輪員工原話**。最大工具 schema 粗估依序含 `jd_insert_item` 約 2,163、`jd_revise_work` 約 1,227、`update_interview_working_state` 約 1,220；這是現有 20 工具的描述／輸入合計，不等於可安全刪除其中任一工具。

對第 10 次 `jd_read` 的第一頁（31,329 字元、34 筆 records）只按 JSON 欄名統計字串長度，不輸出值：`section_ref` 約 11,588、`container_ref` 約 5,957、`field_ref` 約 4,556、`item_ref` 約 3,306、`owner_ref` 約 1,469 字元；上述五種重複發配的定位引用合計約 **26.9k 字元／86%**。文字 `value` 合計僅 320 字元。第一頁含 6 個 section、14 個 container、11 個 field、3 個 item。單是 `section_ref` 在 34 筆 records 中出現 34 次，實際僅 **6 個不同值**；相同值的重複字元約 9.6k。`item_ref` 也在 9 次出現中僅有 3 個不同值。這證實此筆 payload 主要是**安全定位用 signed refs 的重複投影**，不是 JD 正文太長；但只去除完全重複的字串仍不能消除每個不同 field／container 都要可寫定位的成本。縮頁或少讀正文不能直接當作同等修法。`jd_read` current／續頁、成功保存後取新版 ref 與 Runtime 驗證仍是既有業務契約，不能無證據刪除。

2026-09-23 官方交叉核對：[OpenAI token counting](https://developers.openai.com/api/docs/guides/token-counting)將工具 schema 計入 context；[OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)按實際 request token 觸發但不給本產品 16k 規定；[Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)區分保留高訊號工作狀態與清理舊工具結果；[Anthropic keep-recent-turns](https://platform.claude.com/docs/en/build-with-claude/compaction-keep-recent-turns)明示保留近期越多，可壓縮空間越少且工具配對不可切開；[Anthropic context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing)的 `clear_at_least` 是清理舊工具結果時避免低收益／cache 失效的產品化例子；[LangChain short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory)提供摘要／裁剪的不同接點。各家**沒有**共同要求固定 16k、8 則、每有安全 wave 必重摘要，亦未證明 OpenRouter 目前支援 OpenAI／Claude 的原生 compaction 或 tool-search。[OpenRouter GPT-6 Luna 型錄](https://openrouter.ai/openai/gpt-6-luna/)標稱 1,050,000-token context；本次約 53k 的已觀察主請求遠低於型錄上限，**尚無服務端 context overflow 證據**。這是「超過本產品過早的 16k 摘要起點」，不是「已超過模型硬窗口」；也不代表 53k 的品質、延遲及成本已可接受。OpenAI [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)與 Anthropic context editing 均提醒改寫上下文可能使快取前綴失配；本產品 OpenRouter 實際 cache 收益仍需獨立量測。

**後續最小候選／停止線：**先在同一現有 `jd_read` owner 做 test-only 模型可見投影，評估對**重複 signed refs** 的減量，同時證明最新版、跨文件／歷史拒絕、item／container 類型、來源回查、cursor 與 writer round-trip 都不變。若要改為短代號，Runtime 必須保持唯一解析及 scope／revision 檢查，模型不能自行生成授權引用；不先立新資料表或通用 registry。另於既有 compaction middleware 做零付費 pre／post 收益與安全餘額對照，評估「低收益時不再付費重摘要、但硬安全上限仍有受控出口」是否可行。**至少保留最近八則**是目前正式設計，任何清理近期工具結果、調高 16k trigger 或改可用工具集合都先提出此處的量測、失去的 context／cache／費用影響及產品取捨，不以本次研究直接施工。不得把原始員工輸入、未完成工具 wave、Memory／JD authority 或來源證據當可任意刪的資料；不因官方有原生 API 就切換 provider。

### 重複 JD 引用的零付費候選對照（非正式工具格式）

同一批 17 個已發布摘要的 request-only view，沿相同工具、靜態 guidance、既有近八則與員工原話，僅在離線複本中把 `jd_read` records 的 `section_ref`／`container_ref`／`field_ref`／`item_ref`／`owner_ref` 字串改成**每頁整數索引＋完整原值表**。每頁都做逆轉換並斷言可還原原 JSON；沒有更動 Saver、App、ToolMessage artifact 或任何正式 tool schema。這只測**一種無損資料表示候選的減量**，不是所有編碼方式的最小 token 下界；也未證明模型能正確查表、原有 `jd_read` 私有 artifact／digest 校驗可接受新格式，或 writer 在實際回合能安全使用索引。後兩點若要正式採用，仍需在現有 JD owner 做窄接線與真實回歸，不能把索引冒充已發配的可寫 ref。

| 摘要次序 | 現有估算 | 無損表格投影估算 | 節省估算 | 全部 `jd_read` 內容設成空字串的純數學下界 |
|---|---:|---:|---:|---:|
| 1 | 23,347 | 20,750 | 2,597 | 15,574 |
| 9 | 25,776 | 21,979 | 3,797 | 16,673 |
| 17 | 40,837 | 30,204 | 10,633 | 17,321 |

**17／17** 個摘要後 request 在無損表格投影下仍高於 16K；節省範圍約 2.6K–10.6K。末次三筆近期 `jd_read current` 都是各約 7.8K token 的第一頁、各 34 records，且分別屬於**三個不同 JD revision**：前兩頁對最新可寫 ref 已過期，但不能只看版號便斷言其歷程資訊全部無用。末欄把所有 `jd_read` 回覆內容直接清空僅是**不合法、不可採用**的下界測量；末次仍約 17.3K，尚未包含動態 notices。由此可證：**只去重 JD ref，或只把 JD read 變短，並不足以保證壓縮後低於現行 16K trigger**；同時也不表示應刪原始工具結果、縮短近八則或把 trigger 直接提高到某個未驗值。

現在的可審問題應收斂為同一件事：在保留 canonical、未處理員工原話、工具配對、最新可寫 ref 與按需回查的前提下，現行 A middleware 的 **16K 觸發點、可壓縮部分的實際收益、以及過長 request 的安全上限**如何共同設定，使它不對不可再縮的固定／近期部分每 wave 付費重摘要，也不讓 provider request 無界增長。先用離線 trace 驗證候選，再用單一有界真模型／JD writer gate 驗證效果與費用；OpenAI 原生 compaction／tool-search 與 Anthropic 原生 tool-result clearing 均不是目前 OpenRouter 路徑已證可直接切換的產品能力。

再以同一 17 個真 Saver 摘要發布點測一個**只用於證偽的理想下界**：保持原安全切點、當輪員工原話、近期尾段、正式 20 工具及靜態 guidance，唯獨把每次摘要正文暫時換成一個字元；以既有 `build_request_view` 重建並計數。這不是可用的摘要內容，也不修改 checkpoint。結果 **17／17 仍高於 16K**，理想下界約 **23.3K–40.5K**；第 1／9／17 次分別約 23,314／25,567／40,543。當時實際摘要的離線節省 17 筆中 **10 筆不足 2K、13 筆不足 4K**。因此不能以「加強摘要 prompt，讓 summary 再短一點」作為這個逐 wave 觸發問題的主要修法；理想化零資訊摘要都跨不過 trigger。這只證明目前**A 的此一長 JD 寫作 trace**，不是 B1／B2 的容量結論，也不等於正式品質、費用或 provider hard limit 已驗收。

### 工具定義按需載入之相容性核對（非正式接線）

2026-09-23 核對鎖定的 LangChain 1.4.0／`langchain-openai` 1.6.2 原碼、正式 A／B1／B2 組裝及 [LangChain Provider Tool Search](https://docs.langchain.com/oss/python/langchain/middleware/built-in)、[OpenAI Tool Search](https://developers.openai.com/api/docs/guides/tools-tool-search)、[OpenRouter Tool Search](https://openrouter.ai/docs/guides/features/server-tools/tool-search) 官方說明。LangChain 有現成 `ProviderToolSearchMiddleware`，可對指定工具標 `defer_loading` 並加 `tool_search`；OpenRouter Responses 官方也接受該 alias，標示 beta。這是工具**參數 schema 延後進模型 context**，不是不用在每次 HTTP request 向服務端宣告工具；OpenAI 逐一 deferred function 仍先露出名稱／描述。OpenRouter 自己建議 3–5 個常用工具先 eager、適合約 >10K schema tokens／>10 tools，且說小型工具集可能因搜尋往返更貴。

沿現行 `count_tokens_approximately([], tools=...)` 離線估算：A 20 個工具約 **11,541**；B1 10 個約 **1,263**；B2 12 個約 **1,484**。因此 A 有可衡量的延遲載入動機，但 B1／B2 目前 schema 很小，不能因共用 compaction 就自動全 defer。三角色的摘要模型請求本來不帶業務工具，不能再靠 tool search 降那部分。正式 compaction counter 目前估算全套 BaseTool schema，尚未有 deferred 的實際 provider 用量對照，不能先在計數中扣掉工具或宣稱 64K／128K 已反映新機制。

服務端合成 probe 使用單一 OpenRouter key、GPT-6 Luna Responses、OpenAI-only／無 fallback／`store=false`／高推理、無副作用函式與一個 deferred tool；沒有正式文件、JD 或 Memory。第一個沙盒嘗試為 `transport_unknown`，帳本保守保留 US$0.268644，沒有重送；兩個獨立的可連線嘗試各只送一筆 POST，均 HTTP 200、路由 metadata 顯示 OpenAI／`openai/gpt-6-luna-20260922`，觀察費用各 **US$0.0000866**、**US$0.0000859**。第二筆的安全輸出類型記錄為 `openrouter:tool_search`、`function_call`，證明此路徑在這次設定下實際搜尋並產生函式呼叫。既有 P3 test-only 閘門只允許 `service_tier=default`／空，而合成 probe 的回覆為 `auto`，因此兩筆帳本均依既有規則停於 `provider_service_tier_mismatch` 並各保留 US$0.268644 未知額度；**不能稱帳本結算通過，也不能把觀察費用當成承諾上界**。三個獨立帳本不覆寫、不重送；總保守保留 US$0.805932，另見兩筆 HTTP 回覆觀察費用合計 US$0.0001725。

目前不能把 LangChain middleware 直接插入正式 A／B1／B2：`langchain-openai` 的 Responses 回應轉換及下次輸入重播只列 `tool_search_call`／`tool_search_output`，不明列 OpenRouter 這次實測的 `openrouter:tool_search`。零付費 MockTransport 以**已實測的 item type、合成內容**送入現行 ChatOpenAI：SDK 仍能解析伴隨的 `function_call`，但 `AIMessage` 僅留下 `function_call`；真 `create_agent`／InMemorySaver 工具往返的下一次 outbound input 類型只有 `message`、`function_call`、`function_call_output`，沒有 `openrouter:tool_search`。這證明目前 client **沒有忠實保留該類 item**；合成 payload 不能進一步證明 OpenRouter 在缺少它時一定拒絕下一請求或工具搜尋完全失效。OpenRouter 官方也明示 deferred search 與 `tool_choice=none` 衝突；A 既有第 64 次無工具收尾會設 `none`，須維持該安全語意並先做相容性反例。沒有因此修改 LangChain、A 收尾或正式工具集，也不因 server 單次 200 就聲稱完整 App PASS。下一個最小 gate 是只在隔離 fixture 驗真回覆形狀下的 SDK／Saver 重播、A no-tool 收尾、B1／B2 terminal，以及有／無 deferral 的實際 request token／延遲比較；若薄接線無法保持正確語意，才拿具體失敗與 direct OpenAI Responses 的 credential／路由取捨給 Owner 裁決，不新建一套工具 registry／搜索 Agent。

後續零付費 production-model-factory／真 `create_agent`／MockTransport 契約補測：鎖定的 LangChain middleware 辨識現行 GPT-6 Responses 模型為 `openai`，正式 factory 所組出的實際 outbound request 帶 `tool_search` 與所選函式的 `defer_loading=true`，仍保留 OpenAI-only route；定向測試通過。這只證明**請求側可以組裝**，沒有把前述回應 item 遺失或 A 無工具收尾衝突改判通過；也不代表 B1／B2 的小工具集有延遲載入收益。

### 64K／128K 設定的 C-W 自然試跑：第 11 輪 C 錯誤回饋接合首敗

Owner 決定先不接 tool search、不用 Browser，優先以正式新 App API 驗證自然長訪談。新的隔離目標為 `jd-ui-gate-e6919b0b69c943f58cb40459cc864330`，dataset `7bea90dd-89d7-4f95-b24c-38358d062548`、文件 `89ce4f58-2a5e-441c-b245-8ab4d5b1b0ee`；A 64K、B1／B2 128K 觸發值，沿用現行 App-side compaction、正式 20 工具、GPT-6 Luna Responses／OpenAI-only 與 P3 每批 12 員工回合／180 筆實際外送／US$1 上限。前 10 次自然員工輸入均有完成回覆；真模型與正式新 App 已 committed **5 筆 JD 修改**。這證明本批可以訪談並寫入部分 JD，不等於完整專業 JD 已完成；同批真 Browser 沒有執行。

第 11 次員工原話明確更正先前「印象中每月全部盤點」：實際每週循環盤 A 類料、每季全庫盤點。當輪原話已保存，A 呼叫 C 即時修補；C 核心對模型提交的 V4A 差異回 `invalid_edit`，指出舊文片段不符合目前案例，**沒有發布或部分套用 Memory**。這是可回饋模型的正常錯誤，不應讓整輪卡住。然而 App `memory_repair_records._outcome` 原先只允許 `applied`／`stale`／`no_memory` 帶 `head`＋`guide`；C 核心依現行分層設計也在 `invalid_edit`／`scope_too_broad` 帶目前 head 與導覽，於是 App 拋 `invalid_repair_message`。正式 run 停在 `recovery_required`、無 assistant final；一次既有 recover API 回 `409 recovery_required`，未送新的模型請求。這是**C 核心與 App 錯誤結果契約不一致**，不是原話遺失、已證 provider 失敗或新的 Memory 架構需求。

本批帳本 **104 筆實際模型請求均 settled、US$0.194038960、在途 0、員工輸入 11 次**。依安全停止入口停止試驗程序；`serve.finished.json` 記錄 `app_closed=false`、`saver_connection_closed=false`，故只稱程序已退出、隔離資料保留，**不冒稱 App／Saver 優雅關閉**。舊第 11 輪不重新 POST、不自行清理已保存的 C pending 狀態；下次正式自然驗收用新凍結版本與新隔離目標，不繞過 P3 preflight。

依[分層 C 設計](../2026-09-16-layered-case-and-work-understanding-memory-alignment.md#6-c-即時修補工具)與核心 `_feedback` 原碼，只在現有 App outcome decoder 允許 format v2 的上述兩種未套用狀態攜帶**成對、受既有 scope／revision／長度驗證**的 head／guide；未改 C 核心、模型 Prompt、重試上限、publication、JD、背景 B1／B2 或 provider。測試先見兩個狀態的失敗反例，修後 ToolMessage／Saver 序列化往返均通過；另以真 Agent graph、錯誤案例 diff 驗證回饋正常進模型、最終回答可生成，publication 原版不變。相鄰 C 測試 **154 passed**；完整新 App 離線測試在可用 Windows 暫存環境為 **3,180 passed／323 skipped／0 failed**。受限執行環境先出現 93 個 pytest 暫存目錄 `WinError 5` setup errors；同一個控制測試在可存取環境通過，故不歸因於產品修改。**修後真模型、原 pending run 的精確恢復、完整 JD 品質與 Browser 仍未由這些離線測試驗證。**

### 修後新隔離試跑：C 回饋可達模型，但第 11 輪未完成

2026-09-23 以修後 commit `2e50223f35505fdfc5eef2ab04a332f9654b9f7d`、新隔離目標 `jd-ui-gate-562d202db2ff49bfa996e0a0c521f55d`、dataset `d2be2c19-ce1f-420a-bd88-16025c309910`、文件 `a8076092-0e5a-48a7-a460-9b85e15d32a9`，重跑同一已曝光 C-W 員工卡。使用正式新 App API、GPT-6 Luna Responses、A 64K／B1/B2 128K、既有 App-side compaction 與 20 個 A tools；沒有啟用 Browser 或尚未驗成的 tool search。前 10 次自然員工輸入均 `completed`，模型在資料漸足時自行寫入 JD；本批觀察到 9 筆 writer 執行／保存，並非每輪強迫使用 JD 工具。第 11 次明確更正 W05，員工原話有保存，並另說 W09 A/B 結果仍未知。

本批第 11 輪的真 Saver 記錄顯示：A 已讀目前案例、直接相關工作理解與來源，兩次呼叫 `repair_memory` 的 V4A `case_diff` 都把案例正文中**同一段落內的兩句**當成分開兩行，其中一行被錯放為獨立 unchanged context。實際 `read_case` 回傳的是單一完整段落；C 的 SDK patch 因 `Invalid Context 0` 正確回 `invalid_edit`，未部分寫入。第一次 ToolMessage 明示要重讀並修正，模型雖重讀目前內容，第二次仍提交相同錯位 diff。App 這次已把兩次 `invalid_edit` 正常交回模型，**沒有再發生先前的 `invalid_repair_message`**。既有兩次失敗上限之後，第三、四次修補請求都收到 `repair_limit`；其中第三次改成整段替換，但上限已生效，不能聲稱該候選可成功。這是 model-facing V4A 精確行匹配與模型使用上的實測缺口，不是已證 Memory 版本競爭、來源資料遺失或 C 核心錯誤。

模型在 `repair_limit` 後仍繼續多次讀 JD／案例／工作理解／原話及寫作 Skill，沒有本輪 JD mutation 或 final。該輪 Saver 自最後一則 HumanMessage 起有 4 次 `repair_memory`、13 次 `jd_read`、11 次 `read_evidence`、7 次 `read_file`、4 次 `read_case`、4 次 `read_work_understanding`、1 次背景通知。正式 `q019_document_memory_head` 停在 revision **2**，兩筆成功 publication receipt 均為先前 `consolidation`，沒有本輪 C repair publication。第 11 輪終態 `run_status=failed`、`input_state=saved`、`jd_effects.state=settled` 且本輪 effects 0、無 assistant final；**不得標為 C 更正或完整 JD 通過**。第 12 次員工輸入未外送。

P3 每批既定上限 **180 筆實際模型外送／US$1.00**：本批 180 筆均結算，共 **US$0.575568895**、未知保留 0、在途 0；第 181 筆未外送。關停時 `serve.finished.json` 記 `reason=requested`、`app_closed=true`、`saver_connection_closed=true`。關閉輸出另有 `background_workflow_failed`，目前僅能確認新背景 publication 未出現，不能從單一 log 推定具體根因。隔離資料與完整帳本保留，不重送失敗回合、不為這次結果擅自擴大額度。

關停後用**鎖定的 OpenAI Agents SDK `apply_diff`**、本批 Saver 已讀正文及四次原始 `repair_memory` 參數作零付費純記憶體比對：前兩次案例與理解 diff 均不匹配；第三、四次整段 diff 對各自原文都能套用、替換舊頻率且不留「每月全盤」。這只證明 V4A text patch 部分可用，不會越過正式 `repair_limit`，也沒有模擬整個 C 的來源／引用／CAS 驗證；不得倒推那兩次完整 publication 必然成功。[OpenAI 官方 Apply Patch 指南](https://developers.openai.com/api/docs/guides/tools-apply-patch)（查閱 2026-09-23）建議在 patch conflict 時回報可理解錯誤、讓模型重新讀取並調整 diff；本案已採相同錯誤回饋原則，但真 Luna 第二次仍重送相同錯位 diff。這是公開方法與本案實測的區分，不把 OpenAI 原生 `apply_patch` tool 誤稱為本 App 正式工具。

下一個低成本 gate 是沿既有 C／Tool owner，在零付費真形狀測試重現「正文單段、模型產生分行 context」與第一次 `invalid_edit` 後重送相同 diff 的情境；先核對現有工具描述、SDK `apply_diff`、錯誤回饋與 retry guard，再提出最小 model-facing 修正及其受影響測試。不得先加重試次數、替模型自動改寫 diff、新建 patch engine 或重開 Memory 架構。即使 C 候選修正，還需另驗 A 在更正失敗後能誠實收尾、完成 JD 及最終品質；Browser 仍依 Owner 決定暫後。

### C V4A 完整行說明的窄修正與離線驗證

2026-09-23 再以停止的合成 trial Saver 唯讀核對：第一次 `repair_memory` 前 `read_case` ToolMessage 的 `content` 為單一 137 字元段落、無換行；第二次修補前重讀同一段落。前兩次候選 diff 各為四行，卻把段內句子當成獨立的未變／刪除行。這與上面的原始試跑結論相同，**不是新證據證明 compaction 丟失該段或 provider 未收到工具結果**。鎖定的 `caliburn_memory.patch.PATCH_GUIDANCE` 明文要求完整原文行，但正式 `repair_memory` 的模型可見參數說明原先只稱「V4A diff」；故只補 `case_diff` 與理解 `diff` 的完整原文行、不得拆分段內句子要求。這是本產品 SDK matcher 的契約提示，不宣稱 OpenAI／Anthropic 有本 App 的特定 schema；[OpenAI Apply Patch 公開指南](https://developers.openai.com/api/docs/guides/tools-apply-patch)（查閱 2026-09-23）只支持 V4A diff、失敗回報及由模型調整候選的一般做法。

零付費檢查確認 `build_repair_tool()` 經鎖定 LangChain strict tool serializer 後仍為 `repair_memory`、root `required` 5／5，兩處新說明均實際出現在參數 schema；工具名稱、參數結構、C 保存規則、錯誤回饋與兩次失敗上限不變。相鄰離線測試 **40 passed**；新 App 全套第一次在受限 Windows 暫存目錄出現 96 個 `WinError 5` setup errors（3,087 passed／323 skipped），改在可存取的隔離暫存環境執行相同全套後為 **3,183 passed／323 skipped／0 failed**。本次沒有付費請求、沒有恢復或改寫舊 trial，也沒有驗證 Luna 會因描述而產生正確 diff；自然 C、更正後 A 收尾、B1、JD Q11 及完整品質驗收依然 OPEN。

### 同一批試跑的關停後唯讀盤點：背景中斷與 JD 半成品

2026-09-23 使用同一隔離 PostgreSQL 的唯讀連線核對 Saver、背景 admission、JD current 與 P3 帳本；沒有恢復背景工作、重送失敗回合、送模型或修改產品。背景 dispatcher 的 `background_workflow_failed` 只表示 Future 以例外結束，log 本身未保存內層原因。Saver 的 B1 agent、B1 root 與外層 workflow `__error__` 均為 `OpenAIConnectionError('Connection error.')`；B1 agent 在三次已結算的 `background-case-maintainer` 請求及三次成功 `read_case` 後，下一個 model 節點沒有產生已結算的 B1 請求。外層 checkpoint 仍待 `run_b1`，admission 為 `running`／無 error code，沒有新 publication。鎖定 OpenAI SDK 會把底層一般例外（包括測試支出閘門可能拋出的拒絕）包成 `APIConnectionError`；Saver 只留下外層類別，**無法從此紀錄判定是 OpenRouter 連線、本機傳輸或 P3 閘門的哪一種內層原因**。事故時帳本尚未達 180 筆總上限，最終帳本為 active／180 已結算／無未知保留；不能因最後達上限，就反推較早的 B1 錯誤是該上限造成。背景失敗是本次自然 trial 的 OPEN，不是已證的 Memory 邏輯或發布錯誤。若要再定位，先沿既有 test-only 閘門與背景記錄邊界取得不含原話／密鑰的內層錯誤碼；不以猜測修改正式 dispatcher／Memory。

同一文件目前 `jd_head.revision_number=10`，9 筆 JD operation 已保存。唯讀 current 表顯示：有職務名稱、目的、4 個 Duty、3 個 Task、6 個成果／要求 detail、1 個工作條件；K／S 與 task-capability link 均為 0。18 個 JD source link 均為 conversation 類型；**僅確認 link 已保存，尚未驗證每筆語意是否支持文字或 Browser 導覽是否正確**。內容已有收貨核對、到貨差異／重複入帳的區分及年度封存責任，但出貨 Duty 尚無 Task；「年度封存批次清單整理」Task 掛在「庫存查核與差異說明」Duty 下，而另有「封存批次清單整理與追溯」Duty 沒有 Task，構成目前分組的具體待核差異。第 11 輪 W05 更正未成功發布／寫入 JD，因此現稿的盤點頻率仍標待確認；不能把當輪已保存原話誤當現稿已反映。依[工作分析指南](../2026-09-09-complete-work-analysis-guide.md)、[JD 欄位／寫作指南](../2026-09-09-jd-field-and-writing-guide.md)及[品質 Q01–Q15](../2026-09-10-jd-product-quality-acceptance.md)，這是可回查的**部分工作稿**，不是完整 JD 品質 PASS；缺少 K／S、出貨 Task、正確分組、更正後全稿核對與瀏覽器來源／撤回驗證仍是後續 gate。這些觀察尚不足以歸因 Prompt、Memory 或 JD Domain，故本次不做猜測式產品修改。

#### B1 失敗再定位：第 141 筆後缺內層拒絕碼

續以相同**已停止**隔離帳本及鎖定程式唯讀核對，沒有恢復工作或外送請求。B1 最後三筆模型請求為第 132、136、141 筆，皆已結算；第 141 筆完成後至下一筆已准入的第 142 筆 A 請求，中間**沒有 B1 新 attempt**、未知費用預留或 provider HTTP 回應。第 141 筆以前全部已結算費用合計 **US$0.45005514**；加上現行 B1 一筆保守預留 **US$0.287076** 為 **US$0.73713114**，且當時只用到 141／180 個實際外送名額。故「當時已碰 US$1 或 180 次總上限」不是這次 B1 失敗的解釋。

鎖定的 test-only `P3SpendGate.begin()` 在真正外送前驗角色、request 契約、串行等待、次數與費用；若在 admission 前拒絕，`attempt_count` 不增加。鎖定 OpenAI Python SDK 的同步／非同步 `_base_client` 送出邊界均會將非 `OpenAIError` 的一般例外（包括此處可能的 `BudgetGateError`）包成 `APIConnectionError`，並只把原例外留在 `__cause__`；目前 B1 Saver `__error__` 只保留外層 `OpenAIConnectionError`。**這使本機 pre-admission 拒絕成為具體候選，而非已證根因**；也不能從沒有 attempt 單獨證明必定是角色、wire、串行等待或其他哪一個檢查。帳本顯示第 142 筆 A 請求稍後外送並耗時約 46 秒，但沒有 B1 下一次呼叫的精確時點，故不能排除或坐實 30 秒串行等待逾時。下一次驗證應在既有 P3 test-only client 邊界保留**有限、安全的 pre-admission 錯誤碼與角色**，或等價取得例外 cause；不保存原話／金鑰、不修改正式 dispatcher、Memory、publication 或放寬支出上限。取得具體碼前，本次 B1 仍 `OPEN`。

依此缺口，僅在既有 **P3 test-only** 帳本增加 `first_pre_admission_rejection`：首次拒絕的 allowlisted role、固定代碼白名單、當時已准入筆數及時間；不保存 request／response、原話、credential、exception stack，不把拒絕計成外送，也不增加新紀錄服務。同步的「另一請求占用閘門、B1 等待逾時」與非同步的「缺角色」兩個零網路反例先因沒有該欄位而失敗，補接後均通過；後者亦驗證重新建立帳本物件仍能讀回同一筆紀錄，**沒有做跨程序測試**。另以未知但符合一般字串格式的錯誤文字作反例，先確認原接法會原樣落盤，再改為 `pre_admission_unknown`；避免未來意外保存敏感字串。受影響的 P3 閘門及試跑入口測試 **60 passed／0 failed**，沒有修改正式 App／SDK、背景排程、Memory 或產品費用規則。這是**下次試跑的診斷能力**，無法回填本次第 141 筆之後已遺失的內層原因；本次 B1 根因與自然背景完成仍 `OPEN`。

### 同一批試跑的 JD 來源語意唯讀核對：一筆錯誤背書

2026-09-23 繼續沿用上述**已停止**的隔離目標，僅以唯讀 PostgreSQL 與 Saver 檢查 JD revision 10 的來源，沒有重啟試跑、恢復背景、送模型或修改產品。18 筆 `jd_source_link` 對應 5 個不同的 signed conversation source；五個簽章均可在本文件 scope 解析，所指 pinned Saver checkpoint 存在，且選出的 canonical assistant／employee 訊息範圍與 locator 相符。這只證明結構及可回查性，不證明來源對每個 JD 句子的語意支持，也**沒有執行 Browser 來源導覽**。

具體反例在 JD revision 4 建立的「零件出貨核對、包裝與交運記錄」Duty：其一筆來源是員工描述依核准揀貨單核品號與數量、包裝、記錄交運、缺件回報及不自行換料號，確實支持該 Duty；另一筆來源則是較晚的庫存查核回合，員工說明無法確定試算表欄位、區分兩種庫存差異並請顧問先起草 JD，前一則顧問問題也只涉及盤點與試算表。該回合**沒有出貨事實**，不能為這項出貨職責背書。此為[JD 品質驗收 Q11](../2026-09-10-jd-product-quality-acceptance.md#4-可執行驗收-rubric正例與反例)的實際 `FAIL`。

同一唯讀核對亦逐筆比對了目前 18 筆 link 的 JD 目標與五段完整問答，而非只檢查簽章。其他連結中有多筆由**兩段互補員工原話共同**支持收貨核對、入庫紀錄與差異處理，不能要求單一來源逐字包含整項複合 Duty。另有一筆「零件收貨與入庫核對」Duty 連到**出貨回合**：該回合的顧問提問重述了前輪收貨與入庫紀錄，員工本輪只說上架責任未知並描述出貨。由於顧問重述不是新的員工事實，這筆不能視為獨立的收貨確認；它與另兩筆直接收貨原話並列，屬**支持範圍待判讀／冗餘引用風險**，目前不把它等同上一筆確定無關的出貨錯引，也不因此把其餘 17 筆一律宣告語意 PASS。若要正式驗收所有來源，需要按 JD 文字的具體主張與原話角色逐項判讀，而不只計算連結數。

Saver 工具序列與 JD revision 對照可定位接合點：模型首次提出出貨 Duty 時選的兩個 `basis_evidence_keys` 均指向出貨原話，但該次 `jd_insert_item` 回 `invalid_input`、沒有保存；重試時模型保留其中一個出貨 key，另選了當輪庫存差異的 `current_turn` key，這次 `jd_insert_item` 回 `committed`，revision 4 的兩筆 source links 正是上述兩個來源。依[既有來源契約 §7.2](../2026-09-20-cross-agent-evidence-and-jd-context-contract.md#72-jd-寫入只接收-evidence-keys)，模型決定哪筆 evidence 支持哪個 JD 項目；Runtime 驗 document、scope、已讀／可讀及定位，不代模型判讀原話語意，也不自動附加來源。本次證據指向**模型在重試時選了不支持該項目的 key**，不是已證的簽章映射、跨文件隔離或 Domain 保存錯誤。現有 model-facing 欄位描述已要求 key「只支持本項目」，因此不能在未取得反例改善證據前斷言多加一句通用提醒就能修好。

再以同一**已停止**合成資料庫的 root Saver `messages` 唯讀定位兩次工具呼叫及其間的 `jd_read`：第一次 `jd_insert_item` 的 `kind=duty`，其 `container_ref`（339 字元）**逐字等於**緊鄰上一筆成功 `jd_read current` 中 `type=container／child_kind=duty` 的引用；但 `after_ref` 只有 100 字元，與該頁及此前各頁已發出的 item／container／field／section／owner refs 均不相等，也不是它們的前綴。Domain 的 `_insert_item` 在處理這個排序錨點時以 `_anchor → work.ref` 要求它屬於 current read 的已發配引用；該次 `invalid_input` 回饋亦要求重新讀取並原樣複製引用。這證明**至少一個提交的排序引用無效**，而不是可以把首敗簡稱為「模型選錯 duty 容器」；100 字元究竟是模型自行拼造、截斷或其他生成失誤，現有 trace 無法再細分。模型隨後重讀同版 current；第二次 `after_ref` 為完整 365 字元、與該頁 `type=item` 的 item_ref 精確相等並成功保存，但兩個來源 key 中有一個同時改為無關的當輪庫存來源。第一次定位錯誤與第二次語意錯引是先後相連、責任不同的失敗，不可用「已修好定位」推論引用品質通過。

這個新反例也對既有 JD model-view 評估提供實測動機：長 signed target refs 除 token 成本外，現在有一次**未發配短錨點**的真模型輸入。然而單一反例仍不能證明「長度」是唯一根因，或直接授權把正式 JD target refs 全改短代號。[跨角色證據契約 §0](../2026-09-20-cross-agent-evidence-and-jd-context-contract.md#0-preflight)目前明確保留 current-revision JD target refs 讓模型選擇；[先前零付費候選](#jd-撰寫回合的-context-膨脹與反覆摘要分項唯讀診斷)只是無損表格化對照，尚未驗 writer round-trip。下一步若比較短 target handle，須先在**同一 JD read／writer owner 的 test-only model view**證明短 handle→原已發配 ref 的唯一還原、current revision／scope／target kind 與來源／receipt 不變，再交 Owner 裁決是否修改正式 model-facing 契約；不另造 DB authority、通用 registry 或語意驗證器。OpenAI [Function Calling](https://developers.openai.com/api/docs/guides/function-calling)（查閱 2026-09-23）對 recurring tool failures 建議清楚參數格式與邊界；Anthropic [Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)（同日查閱）建議對模型回傳穩定、具語意的識別符而非冗長不透明內部引用。這些是供比較的公開原則，**不等於**兩家保證短 handle 能解決本案或背書 Caliburn 的具體 schema。

驗收狀態：**來源結構／Pinned Saver 可讀 PASS；來源語意 Q11 FAIL；Browser 導覽 NOT_OBSERVED；完整 JD 仍 OPEN。**後續沿現有模型選 key／工具回饋 owner 提出可重現、最小的候選改善與受影響測試；不新增第二套來源庫、語意 validator 或讓 Runtime 猜來源，也不因這一筆錯誤重做 Memory／JD 架構。若候選要改 Prompt／Skill 或正式工具描述，先與 Owner 對齊其語意與取捨。

### V4A 提示後的新隔離 C-W 試跑：Working State 讀取證明首敗

2026-09-23 以 commit `07acb824ffb28496e767d3ebdd3ab05e929339c6` 開新隔離目標 `jd-ui-gate-b6a48a120c2d4a939ed67a5e87f21340`，正式新 App、GPT-6 Luna Responses／OpenAI-only、A 64K／B1/B2 128K 與同一有界 P3 閘門。dataset `ea30b60a-ab1b-4fc3-95ef-3f18140a12df`、文件 `888c1300-1ff7-4ad1-9467-1abe62cd2ddc`。Windows 受限 token 初次初始化停在 `initialization_pending`，依既有 `resume=True` 在可存取環境完成；初次建立文件忘帶正式 dataset header 收到 409，補上 header 後才建立，均未改產品或遺失資料。合成員工只按已曝光 C-W 卡片回應自然追問，未把卡片／oracle 送模型，也沒有強迫每輪編 JD。

前 7 次員工輸入均 `completed` 且有自然回覆，未知的收貨放行、出貨交接、試算表細節與未查證的盤點頻率都保留為未知／印象。背景 A／B1／B2 實際外送；關停後唯讀 DB 顯示 Memory head revision 3、背景 admission `idle`。第 8 次回答兩個不同差異案例後，模型先讀兩筆 Working State item，成功修訂第一筆，再試圖修訂第二筆；最後一個 `update_interview_working_state` 沒有 ToolMessage。Saver root／child 的 pending `__error__` 是 `AiToolError('ai_tool_unavailable')`，公開 run 為 `recovery_required`、員工原話 `saved`、無 final；原 run 的一次明示 recover 回 503，沒有重送員工 POST。隔離 JD 仍 revision 1／0 筆 operation，因此**這批尚未驗 JD 寫入或品質**。本批 8 次員工輸入、57 筆 provider request 全數結算 **US$0.034258200**，未知保留及在途均 0。試跑已按 stop request 退出，但 `serve.finished.json` 的 `app_closed=false`、`saver_connection_closed=false`；舊隔離資料與 pending run 保留，不能冒稱優雅關閉。

零付費分層定位：第二次 Working State patch 本身以目前 checkpoint state 經正式 parser／`_apply_update` 可成功；但 `working_evidence_catalog` 以已保存同輪 ToolMessage 重算時，可重現 `invalid_working_state`。原 `_read_item_ids` 拿**讀取當時**的完整 item ToolMessage，和**第一次修訂後**的 current item 正文逐字比較；正常文字變更被當作假 read proof。這是 Working State 自身驗證時點錯置，不是 OpenRouter 400、Memory 發布、JD Domain 或新增 Agent 的需求。窄修正仍在同一 owner：驗證當時 ToolMessage 的 scope、call identity、private artifact、digest 與投影一致性；只有來源集合仍與 current item 相同時，舊 read 才可展開目前來源；來源已變則舊 read 不授權新來源，也不因正常修訂卡死整輪。不改 canonical conversation、Memory、JD、工具 schema、Prompt、費用上限或重試。

同檔 regression 先以「同輪讀取後只修文字」得到預期紅燈，再以「來源變更後舊 read 不授權新來源」得到第二個紅燈；修後受影響 Working State **15 passed**，並直接用本批 Saver 最後 checkpoint 做唯讀重算，不再出現該 `invalid_working_state`。完整新 App 離線 suite 在可存取 Windows 暫存環境 **3,185 passed／323 skipped／0 failed**；受限沙盒第一次使用 pytest 暫存資料夾有 `WinError 5` setup errors，不能當產品回歸。這些只驗證 deterministic 讀取證明與相鄰契約；**真模型第 8 輪不會重送，修後自然訪談、C 更正、完整 JD／Q11 來源語意、Browser 仍 OPEN**。下一次須再用新凍結 commit／新隔離目標延續有界自然驗收，不沿用本批帳本或把離線結果冒稱完整產品通過。

### Working State 修後的獨立 C-W 長訪談：12 輪上限結果

固定 commit `c1678359889b4faf39e2ed287d910acd03690ece`、新隔離目標 `jd-ui-gate-af5e1d33c3a5446797a366aea6835f5f`、dataset `9c595693-e365-4f8b-9a55-b08bb7b86e23`、文件 `4466b141-1c8e-493a-82fb-15faf15de7b2`。沿同一已核准 P3 C-W 卡、正式新 App、GPT-6 Luna Responses/OpenAI-only，員工回答不提供 oracle、工具名或寫 JD 指令；每輪只按自然提問揭露。程式整理後重新驗證 Working State 指定測試 **15 passed**、完整新 App **3,185 passed／323 skipped**，無新產品差異。

12／12 次員工 POST 的原話已保存、各 run `completed` 且有自然 assistant final；第 8 輪含到貨短少與重複入帳兩案，這次正常回覆並保持處理結論分開，惟未單憑 final 證明模型重現前批完全相同的兩次 Working State 工具序列。顧問多次保留員工明言「不清楚」的放行、調帳、試算表與重量資訊；對「印象中每月全盤」沒有提前升格為確定事實。第 12 輪員工明確查證更正為「每週只循環盤 A 類料，每季才全庫盤點」，final 自然回覆正確轉述，沒有說每月全盤。這是**對話層更正 PASS**，不是 Memory 或 JD 寫入 PASS。第 4 輪查詢 run 狀態曾短暫收到 503，但同一 run 隨後查回 `completed` 與 final；沒有重送員工 POST。

正式 PostgreSQL 首次唯讀核對：背景 B1／B2 有四筆 `consolidation` publication，最新 Memory head revision 4，admission 回到 `idle`；無 `repair` receipt。當時檢視到較早 artifact 的盤點案例及理解仍寫「頻率尚未查證」，約在 **11:46:43 UTC** 形成，早於第 12 輪更正；這個時間點的觀察**不是最終 head 的內容結論**，關停後正式讀取器的複核結果見下方。JD head 仍 revision 1、`jd_operation` 0、12 輪 `jd_effects.results` 全空；沒有 AI 工作稿可做來源、改動查看、手改或撤回驗收。這批未證明「資訊必然不足」或「JD writer 必然有程式故障」，但 P3 所要求的完整 JD 旅程**未達成**；已揭露 W01／W03／W04／W07 等可支持的局部內容，需在下一個有界續談中確認顧問是否能適時開始撰稿。

支出閘門紀錄：**12 員工回合／61 實際 provider requests（A 19、B1 18、B2 24）／US$0.037472660**，全部 settled、在途與未知保留皆 0，無 fallback。達原 [P3 首批停止線](../2026-09-10-jd-product-quality-acceptance.md#6-p3-首個自然縱切有界尚未執行)後未增加 cap、未再送員工訊息。正常 stop 後 `app_closed=true`、`saver_connection_closed=true`；隔離 PostgreSQL、Saver、Store 與原話保留，不刪資料。下一步先就**同一文件續談所需的新一批回合／請求／費用上限及測試入口**取得具體裁決，不能用重啟繞過這批 12 輪閘門；再驗 JD 首建／局部足夠時機、來源語意與後續 Browser 旅程。Memory 更正的最終發布狀態以下方正式讀取器複核為準，不重驗較早 artifact 快照。不為了這批未完成直接改 Prompt、Memory 架構或新增 Agent。

**關停後正式讀取器唯讀複核（取代上方較早 artifact 推論）：**以該隔離文件的正式 `ConversationSourceService`、`PublicationStore` 與 `MemoryArtifacts` 讀取同一 head v4，不啟動顧問、背景或模型。已保存安全回合共 12 輪；v4 的 `processed_source` 固定窗口包含第 12 輪，`pending_windows(document_id, processed_source)` 為空。v4 bundle 共有 5 筆目前案例、4 筆工作理解；正文關鍵詞核對發現「每週」「每季」各在一筆案例與一筆工作理解中，「頻率尚未查證」不在目前正文；唯一「每月」是案例明確寫的「不是每月全盤」。因此第 12 輪更正**已由背景 B1／B2 正式發布並可回查**，先前「尚未寫入 Memory」判斷不成立。這不證明每個案例細節或 JD 品質全面合格，也不要求為了沒有 C receipt 另做即時修補。

同一 Saver 的 12 輪 A 工具序列只有兩次 Skill 檔案讀取與五次 `request_memory_consolidation`，沒有 JD read／write、Working State read／update 或 `repair_memory`；根 state 的 `interview_working_state` 為空。因此 JD revision 1／0 operation 的直接責任層是**本批顧問未嘗試 JD 工具**，不是已有工具寫入卻被 DB／receipt 吞掉。本批沒有要求每輪寫 JD；不能單憑 12 輪無寫入判定 prompt 或撰稿時機缺陷。下一個有界續談才檢查局部內容足夠時能否自然起稿；若仍不動筆，再以具體對話、已讀 Memory 與 request view 診斷，不預先改產品語意。
