# JD 按需導覽與正文讀取：設計審查稿

- 日期／階段：2026-09-24；G4 **Proposed**。Owner 已同意「導覽定位、讀正文後修改、必要時讀全稿」的效果；本稿的 wire／引用實現仍待審查，**不授權 production 施工**。
- 範圍：正式新 App 的 A 主顧問讀取 **current JD**。不改 B1／B2／C、Memory、來源 authority、JD Domain、保存／撤回、Prompt／Skills 或模型路由。
- 既有權責：[跨顧問來源與 JD 契約](2026-09-20-cross-agent-evidence-and-jd-context-contract.md)、[完整工作分析](2026-09-09-complete-work-analysis-guide.md)、[JD 寫作指南](2026-09-09-jd-field-and-writing-guide.md)、[品質驗收](2026-09-10-jd-product-quality-acceptance.md)、[ADR 0075](../adr/0075-relational-jd-authority-and-structured-editor.md)及[ADR 0077](../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)不由本稿取代。

## 1. 先定義真正問題與停止線

[2026-09-23 真實續談對照](evidence/2026-09-23-gpt6-cw-natural-trial.md)顯示：同版 `jd_read current` 三頁為 85,893 bytes；六章分讀八步為 88,650 bytes；只讀職責／任務章三步仍有 60,994 bytes。第四次同版全讀前，先前三頁已離開 A 的 request-only 視圖，故不能把它叫作模型無故重讀。當前 JD notice 有 revision／改動訊號，沒有定位六章或項目的輕量導覽。表格化同一批頁面在隔離計算可少 39.6% bytes，但未驗 provider／writer，也不減工具步數。**bytes 不是 tokens；節省不等於品質改善。**

本切片要讓模型在長訪談中知道「JD 有哪些部分、目前要讀哪個」，保留局部足夠才寫、跨案例形成穩定任務、JD 六章與 K／S 關係、手改、來源和全稿雙向核對。Q12「已提交卻在 final 說未保存」是獨立 OPEN，不以本切片結案。完整 JD、真瀏覽器與真人品質仍 OPEN。

## 2. 官方事實、共同原則、未知

查閱日：2026-09-24。以下是公開產品／API 指引，不是宣稱廠商有同一種 JD schema 或 Caliburn 的內部實現。

| 類別 | 直接依據與可用範圍 |
|---|---|
| 官方事實：OpenAI | [GPT-6 提示／Skills 指引](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)建議精簡入口、需要時再讀支援材料；[tool search](https://developers.openai.com/api/docs/guides/tools-tool-search) 的 `defer_loading` 是延後載入**工具定義**，不是 JD 資料讀取。不能推論目前 OpenRouter／LangChain 路徑能忠實使用該功能。 |
| 官方事實：Anthropic | [有效 context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)描述輕量識別與工具按需取回；[有效工具設計](https://www.anthropic.com/engineering/writing-tools-for-agents)建議聚焦回應、必要時選擇／分頁、以 trace 和實測選格式，並指出單一最佳表示不存在。 |
| 共同原則 | 導覽與正文分層、讀取聚焦於任務、工具結果保留必要身分與進度；跨廠資料支持的是這個原則，**不支持**「必須上 RAG／向量庫／新 Agent／特定短代號」。 |
| 本案取捨 | JD 是單份可編輯關聯式工作稿，非程式 repo。由 App 的 current snapshot 產生定位資訊；模型只選 App 發出的 locator。App 管 document、revision、cursor、存在性、讀取證明、交易與 receipt。 |
| 未知，必須以本機鎖定版本驗 | OpenRouter GPT-6 Luna Responses 是否完整支援 OpenAI 原生 `tool_search`／`defer_loading`；目前沒有足夠證據。此功能也不解決 JD 內容讀取，因此不作本切片依賴。鎖定 LangChain 1.4.0、langchain-openai 1.6.2、langchain-openrouter 0.2.8、LangGraph 1.2.11 的實際 request、ToolMessage 與 Saver 行為以本機測試為準。 |

## 3. 實際接點與三個選項

現行 [`JdNoticeMiddleware`](../../experiments/jd-relational-app/src/jd_relational/consultant_context.py) 每個模型請求重新組裝 notice；[`jd_read` contract](../../experiments/jd-relational-app/contracts/jd-read.schema.json) 的 model 參數是 `view`、`target_ref`、`cursor`，只接受 `current/item/section/history`；[`ReadService`](../../experiments/jd-relational-app/src/jd_relational/reads.py) 由 current snapshot 投影正文與 App-issued refs；`command_context` 只接受 `purpose=current` 的寫入目標。[`ReferenceCodec`](../../experiments/jd-relational-app/src/jd_relational/references.py) 目前沒有導覽用途。[`AiToolSession._read_base`](../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py) 驗可信 `jd_read` ToolMessage、artifact 與 revision，但目前**只證明曾有同版讀取**，尚未證明「此寫入目標的所有正文頁已在模型可見視圖讀完」。這是需要測試的精確界線，不能把概念上的 read-before-write 當成已全面強制。

| 候選 | 好處 | 在本案的問題 |
|---|---|---|
| 僅把 `current` 三頁壓成更短表示 | 不增新讀取模式 | 已見零付費 bytes 降低可能，但仍須三步、每次讀全稿；欄位／引用／writer 往返未驗。可作獨立比較，不當主方案。 |
| 每次 system notice 直接附全項目清單與目標 refs | 不增索引工具步驟 | 長 JD 時反覆佔 context；若發出現有可寫 `purpose=current` refs，導覽可能被當成已讀正文。 |
| **建議：極小章節入口＋按需輪廓＋既有聚焦正文** | notice 長度穩定；小範圍可直讀，大稿按需定位；仍能讀全稿 | 需在既有 `jd_read` 加窄的唯讀輪廓投影，驗證引用、分頁與 read-proof 邊界。先離線證明收益與安全，再決定 production diff。 |

## 4. 建議的最小資料流（待離線 gate 證實）

1. **每次模型請求**：既有 JD notice 附 current revision 與六章簡短目錄；僅給 App 發出的**導覽用途**章節 locator，不含可寫 field／container refs 或全文。沿既有 middleware 即時投影，不新增持久 map／cache。固定 Prompt／Skills 留原處，動態 JD 導覽只描述最新已保存稿，不把手改推作訪談事實。若草稿為空，原本快速讀全稿／容器的路徑仍可用。
2. **選擇範圍**：模型可以用導覽 locator 直接 `jd_read section`；任務多、整章仍太大時，候選是在**現有 `jd_read`** 增加一種唯讀 `outline` view，回傳章節→職責→任務及 K／S 的短標題／關係提示和導覽 locator。只列定位資訊，不回傳完整正文、來源背書或可寫 refs；大到必須分頁時沿現有 cursor 語意，不靜默截斷。是否採此 view，需與「直接附少量項目」在真實稿上比步數、實際 request tokens、正文覆蓋與參數複雜度。
3. **取得內容**：模型從已發出的 locator 選 `jd_read item/section`，或在全稿核對／多處衝突時用現有 `jd_read current`。App 驗 document、revision、view、target、cursor；正文結果才發出同版 `purpose=current` 的 item／field／container refs。任務、成果／要求、K／S 的現行關係與來源資訊須完整保留；不得以目錄標題冒充正文或來源。
4. **編輯**：只在相關正文完整可見、來源已按既有規則查核時用現有 JD writer。模型撰寫文案、選已發 refs／evidence keys；Runtime／Domain 負責 read proof、版本、ID、排序、原子寫入、receipt。若改到未讀的另一個目標，先讀該目標；若 JD head 已變，舊 locator 失效，取得新版導覽／正文後再判斷，不能僅替舊修改換版號。
5. **長上下文**：canonical JD／訪談、Saver 與資料庫不因 compaction 改變。導覽每次從 current head 重新投影；舊工具結果若已離開 request，模型需要細節就再按需讀，不用摘要作 read proof。未處理的當輪員工原話仍須完整可見；不把 source、Memory、Working State 當成 JD 正文。全稿品質核對保留 `current` 多頁路徑與工作↔JD 雙向檢查。

### 參數與安全的具體候選

最小改動優先沿用 `jd_read(view, target_ref, cursor)`：若加 `outline`，它使用 `target_ref=null` 與原樣回傳的 App cursor；新增 view／輪廓 record 只能從 `contracts/jd-read.schema.json` 生成，不手改 generated DTO。`item/section` 仍選 App 發的同類 locator。document／revision／offset／item ID 不給模型計算。輪廓和 notice 的 locator 可考慮在**現有 `ReferenceCodec`** 加只供讀取的 `purpose=navigation`（僅 item／section），由 `ReadService` 接受；`command_context` 仍嚴格只接受 `current`。這是 Caliburn 的權限映射，**不是** OpenAI 或 Anthropic 指定的 token 格式；不得另造 handle registry 或第二套 signer。完整正文讀取才產生現有可寫 refs。

注意：加 `outline` 不是「改一行 enum」。`ReadInput`／`ReadPage`／record union、cursor、`read_tool_definition`、`AiToolSession` 的 read binding、模型可見結果與 Saver 往返都要一起審；若這個表面比直接縮短既有結果更複雜、且無實測收益，就停下採更小方案。既有 `jd_read` 說明的「開始撰寫／過時先讀 current」與局部讀可作寫入基準的現有測試並不完全一致；實作前須在單一權威文件與工具說明中釐清，不許只改 Prompt 文字掩蓋接線差異。

## 5. 零付費驗證、完成與停止條件

- **先建立反例**：outline／notice locator 直接送 writer、跨文件／跨 revision／錯 role、偽造 cursor、缺頁、只讀其他項目、stale 後舊目標、compaction 後失去正文，各不得被誤當有效寫入依據。尤其現有 `_read_base` 的「同版任一讀取」不能冒稱「目標已完整讀取」；若需要強化，只在原 `AiToolSession`／可信 artifact／checkpoint owner 保存必要的讀取完成證明，不建第二套 validator 或資料表。
- **功能**：從六章入口定位到實際 Task，讀取該 Task 的完整正文及關聯後修改；若 `has_more=true`，須續完同一 view／target；人工改稿後使用新版；必要時 full current 仍可做全稿核對。正文、來源、K／S 和 writer 結果與原 current 投影對等；Q11 的語意來源仍須人／模型實際核對，不由合法 ref 自動通過。
- **效益**：在已保存 C-W checkpoint 的同一寫作任務，對照舊路徑的 provider 請求數、實際送出 tokens（包含 guide、工具定義、正文、compaction）、工具結果 bytes、定位錯誤、已讀覆蓋與總成本；先用零付費固定模型／transport 測試。只有無損且顯著減少重讀、未增加更正失敗或跨稿錯誤，才考慮有界真 Luna 驗收。不得用「一次 `jd_read` 變短」掩蓋多次額外模型請求。
- **回歸**：受影響 `ReadService`／references／contract codegen／`AiToolSession`／middleware／Saver、JD 人編輯與 AI 編輯同 Domain、stale／receipt／undo、compaction 後重讀；已完成且未受影響的 B1／B2／C 不重跑全套。產品品質用 Q02／Q03／Q07／Q10／Q11／Q12／Q13／Q14 分開報，不能因效率 PASS 宣稱完整專業 JD PASS。
- **停止線**：outline 無法確保模型看過目標全文、locator 會越過現有寫入檢查、模型因短目錄漏掉其他重要工作、或更省 bytes 但多步成本／品質更差；先保留現有 production 路徑，帶 trace 與最小候選回 Owner 討論。不得自動開通 OpenAI 原生 tool search、換 provider、加向量庫／新 Agent／新 DB、強制每輪讀全稿或把摘要當來源。

本稿要先審 **資料流與權責**；實作細節只在本地固定合約、分頁與可信 ToolMessage 反例通過後定版。這些 gate 前不改正式行為、不送付費模型。
