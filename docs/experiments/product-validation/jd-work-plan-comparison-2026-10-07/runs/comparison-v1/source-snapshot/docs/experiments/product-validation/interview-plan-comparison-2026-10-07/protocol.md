# 長訪談 P1／P2 有限比較（2026-10-07）

本批依已接受設計 §7.1 與本次使用者真 API 授權執行。P1 使用共用 FOCUS 指引與既有 JD／Memory；P2 使用相同能力及 guides，加持久短筆記指引、工具與投影。沒有人工筆記、私有 oracle 或其他組答案注入顧問。

pilot 為倉庫兩組各最多 6 Turn，費用保留上限 US$0.60、30 分鐘、80 次生成、2 次 compact、200 次外送與 4M 累計 counted input。它只核接線與披露，不列正式品質證據。

正式為倉庫／課務行政各配對重複兩次，共 8 場；每場最多 20 Turn，第 20 Turn 使用同一收束輸入，請模型整理已確認事實、保存正式 JD 並指出未知。全批 US$8、4 小時、1500 次生成、16 次 compact、3500 次外送與 40M 累計 counted input。生成與外送額度依先導 11 Turn 使用 80 次生成／175 次外送的機械成本校準；費用、時長、compact 與 counted input 界線未放寬。不得把共同收束或模型自報完成稱成自然完成。資源停止與失敗原件保留，未排到的場次明列；不重設 guard 續跑。

重複 1 保留 production 原生 128K／160K 門檻。重複 2 僅在隔離程序將 A 的 mid-work 門檻一次設為實際 counted input 45K，收到第一次 A native compact 原件後恢復 160K；兩組條件一致，B 的門檻不改。這是受控換窗機制壓力觀察，與自然長任務分開。實際未跨門檻／compact 未發生須如實報告。

初始化為各組獨立新 schema、同空白 JD／Memory、同公開工作輪廓及案例。模型、有效 guides、prompt、工具契約、程式、私有事實與披露政策 hash 在每批 manifest 凍結；正式另逐檔保存精確原文 source-snapshot，出站前重新核對。完整外送 request 的公開 input、instructions、tools 保留；opaque item 保存完整 hash 並去除 encrypted_content。RAG 兩組皆關閉。所有正式寫入及讀取透過真 loopback 產品 HTTP；唯 migration 與原 checkpoint／背景執行觀測在隔離 DB／保存接縫讀取，不作業務寫入。

回答者依[人工披露政策](disclosure-policy.md)逐題匿名核定，keyword candidate 不作放行權威；compound 最多回 4 個明確相關且可取得的凍結事實原字串。不知道保留，拒答不重開；部分盤點／代課問題須在 gap 開啟後實際轉到指定新主題，再在顧問相關回訪時揭露責任。更正依同題追問觸發，沒有第幾輪補正。每次保留問題、判定、員工原話、selected／submitted／formal 可見及剩餘未知供污染核查。這是合成人工政策近似，無法直接推論真人負擔。

護欄沿既有 BatchGuard／ObservedStream 擴充有限 compact 入場：須匹配原 input count，input 不超過 200K；compact API 沒有本次可用的 max_output wire 參數，故以 1.05M 整個模型 window 的長上下文最壞費率保留 output 費用。此 reserve 是有界工程估計，不是 provider 票據保證。用量未知或超出 reserve 即停並保留額度；錯誤／429 保留該次 reserve，產品自己的有界重試仍計入批次上限。SDK 全部原始 chunks／C 照原件傳回；artifact 遞迴排除 encrypted_content，只留下完整 item hash。金鑰只經既有 reader 讀入記憶體，無環境或 header 輸出。

真正 mid-work 換窗須同時核 provider compact C、preparation_policy 為 null 的已提交 adopted checkpoint 的完整 C hash，及後續 A request 的完整 prefix hash；pre-work 換窗另列，不能冒充受控 mid-work 證據。P2 另核 saved projection.input_binding 的 compact thread／checkpoint 恰為該 C、後續 A item 恰為 saved plan_item，以及公開 plan 讀取。只有 compact 成功或 B 的 compact 不成立。

盲評 bundle 只給匿名正式 JD、正式 HTTP 已提交的員工原話及 JD 來源可讀正文。以實際 formal revision／citation 與其固定可達 source_ref 沿正式 HTTP 讀原 Memory／情境／原話正文，不能以 latest Memory 替換。bundle 位於 blind-input/<opaque ID>.json；解盲 mapping 由 root 封存，評閱者鎖定評語前不讀。評閱者先固定依現有三指南的語意判準；不看組別、plan、工具、成本與模型過程。先判重要工作有據涵蓋、責任／判斷／交付、要求與跨欄一致，以及無據／誤歸責，再解盲對照實際回訪與成本；不建立總分，不挑最佳場。相近資源品質和多問後品質／負擔分開，尚未披露且未入稿與已披露卻漏稿分開。

官方依據：[Compaction](https://developers.openai.com/api/docs/guides/compaction)、[compact API](https://developers.openai.com/api/reference/resources/responses/methods/compact)、[Luna 規格](https://developers.openai.com/api/docs/models/gpt-6-luna)、[費率](https://developers.openai.com/api/docs/pricing)。費率計算以 repository 固定 pricing object 為準，本批僅 Luna／default tier。

離線 Red：既有 transport 真拒 `/responses/compact`，4 個反例失敗；有限擴充後 4/4 Green。新增條件披露反例核部分答案返回、摘要不能洩漏年度私有事實及拒答不重开。

首次 pilot 啟動在 provider 前因 Windows Proactor／psycopg 不相容失敗，pilot/manifest 與 batch-state 保留，所有外送／費用為 0。改沿現有 PG 測試 SelectorEventLoop，真 PG＋產品 HTTP 無 key preflight 通過。獨立人工政策審查發現同義／摘要／compound／個案拒答／未送答案的反例，故 paid pilot 使用 mandatory anonymous review，而不以擴 keywords 保證公平。先導原件保留在 pilot-reviewed，80 次生成均有唯一 usage，無缺漏保留額度；P1 6 Turn 有收束，P2 5 Turn 後被 cap 停止，背景 Memory 1 次失敗及 async stream warning 保留。兩組均有正式 JD；P2 真 read／edit 與公開 plan 生效，但沒有 actual compact，不能稱換窗驗證。正式新增 no_question／true unknown compound 分支及引用正文／匿名 bundle 的離線反例；先導政策／未先封存的舊 harness 限制見 [先導證據](pilot-results.md)，不列品質勝負樣本。
