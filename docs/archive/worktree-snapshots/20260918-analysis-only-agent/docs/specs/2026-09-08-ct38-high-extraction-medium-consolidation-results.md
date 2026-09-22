# CT38：high 抽取 → medium 整併與增量保留

2026-09-08 · LLM-Q019 · G5局部完成／整體G8 OPEN

**結論：本次支持「CT37候選提示＋背景B1 high，B2維持medium」繼續做產品驗證，不支持只升high就能修好，也不代表完整訪談已穩定。** 本輪只是隔離對照；沒有修改產品prompt、模型預設、工具、Memory架構或舊資料。

## 1. 沿用的決策與官方依據

- [CT38核准方向與計畫](../plans/2026-09-08-ct38-high-extraction-medium-consolidation-probe.md)是本輪唯一範圍；[CT37結果](2026-09-08-ct37-prompt-effort-comparison-results.md)保存提示差異、原失敗與medium對照，不另重做Memory架構研究。
- [OpenAI prompting／reasoning effort指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#reasoning-effort)支持先有baseline、確認成功條件，再看提高effort是否值得；[模型選擇指引](https://developers.openai.com/tracks/building-agents#how-to-choose)支持按工作難度及成本選擇。**「B1 high／B2 medium」是本案實驗映射，官方沒有保證它最佳。** 本輪2026-09-08重讀上述頁面；GPT-5.6提示頁以Sol為主，Luna效果須實測。
- 保留不確定性／來源範圍的依據沿[Codex整併提示](https://raw.githubusercontent.com/openai/codex/main/codex-rs/memories/write/templates/memories/consolidation.md)及[Anthropic減少幻覺指引](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)，詳見CT37。沒有官方資料可證明某段繁中prompt必然正確，不能把官方建議當測試結果。

## 2. 真正跑了什麼

沿現行`ExtractionWorkflow`、`ConsolidationWorkflow`、LangChain模型接點、官方Saver／Store及既有publication流程，使用InMemorySaver／InMemoryStore＋SQLite記憶型publication隔離。保留同一個獲選B1物件／checkpoint／Store，人工讀完產物後才交B2；**沒有拿另一輪重跑的medium抽取冒充high產物**。

原料是CT15最初完整8則員工／顧問訊息；再追加明確標記的2則合成澄清，共10則。未呼叫主顧問，合成澄清也不是模型自然訪談產生，故**不驗主顧問提問能力／背景觸發時機**。首次B1失敗獨立保留，沒有送進B2；最多使用已封存CT37候選，沒有第三版提示。

實際請求全部為Luna，B1 high／B2 medium、`all_turns`、4,096輸出上限、`store=false`、`truncation=disabled`。兩次B2皆保持現行提示與工具，沒有強制tool choice、額外judge、欄位或新語意驗證器。人工判讀不在產品runtime裡。

## 3. 逐段結果與限制

| 請求 | 階段 | 實際結果 |
|---|---|---|
| #1 | 現行提示＋B1 high | **未通過**。海鷗案例段保留「印象中」，權責總結卻肯定營運主管核准；總結另有員工核對附件／倉庫取件配送的角色範圍風險。只升high仍不足，保留失敗 |
| #2 | 封存候選＋B1 high | 主要檢查通過：保留核准者「印象中」，分清「客戶兩方案都拒絕沒做過」與「技師爭議還沒回答」，案例辨識／頻率／工作量／單案時程適用範圍保留 |
| #3–7 | 同一#2產物→B2 medium | 發布rev1；主要差別沒有在整併時變掉。技師爭議仍未知，退款核准者仍印象中；正文引用實際詳記 |
| #8 | 合成澄清→同候選B1 high | 記下白岩電熱水壺的技師爭議實際經驗、分工；員工核對後確認退款由營運主管核准；仍沒遇過客戶同時拒絕等待與退款 |
| #9–13 | 同一#8產物→B2 medium | 發布rev2：相應未知改為已知，退款權限只在核實後改肯定；新舊案例沒有混淆，導覽及受影響主題連到新詳記，舊資訊保留 |

具體保留：每日9:00／14:00收件、CRM同訂單同機器合併、15–25件是工作量不是考核、安全風險→承諾期限→一般先後排序、破損／缺附件／問進度仍在工作範圍、雲杉果汁機與海鷗除濕機不串案、三工作日只是單案預估、本人不能判故障或核准退款。新白岩案的售後主管決定是否重檢，與營運主管退款核准分清。

**仍有措辭瑕疵，不藏成完全通過：**#8詳記在「客戶同時不接受等待與退款」標題下寫「兩種情況都沒有實際處理經驗」，不如候選的單一情境表達清楚；下一項已明示技師爭議有經驗，最終正文也正確限定為「同時不接受等待與退款」，本次未判成原本的技師爭議無經驗錯誤。「權限更正」在此其實是核實先前印象，不是核准者換人。暫不因此增加第三版提示，留作後續長訪談觀察。

原案例候選＋high已有CT37一次及CT38一次局部正向訊號，但不是隨機化重複實驗／錯誤率統計；其他職位的長訪談效果仍未知。不能推論任何模型或prompt永不漏記。

## 4. 接線、引用與回歸證據

- 原8則、合成2則、合成抽取的前2則`CONTEXT_ONLY`均與實際wire逐字核對。提示、effort與4,096上限對上實際請求；src／tests無diff。
- B2實際`NEW_CANDIDATES`／`NEW_DETAILS`與該B1 Store產物全等；rev1正是第二次整併的基準，不是重新組一份假Memory。
- 兩次B2均5模型步／4工具：讀正文、寫正文、寫導覽、可選預檢，最後回答後由既有系統驗證／發布。這次沒有工具錯誤，**不算工具失敗重試已驗收，也未測patch介面**。
- 收件整節、未受影響的雲杉與海鷗案例行逐字保留；舊詳記未改，全部10則canonical問答逐字保留。這不是所有artifact逐一byte比對。
- 程式從正文／導覽中的詳記引用及已存詳記，沿既有source reader展開來源／context頁，逐字對照canonical訊息。**驗的是地址與原文讀取鏈路，不是LLM自己選對搜尋工具／召回率。** 沒有保存到PostgreSQL，不能宣稱跨重啟持久驗收。
- 本輪離線回歸：**118 passed in 32.66s**，exit 0；實驗前ledger effort／來源固定自查通過。封存另驗完整訊息、提示、effort、來源、版本接續、保留段落、closed與費用邊界，不增加模型呼叫。
- Newton唯讀審核CT38driver至#2截點，未發現儀表blocking finding；已確認同物件接續、框架追加ID、同帳本、輸出留存。其審核不是B2語意PASS，完整語意由主線逐段讀實際來源及產物；沒有另外派judge model。
- 同一review席另核對最終報告與封存13次結果：B2取料／寫入、rev1→rev2、引用原文、effort與費用一致，#8瑕疵已揭露，無新增重要finding；只支持按報告限定範圍封存，不授權產品升級。

## 5. 成本、封存與下一步

| 階段 | 次數 | Usage估算USD | 觀察到的模型請求耗時合計 |
|---|---:|---:|---:|
| 現行提示high失敗對照 | 1 | 0.00353130 | 32.42秒 |
| 候選high抽取 | 1 | 0.00291560 | 29.44秒 |
| 首次medium整併 | 5 | 0.00380049 | 22.47秒 |
| 澄清high抽取 | 1 | 0.00215815 | 21.17秒 |
| 增量medium整併 | 5 | 0.00452881 | 30.62秒 |

總計**13次HTTP200、US$0.01693435**，已含失敗對照；本輪沒有無usage請求，帳本占用同估算且已closed，未達20次／US$0.10護欄。估價沿[官方定價](https://developers.openai.com/api/docs/pricing)的CT37同日核對值，區分cache write／cached input／一般input／output；reasoning已在output內，不重複算。不是實際帳單，時間不含人工檢查停頓，不是整場訪談成本。

[完整證據](evidence/2026-09-08-ct38-high-extraction-medium-consolidation.json)保存13次可見輸入輸出、實際effort、prompt/schema、B1詳記／候選、B2前後正文／導覽／diff、來源展開頁、人工判讀、usage、driver及helper雜湊。SHA256：`cceb800993f7da8dd4ee911d1f1fc191d9af7a2bd48a7b9999d5ef698a1813d4`。opaque只留型別／雜湊，不留隱藏推理或憑證；driver供稽核，不是獨立可安裝的重播套件，不能重開closed帳本。

**下一唯一gate：**建議在隔離analysis-agent採用CT37候選提示，讓**背景B1抽取可單獨選high，主顧問與B2仍medium**，再接回正常訪談驗收。目前`BackgroundDispatcher`仍把同一service model交B1／B2，因此需要小幅分開模型注入，不能僅改全域provider預設；此輪未施工。不全面升級、不繼續疊警告、不改Memory分層。若實作接線遇到新的契約／成本問題才重開討論。

CT15／CT36舊Memory未修、C漏用工具與CT35額外final攔截仍PARKED；JD、production、排程時機、長訪談／主顧問品質沒有在本輪驗收。實驗成功只縮小下一步，不等於產品完成。
