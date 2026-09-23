# JD 按需導覽與正文讀取：設計審查稿

- 日期／階段：2026-09-24；G4 **Proposed**。Owner 已同意「導覽定位、讀正文後修改、必要時讀全稿」的效果；2026-09-24 依 Codex／Claude Code 大型 repo 導覽方式複核後，原「固定六章入口＋outline」改列**待比較候選**，不再當作已決實作。wire／引用實現仍待審查，**不授權 production 施工**。
- 範圍：正式新 App 的 A 主顧問讀取 **current JD**。不改 B1／B2／C、Memory、來源 authority、JD Domain、保存／撤回、Prompt／Skills 或模型路由。
- 既有權責：[跨顧問來源與 JD 契約](2026-09-20-cross-agent-evidence-and-jd-context-contract.md)、[完整工作分析](2026-09-09-complete-work-analysis-guide.md)、[JD 寫作指南](2026-09-09-jd-field-and-writing-guide.md)、[品質驗收](2026-09-10-jd-product-quality-acceptance.md)、[ADR 0075](../adr/0075-relational-jd-authority-and-structured-editor.md)及[ADR 0077](../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)不由本稿取代。

## 1. 先定義真正問題與停止線

[2026-09-23 真實續談對照](evidence/2026-09-23-gpt6-cw-natural-trial.md)顯示：同版 `jd_read current` 三頁為 85,893 bytes；六章分讀八步為 88,650 bytes；只讀職責／任務章三步仍有 60,994 bytes。第四次同版全讀前，先前三頁已離開 A 的 request-only 視圖，故不能把它叫作模型無故重讀。當前 JD notice 有 revision／改動訊號，沒有定位六章或項目的輕量導覽。表格化同一批頁面在隔離計算可少 39.6% bytes，但未驗 provider／writer，也不減工具步數。**bytes 不是 tokens；節省不等於品質改善。**

本切片要讓模型在長訪談中知道「JD 有哪些部分、目前要讀哪個」，保留局部足夠才寫、跨案例形成穩定任務、JD 六章與 K／S 關係、手改、來源和全稿雙向核對。Q12「已提交卻在 final 說未保存」是獨立 OPEN，不以本切片結案。完整 JD、真瀏覽器與真人品質仍 OPEN。

## 2. 官方事實、共同原則、未知

查閱日：2026-09-24。以下是公開產品／API 指引，不是宣稱廠商有同一種 JD schema 或 Caliburn 的內部實現。

| 類別 | 直接依據與可用範圍 |
|---|---|
| 官方事實：OpenAI／Codex | [大型 codebase 使用案例](https://learn.chatgpt.com/use-cases/codebase-onboarding)要求依具體功能追請求流程、模組權責、相依及風險，再指出下一批值得讀的檔案；[OpenAI 的 Codex harness 實例](https://openai.com/index/harness-engineering/)用小型 `AGENTS.md` 作知識地圖，詳細文件留在可查的 repository，並用標準開發工具取得所需上下文；[2026-09 Codex 指引](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)再次強調精簡入口、任務相關資料漸進揭露。這些是公開案例／操作方式，**沒有公開一套 Codex 內部自動相關性排序演算法**。 |
| 官方事實：Anthropic／Claude Code | [有效 context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)明示 Claude Code 的混合做法：`CLAUDE.md` 作小型入口，以 glob／grep 即時定位並按需讀取，保留輕量 locator 而非預先塞入所有檔案；長任務的 compaction 保留決策與未完工作，淘汰冗餘舊工具結果。[工具設計](https://www.anthropic.com/engineering/writing-tools-for-agents)另強調聚焦回覆；這不是要求 Caliburn 新增同名檔案工具。 |
| 跨來源共同原則／本案推論 | **任務線索 → 找候選位置 → 讀相關正文與相鄰關係 → 修改 → 驗證影響範圍**；外部權威資料維持完整，request 只裝本次需要的內容。目錄是定位入口，不等於相關性判斷或完整性證明。這個 JD 映射是本案推論，不宣稱兩家公司公開了相同底層演算法。 |
| 本案取捨 | JD 是單份可編輯關聯式工作稿，非程式 repo。由 App 的 current snapshot 提供最新定位／讀取；模型從員工目前話題、Working State、已讀 Memory 與現行 JD 判斷候選工作，選 App 發出的 locator，再沿職責↔任務↔K／S、條件與來源補讀。App 管 document、revision、cursor、存在性、讀取證明、交易與 receipt。 |
| 未知，須離線驗 | 本案究竟只需小型目錄與現有 `item/section/current`，或還需對 current JD 作受控文字／結構查找；哪一種能少步數、少遺漏且保持 JD 品質，官方資料不能代替 C-W trace 回答。鎖定版本的 request、ToolMessage 與 Saver 行為以本機測試為準。OpenAI `tool_search/defer_loading` 只涉及工具定義，不是本題 JD 資料檢索，**移出本切片決策依據**。 |

## 3. 實際接點與三個選項

現行 [`JdNoticeMiddleware`](../../experiments/jd-relational-app/src/jd_relational/consultant_context.py) 每個模型請求重新組裝 notice；[`jd_read` contract](../../experiments/jd-relational-app/contracts/jd-read.schema.json) 的 model 參數是 `view`、`target_ref`、`cursor`，只接受 `current/item/section/history`；[`ReadService`](../../experiments/jd-relational-app/src/jd_relational/reads.py) 由 current snapshot 投影正文與 App-issued refs；`command_context` 只接受 `purpose=current` 的寫入目標。[`ReferenceCodec`](../../experiments/jd-relational-app/src/jd_relational/references.py) 目前沒有導覽用途。[`AiToolSession._read_base`](../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py) 驗可信 `jd_read` ToolMessage、artifact 與 revision，但目前**只證明曾有同版讀取**，尚未證明「此寫入目標的所有正文頁已在模型可見視圖讀完」。這是需要測試的精確界線，不能把概念上的 read-before-write 當成已全面強制。

| 候選 | 好處 | 在本案的問題 |
|---|---|---|
| 壓縮 `current` 回覆，沿現有全稿讀取 | 不增讀取模式，保留全範圍可見 | 已見 bytes 可下降，但仍可能多頁、多步；欄位／引用／writer 往返未驗。適合小稿或全面核對，不應假設長稿每次都最省。 |
| 固定章節入口＋`outline`／全項目清單 | 保留清楚的 JD 結構定位；已有效果規格 | 標題不一定能找出同一工作在別章、共用 K／S、手改與更正的影響；長清單反覆佔 context，另加唯讀 ref 與 view 可能超過收益。**先前首選降為候選**。 |
| **待優先驗證：按任務定位、逐步追關聯** | 從當輪話題／Memory／Working State 找候選 JD 位置，讀正文與相關項目；需要時擴到相鄰／全稿，貼近公開 coding-agent 工作方式 | 先用現有 `item/section/current` 比較；只有真 trace 證明模型缺乏候選定位，才考慮在既有 `jd_read` 增加窄的 current-JD 查找／輪廓能力。不能因類比 repo 就直接建向量索引、RAG 或第二套資料權威。 |

## 4. 任務驅動的資料流（待離線 gate 證實）

1. **先知道在處理什麼**：A 已有的當輪員工原話、Working State、Memory guide／已讀正文與 JD revision／變更 notice 是候選線索。模型先辨識「要補哪項工作、可能影響哪些責任／K／S／條件」，不因每輪聊天自動讀全 JD 或改 JD；若訊息不足，仍先訪談。這裡不把 Memory 摘要當成 JD 正文或原話證據。
2. **定位，不預設只看章節樹**：小稿可直接沿現有 `jd_read current`；較大稿先從最小且最新的結構入口找候選。現有 `item/section` 只有在模型已取得有效 target ref 時可用，不能假設它能從空白 request 直接找到未知任務。離線比較兩種定位資訊：既有 current 結果發出的 refs，以及從**同一 current snapshot** 投影的短標題、隸屬關係、必要的文字命中片段。後者僅在真 trace 顯示固定章節入口找不到相關內容時才值得施工；其接口可落在現有 `jd_read`，但現在不預定 `outline`、`search`、query 語法、索引或特定 token 格式。若定位不確定，向鄰近章節／全稿擴讀，不能把無命中當成 JD 無相關工作。
3. **聚焦讀取並追相依**：用現有 `jd_read item/section/current` 取得受影響正文；必要時擴讀同職責其他任務、共享 K／S、工作條件、來源與人工修改。只讀一個標題不足以決定新增、去重或修正；模型應知道哪些已讀、哪些仍只是候選。App 驗 document、revision、view、target、cursor；正文結果才發同版可寫 refs。跨案例形成穩定工作與 JD 六章關係仍沿既有分析／寫作規則，不讓目錄替模型做業務判斷。
4. **編輯與驗證**：只在相關正文完整可見、來源已按既有規則查核時用現有 JD writer。模型撰寫文案、選已發 refs／evidence keys；Runtime／Domain 負責 read proof、版本、ID、排序、原子寫入、receipt。若改到未讀的另一個目標，先讀該目標；若 JD head 已變，取新版正文再判斷。修改後核對目標及受影響關係；全面製作／收尾才做工作↔JD 全範圍雙向檢查，不能因局部命中宣稱整份完成。
5. **長上下文**：canonical JD／訪談、Saver 與資料庫不因 compaction 改變；定位資訊必須是目前 current head，不能用舊摘要替代。舊工具結果若已離開 request，模型需要細節就再按需讀，不用摘要作 read proof。未處理的當輪員工原話仍須完整可見；全稿核對保留 `current` 多頁路徑。這是**外部保存完整、模型工作記憶按需取回**，不是把 JD 壓縮成第二份權威摘要。

### 參數與安全的具體候選

目前**不固定新參數或 `purpose=navigation`**。先檢查現有 `jd_read(view, target_ref, cursor)` 及可見 refs，是否足以在保存的真實稿上完成「找候選→聚焦讀→擴讀→寫→核對」。只有反例顯示缺少定位能力，才比較最小短目錄與受控文字／結構查找；若需新增 model-facing view／record，從 `contracts/jd-read.schema.json` 生成，不手改 DTO。`item/section` 仍只選 App 發的 locator；document／revision／offset／item ID 不給模型計算。若需只讀 locator，應優先擴充**現有 `ReferenceCodec`** 且使 `command_context` 拒絕將導覽當寫入授權，不另造 handle registry 或第二套 signer；正文讀取才可產生可寫 refs。

注意：加任何 `outline`／查找 view 都不是「改一行 enum」。`ReadInput`／`ReadPage`／record union、cursor、`read_tool_definition`、`AiToolSession` 的 read binding、模型可見結果與 Saver 往返都要一起審；若新接口比現有聚焦讀更複雜而無實測收益，就不加。既有 `jd_read` 說明的「開始撰寫／過時先讀 current」與局部讀可作寫入基準的現有測試並不完全一致；實作前須在單一權威文件與工具說明中釐清，不許只改 Prompt 文字掩蓋接線差異。

## 5. 零付費驗證、完成與停止條件

- **先建立反例**：若採用新的導覽／查找 locator，直接送 writer、跨文件／跨 revision／錯 role、偽造 cursor、缺頁、只讀其他項目、stale 後舊目標、compaction 後失去正文，各不得被誤當有效寫入依據。尤其現有 `_read_base` 的「同版任一讀取」不能冒稱「目標已完整讀取」；若需要強化，只在原 `AiToolSession`／可信 artifact／checkpoint owner 保存必要的讀取完成證明，不建第二套 validator 或資料表。
- **功能**：用同一份稿模擬「已知某任務」「員工用不同詞描述舊工作」「跨兩職責的共用 K／S」「人工改動」「補充低頻工作」；確認能找到真正受影響的位置、讀完整正文及關聯後修改，也能判定需要新增而非硬併舊項。若 `has_more=true`，須續完同一 view／target；必要時 full current 仍可做全稿核對。正文、來源、K／S 和 writer 結果與原 current 投影對等；Q11 的語意來源仍須人／模型實際核對，不由合法 ref 自動通過。
- **效益**：在已保存 C-W checkpoint 的同一寫作任務，對照「現有全稿」「章節／項目聚焦」「候選定位＋擴讀」的 provider 請求數、實際送出 tokens（包含 guide、工具定義、正文、compaction）、工具結果 bytes、候選命中／漏找、關聯覆蓋、錯誤寫入與總成本；先用零付費固定資料／transport 比較能客觀比的部分。只有無損且有明確步數／成本或定位收益、未增加更正失敗或跨稿錯誤，才考慮有界真 Luna 驗收。不得用「一次 `jd_read` 變短」掩蓋多次額外模型請求，也不能用固定 mock 證明自然模型會正確選候選。
- **回歸**：受影響 `ReadService`／references／contract codegen／`AiToolSession`／middleware／Saver、JD 人編輯與 AI 編輯同 Domain、stale／receipt／undo、compaction 後重讀；已完成且未受影響的 B1／B2／C 不重跑全套。產品品質用 Q02／Q03／Q07／Q10／Q11／Q12／Q13／Q14 分開報，不能因效率 PASS 宣稱完整專業 JD PASS。
- **停止線**：候選查找／短目錄漏掉重要工作、無法確保模型看過目標全文、locator 會越過現有寫入檢查、或更省 bytes 但多步成本／品質更差；先保留現有 production 路徑，帶 trace 與最小候選回 Owner 討論。不得因大 repo 類比自動加向量庫／RAG／新 Agent／新 DB、切 OpenAI tool search、換 provider、強制每輪讀全稿或把摘要當來源。

本稿要先審 **資料流與權責**；實作細節只在本地固定合約、分頁與可信 ToolMessage 反例通過後定版。這些 gate 前不改正式行為、不送付費模型。
