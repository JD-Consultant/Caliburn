# P3 首例付費前：零成本執行防護前置

2026-09-10。**文件前置完成；防護未驗、自然 trial 未執行、180 provider requests／12 員工回合／US$1.00 仍為 NOT AUTHORIZED 提案。** 本次 0 inference requests、0 付費，沒有讀 key／`.env`、載入 Settings、安裝或執行任何 helper／模型／API／DB／Job。僅查官方公開文件及唯讀原碼；不改 durable 決策或阻擋 Task4 review、Task5／6 工程。

## 1. 結論與證據界線

已採模型可精確對應到 `gpt-5.6-luna`、OpenAI Responses binding、A／B1／B2 high、顯式 8192、all_turns、native compaction 12000；但**尚未發生的 P3 實際程序／endpoint／最終 request 配置不能由環境變數預設推定**。P3 凍結時須再核實，不把 CT50／51 或目前原碼當新 trial 的實測。

可重用 CT51 封存的 HTTP request／response hook、單程序同步帳本、每次嘗試預留及消毒 trace。**不能直接重用其位元組估 token 公式宣稱 US$1 硬上限。** 現有 runtime `ResponsesBudget` 是 context 容量契約，不是美元 limiter；LangChain 模型步數也不是實際 provider HTTP attempts。

依據：`docs/specs/2026-09-10-jd-product-quality-acceptance.md` §1、§4–6、§9；`docs/specs/evidence/jd-product-p3-calibration/` README／release-protocol／manifest／results-template（W01–10、M-W1 沿既有 C-W，不新增內容）；`docs/specs/2026-09-10-jd-production-adoption-design.md` §3.3。所有 runtime／CT helper 原碼均從已接受 **80e29b4a98363f10cffeaf332802adb6f6e29329** 的 `git show` 讀取，不讀 Task4 未接受版本。CT helper 是該 commit 的 `docs/specs/evidence/2026-09-09-ct51-output-budget.json` 內 `scripts` 字串；只解析 JSON／閱讀文字，沒有匯出或執行腳本。

## 2. 已接受配置與可重用接點

以下 runtime 路徑皆相對 `experiments/analysis-agent/src/analysis_agent/`，位置指上述 commit。

|原碼／證據位置|已確認事實|P3 必保留／不得誤稱|
|---|---|---|
|`api.py` open_service，約103–183|Q019_MODEL 預設 gpt-5.6-luna；A effort／B2 effort 預設 high，B1 固定 high。output／compaction／capacity／timeout／poll／recoveries 明確要求設定。counter SDK 公開 base_url 同時傳 model；OPENAI_BASE_URL 可影響它。|不讀 key 即能確認配置路徑，不能確認此 trial 的實際 endpoint。正式接手沿 Luna/high/8192，不混舊 OpenRouter／Opus；最終組裝需記無秘密的實際值及 request fixture。|
|`provider.py` build_model|ChatOpenAI，use_responses_api=True、responses/v1、store=False、truncation disabled、reasoning context all_turns、parallel_tool_calls False、顯式 timeout／native compaction；output 由 composition model copy 設定。沒有自行固定 SDK max_retries。|binding 與 provider 帳戶／授權分開。現有 SDK retry 不能被當 0；每個實際 HTTP 嘗試都須經 hook。無改模型／effort／上限／重試政策的本輪授權。|
|`budget.py` ResponsesBudget|native 模式核 model/output/truncation，不發 count；exact 模式另呼叫 responses.input_tokens.count。其註解明示非近似 token 保證，也無法預測待回應新 inline compaction。|不是美元 guard。不得為計費前置偷偷切 exact 或額外呼叫 count；若將來另採有外部呼叫的計数方案，需先釐清計數與授權範圍。|
|`conversation.py` build_conversation；`service.py` constructor|A 每 input 的框架 16 模型／15 工具；resume 沿 checkpoint 不歸零。|12 員工回合不是最多 12 模型請求；16 也不包括 SDK 的重送嘗試，更不覆蓋另一角色的 calls。|
|`consolidation.py`；`extraction.py`；`scheduling.py`|B2 有16／15與 durable used counters；B1 分 windows，validation correction 有先保存 reservation 的 allowance；dispatcher 接受明確 recoveries／最多 windows。|以上限制各守角色／操作，不是整批 provider cap。B1 校正、B2 多步、既有恢復及所有失敗嘗試均入同批帳本。|
|`service.py` get_run 約386–402|前景 AIMessage usage_metadata 加總 input/output/total，無 usage 時 usage_complete=False；只投影 allow-list。|UI run usage 不包含全批 A+B，也無完整 cached／cache-write／inflight 成本對帳，不能取代 HTTP 層帳本。缺失不是 0。|
|CT51 JSON scripts `ct51_service.py::CT51Ledger.before`；`native_service_probe.py::Ledger.after`|每次 HTTP 前鎖住、驗 endpoint/model/high/output/function tools/tier/body size／running 狀態；計 attempts、reserve、先 save；response 保存 status/usage/tier，未知 usage 保留 reserve。|可沿既有 harness 接線再有限補核。舊實驗 state／authorization／DB／closed ledger 不重開；不將試驗帳本搬成產品第二 operation／Memory authority。|
|同 JSON `ct15_full.py` 的 Audited client|request hook 置於原 hooks 前，response hook 接後；A、B 模型共享 composition client；真服務 driver 使用這接點。|這是 TestClient 所在程序的 monkeypatch，不會自動覆蓋另一個已啟動 Uvicorn／browser 所連 API。真 P3 每個出站 client 與重開程序都必須證明受同一批 cap 管理，不能只 patch 測試端。|

CT51 `Ledger.after` 保存可見 input/output、tool definitions、status、incomplete_details、usage、耗時與 service tier；reasoning／compaction 只留 hash／存在標記，錯誤採有限欄位。可沿用消毒規則；不記 headers、credential、任意 exception body 或 opaque reasoning 原文。逐 request 還須可映射 trial／員工事件／A或B角色／run與operation，不因不同執行緒回覆順序交錯而錯配。

## 3. 三條提案界線必須同時成立

|提案|真實計數／停止界線|具體不足|
|---|---|---|
|最多12員工回合|人員實際送入的開場、回答、更正、澄清、收尾／重開後續談都計回合；純手改不是聊天回合。|不能拿第12輪之後的「只回查一下」無限續談。相同已保存送件的只讀對帳不新造回合／模型，必須區分。|
|最多180 provider requests|同一 trial 前景A、Memory B1/B2、所有 SDK retry／校正／恢復／模型讀取回覆、任何在途已出站 attempt 都共用總數；每次出站前先預留一名額，失敗不退名額。|本地 read_file／JD deterministic tool／UI polling 不是 provider request；由其引起的下一個模型 request 則是。計數服務等額外出站不可漏算或擅開。單輪／單角色 cap 與總 cap 都成立，不以 12×16 當全批。|
|US$1.00 硬上限|出站前檢查「已結算估算＋全部在途／未知保留＋下一次最壞費用」；不能成立或 usage 不可對帳就停發。先停 admission，再沿既定 lifecycle 處理在途，保留已存成果。|取消／關頁／timeout 不能證明 provider 未計費；未知 reserve 不釋放。停止不取消已發生支出，也不重開 closed 帳本或自動增加額度。|

180 是最大次數而非保證可跑滿的配額。以當日 Standard 短 context output 費率作純算術示例，180×8192×US$1.20／1M＝US$1.769472，尚未含 input；所以三界線中美元限制可能先到。這不是費用預測，不更改8192或建議加額。

## 4. 官方定點事實與美元硬保證缺口

2026-09-10 依 OpenAI Docs 技能查阅并開啟：

- [Luna model](https://developers.openai.com/api/docs/models/gpt-5.6-luna)：支援 Responses、高推理與1,050,000 context；模型容量不是此 trial 已接受最大計費輸入。
- [Pricing](https://developers.openai.com/api/docs/pricing)：Standard Luna 每百萬 tokens，短 context input／cached／cache-write／output 為 $0.20／$0.02／$0.25／$1.20；長 context 為 $0.40／$0.04／$0.50／$1.80；Fast mode／region 有不同條件。必須在實際執行日核對適用 tier／context／endpoint，不用舊 CT 平均費用保證。此頁讀取未閉合本 trial 的短／長門檻及 inline compaction 計費上界，仍列待證，不猜。
- [Reasoning](https://developers.openai.com/api/docs/guides/reasoning#allocating-space-for-reasoning)：reasoning 計入 output 費用；max_output_tokens 用完可 incomplete，甚至沒有可見答案仍產生費用。8192含reasoning，不要另外再加一次reasoning usage。

**P3-B01／token與費率上界未閉合。** CT51 reserve 是 `max(64000, serialized_bytes×2)×0.25/1M + output_bound×1.2/1M`，註解稱診斷保守估計，非 exact tokenizer。128000 body bytes 的限制不自行證明 opaque context、provider內部表示／inline compaction或其他接受欄位的 billable tokens 上界。CT guard 也未 whitelist 全部 top-level input paths。0.25 只覆蓋該既有短 context cache-write 費率，並非所有 tier。需要沿既有 harness 證明本次實際接受請求的最大可能帳單費用；證明不足就不稱 $1 硬保證，不另外造通用 budget engine。exact count 也不能被當作所有生成／compaction支出的總解答。

**P3-B02／usage不可對帳未必停下一請求。** CT after 對無 usage、invalid JSON、非200保留原 reserve 是可用起點，但沒有一律把整批標 stop；正常200的 usage 僅 get 預設值，未充分拒負值、非整數、cached+write>input、費用超出 reserve 等。這不滿足 P3「不可對帳即停止」。完整 usage 才可依確定規則釋放差額；unknown 不歸零、不樂觀假 cache hit。

**P3-B03／真產品與重開覆蓋未驗。** RLock 只保護單程序；save 是直接 write_text，pending 是記憶體字典 id(request)，不是跨程序原子總批預留。CT依次driver保存並reload的方式不證明突然 crash／雙程序／真browser API仍受限。需有界證明本次單批 owner、持久預留、lost reply／重開後不清名額或未知金額，以及關閉後不漏背景請求；不能把 Task5 Job 停止證據當遠端計費取消證據。

**P3-B04／counter、retry及trace實際覆蓋未驗。** native無 count；exact有另一個counter client。現行 build_model 未明設retry，不能只數 LangChain invocation。guard拒絕須在network前且不被分類成可重送網路失敗。到額度或使用量未知時A與B都停新provider請求；留下的背景 durable work不能在下次普通開機避開本批授權自動付費。既有 trace 只記回傳 service_tier 還不足以事前保證採價，需核配置與最終request。

以上是 P3 執行前缺口，不改判 CT49–51 歷史觀測，不推論舊帳單超額，也不開模型／Memory重研究。

## 5. 交 Owner 確認前必備 offline checks（本輪均未執行）

|ID|離線固定檢查|應保存的 PASS 證據|
|---|---|---|
|OFF01 凍結|核心Task1–6接受後記 exact commit／lock／prompt／Skill／schema hashes；C-W pack manifest逐檔hash核對。|實際BASE與完整配置表；未知不可假填。自然cap與模型16／15分欄；不更改compaction門檻湊覆蓋。|
|OFF02 斷網接線|使用假credential及拒全部出站 transport，涵蓋實際產品composition的A/B1/B2/counter與重開入口。|network attempts實際0；guard掛載位置、每個client路由可查。只用MockTransport／TestClient替代產品啟動觀察時明標限制。|
|OFF03 最終request契約|fixture核 endpoint/model/high/8192/all_turns/native配置、store/truncation、tool種類、tier、最大接受payload／opaque內容。|錯endpoint／model／effort／output／tier／非預期內容路徑在transport前拒；token／費率上界推導及來源封存。沒有證據就P3-B01 OPEN。|
|OFF04 總數競爭|模擬A與B並行接近180，以及SDK重試／B1校正／B2多步／恢復。|每次attempt在出站前佔名額；第181個不能出站；被拒不是另一個付費重試；已發失敗不退額。|
|OFF05 費用競爭|逼近$1時同時有多筆在途與下一筆，所有價格／數值合法性反例。|檢查與reserve原子，不雙花剩餘額度；上界超預留即停止，不先放行再補帳。cache-write不低估，reasoning不重複算。|
|OFF06 未知與取消|timeout、取消、invalid JSON、非200、缺usage、缺cache細項、負值、重複response、超出reserve、突然程序結束。|未知保留／整批停新request，重開不reset；不能用cancel確認或local stop釋放provider reserve。已完成operation沿原receipt查回。|
|OFF07 closed與重開|closed／未授權／舊CT ledger、另一文件背景／新程序啟動試圖請求。|全拒且不偷建新帳本；restore/reload不新增預算；真實執行時只包含該獲授權trial工作。|
|OFF08 turn及資料|12回合邊界、手改分離、自然揭露離線演練、Q正反例判讀。|第13個新聊天input不能為湊測試放行；無oracle／卡全文／其他案例入model context；M-W1 document與聊天澄清各有event。|
|OFF09 trace／收尾|以非秘密fixture核 trace allow-list、role／request／event映射、順序交錯、usage缺失与first failure。|無key/headers/opaque reasoning原文；可見問答／工具／JD receipt／Memory狀態可對照；drain/close後仍0新request。|

只沿必要既有測試harness／hook補證，不重跑Task1–3完整基底，不把fixture成功稱自然品質通過。若必須更動設計才可建立費用上界，先將具體缺口交root，不默默放寬硬上限或提前付費。

## 6. 待決資料與人員（本輪不向Owner提問）

- 首批範圍明確為單一公開C-W、自然角色扮演；不含P6六次、新職位、真人工作資料、judge或模擬員工LLM。只傳實際已揭露的合成回答及由App正常產生的必要JD／Memory／原話工具內容，不整包上傳oracle、研究檔或CT歷史資料。
- 待指定真正的人員card operator、操作方式／時間與判讀者；資料作者與判讀者若同人明示。Agent可以準備／觀測，但不冒稱自己是人員；若要改成agent扮演是協議變動，不能由本前置自行採用。自然角色扮演也不等同真員工實務驗收。
- 待完整核心BASE、空JD／訪談／Memory之明確隔離trial、合法正式endpoint與當日適用價、驗證完成的本批guard及新增執行授權。不能挪用CT49–51授權或Account現有餘額當同意。
- 提交Owner時須有具體可審的執行包：上述offline結果、仍未解風險、模型／資料／操作人、三個同時上限、停止及未知對帳路徑。任何一項硬保證未成立，包上如實列未ready；不以此阻擋其餘零付費工程。

本輪產物只有本報告；沒有已驗防護、trial問答／JD／usage或付費結果。

## 2026-09-10 操作者來源效力與採用補記

原§6『待指定真正的人員card operator』是當時品質§6測法的假設，不是已找到的Owner硬裁決。Root經有限spec／quality PASS採用既有AI controller按公開C-W卡供應合成回答，作待付費授權的P3測法；controller是AI、已見oracle、非盲，同操作者判讀非獨立人工評量，不另啟provider員工／judge模型。平台資源與App美元帳本分開揭露，不冒稱真人或全部AI運算免費。依操作設計同步品質§6及卡包v2，P6未見案例／三名真員工與人工評讀缺證保留。此补記不閉合P3-B01–04、不改OFF01–09或12／180／US$1提案，不授權任何付費，也不稱防護／P3已驗。

## 2026-09-10 P3-B01有限官方補核

[定點研究](2026-09-10-jd-natural-trial-billable-bound.md)已確認Luna input>272K長context門檻與公開費率；仍缺inline compaction整筆input/output/pass及失敗計費的明確上界契約。P3-B01維持Unknown／OPEN，停止擴大搜尋，不把context容量×最高單價稱為已證的美元硬上限；也不據此推論实际必超額。後續執行包須如實處理這個保證缺口，不能默默把硬上限改成估算。B02–04／OFF檢查尚待實作；Task5／6繼續零付費工程，沒有新授權或模型設定變更。

## 2026-09-10 Provider支出控制補核

[官方定點結果](2026-09-10-jd-natural-trial-provider-spend-controls.md)：目前有可拒絕流量的project／organization硬支出限制，不能籠統說只有提醒；但官方明示執行有延遲且可能超額，未給單批US$1零超額保證。預付與key控制亦未補足此保證。未查帳戶或修改任何限額，P3-B01不關閉；核心／guard與具體包準備後，再據真實可保證的條件取得費用授權，不默默將硬上限改成估算。
