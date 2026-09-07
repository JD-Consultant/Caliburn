# CT-05：增量整併與正常訪談品質

2026-09-07 · LLM-Q019／CT04-Q01 · G5/G7 isolated · 局部回歸通過；追加發布驗收未完成，付費已停止

入口：[current decisions](../../../../docs/current-decisions.md)；前次完整事實與實驗：[CT-04](2026-09-07-api-memory-interview-validation.md)。本頁只持有新假設／核准／新結果，舊證據不改寫。

## 本輪唯一問題

背景整併已讀到正確舊正文，工具也精確套用模型指定內容，但模型重寫句子時省略了仍成立的資訊。不是 PostgreSQL 漏存、工具說明未接到或同時寫入覆蓋。剩餘問題是模型的內容取捨；不能宣稱已知道其內部推理原因。

**假設：**原 B2 任務提示沒有明確區分初次建立與增量整理、沒有「更新後仍涵蓋舊的有效內容」的完成標準；只補 tool description 不足。用最小任務提示修正測此假設，不追加模型審核者、欄位、validator 或新儲存機制。

Owner 已核准本輪局部調整與小測：Luna／medium，最多24次請求／US$0.10，包含背景與重試；不接JD、Web或production。前次兩個帳本保持關閉，本次另立帳本。若語意仍失敗，先保存原因，不在同一輪無限堆提示／測試。

## 直接來源與設計邊界

- [OpenAI Codex consolidation 原始提示](https://raw.githubusercontent.com/openai/codex/main/codex-rs/memories/write/templates/memories/consolidation.md)：明確區分 INIT／INCREMENTAL，既有知識是輸入；增量處理保留仍受支持的内容，既有片段仍正確時減少重寫。學習此目的，不複製 coding 專用 schema、跨 thread 或其淘汰政策。
- [GPT-5.6 family prompting guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)：把成果、必須保留的事實與完成條件寫清楚；遇退化先找真實 traces，以小範圍提示改動再試，不同時換模型、努力程度或重寫整個 prompt stack。本案保留 Luna／medium；不以官方其他模型的成效數字宣稱本案成效。
- [OpenAI instructions／roles](https://developers.openai.com/api/docs/guides/prompt-engineering#message-roles-and-instruction-following)：應用的任務規則應放在對應 instructions／system/developer 訊息；資料仍是資料。本案沿用 LangChain `create_agent(system_prompt=INSTRUCTIONS)`，不改訊息 authority。
- [Anthropic memory prompting guidance](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance)：模型仍整理不佳時，可在提示補足記憶維護要求。其精確替換工具只保障操作契約，不能保證不漏語意。

來源於2026-09-07核對；以上是公開機制／指引。具體三行繁中增量提示是本案映射，不稱為大廠逐字共識或一定有效。

## 最小改動與驗證順序

僅修改 B2 `INSTRUCTIONS`：非空正文是累積理解、候選是增量；局部更正保留同段未變事實；結束前核對受影響內容，不新增工具呼叫。保持既有框架、讀取、C、B1、格式檢查與產品上限。

1. 先以 CT-04 真模型的 B2 替換內容重現「主管原有查看範圍消失」FAIL；不是以 prompt 字串斷言冒充效果測試。
2. 重用同一 Memory fixture 與先前真正產生的 B1 結果，跑真 B2 至發布。只核對增量保存，不花費重抽同批。未通過即停、不宣稱全流程改善。
3. 若通過，再从實際 API 入口做自然訪談：新增案例、補充、更正、背景整理、重開與回查；保留預設背景分工，判斷已知／未知及案例責任是否正確。依實際呼叫耗用決定可完成幾輪，不縮小產品能力來符合測試額度。
4. 跑既有回歸與獨立 review。只以實際完成範圍報告，不宣稱此小測保證所有長訪談品質或真正觸發 compaction。

## 結果：分開回答「有沒有回答正確」與「有沒有寫進 Memory」

[完整實驗證據](evidence/2026-09-07-incremental-memory-quality-calibration.json)保存請求／工具契約、結果、實際正文、詳記／原文回查、使用量與診斷程式。以下是觀察，不把單一樣本當模型品質保證。

| 階段 | 真模型請求 | 實際結果與界線 |
|---|---:|---|
| 同一舊問題的 B2 回歸 | 1–6 | **PASS，發布 revision 2**。客服查看全公司但不能匯出、主管查看全部且可匯出；A案、驗收角色、未更正的舊內容及引用均保留。重用先前真 B1，不代表此次重新驗 B1。模型另讀回並修掉自己多打的句點，未追加另一位審核模型。 |
| 自然新增 C 案 | 7–16 | 預設 API factory／scheduler：A 4次、B1 1次、B2 5次。按需讀2份分析Skill、通知整理、回答追問，背景發布 revision 3；加入旅宿案例時仍保留 A/B 舊內容。 |
| 員工更正 C 案 | 17 | **回答採用新條件**：只有週五至少兩晚，平日可一晚；保留逾時／分工，詢問規則由前端或後端處理。沒有呼叫 C 或通知 B，因此當下 Memory 仍 revision 3，不能稱更正已寫入長期記憶。 |
| 關閉／重開後回顧 | 18 | API 完成，回答保留 A/B/C 差異、更正與未知，歸納共同前端工作而非三個固定職位。4個先前 reasoning 指紋實際重播。近期原始對話仍在，**不是 Memory-only 或 compaction 後的證明**。 |
| 已累積更正的背景補驗 | 19–24 | **未完成發布**。測試程式明確提交尚未處理的範圍給既有 B1/B2，並非主顧問自然通知，也不是產品新增手動整理功能。B1已保存更正詳記／候選；B2因 old_string 多複製兩個空白而 exact edit 失敗一次，既有工具回錯後模型改用小片段成功修正，再補引用／導覽。第25次生成被同帳本上限攔住，最後程式驗證／發布未執行；current head仍revision 3。不能假設再一次就必定通過。 |

**費用與成本：**本輪單一帳本共24次 Luna／medium，usage估 US$0.02051763（包含背景；定價依證據內連結與算式，不是帳單）。前18次估US$0.01450390，最後6次估US$0.00601373；沒有重置24次／US$0.10上限。這是測試上限，非產品終身／固定每輪限制；HTTP24次均成功，額度攔截在第25次送出前。主訪談三輪各4／1／1次生成，其餘18次為本輪不同背景驗證；不可拿24次當一般單輪訪談成本。

## 來源、機械安全網與獨立審核

- 最新已發布正文中的5份詳記，全部實際回查其完整可見問答範圍；另1份尚待B2完成的更正詳記也可回查。原fixture16則訊息逐字不變。引用是有界輸入範圍，不冒充每句內容都經語意核實。
- 追加B1區分「員工更正」與「顧問回顧」，沒有把第18次AI回顧當成員工重新確認A/B的事實。它仍使用周邊對話理解回答，不將 context-only 的重述冒充新來源。
- 原問題用 CT04 真模型輸出重現FAIL，再以 CT05已發布結果驗PASS；案例斷言僅是實驗觀察，不變成產品專用欄位或語意verifier。
- 完整離線測試：**547 passed／0 skipped，108.66秒**，包含PostgreSQL；1項既有Starlette／AnyIO deprecation warning。純讀取封存工具曾把自身的安全檢查字串誤判，改成檢查真credential與金鑰形狀後通過；零追加模型請求、不是產品錯誤。
- 獨立review無Critical／新增Important／必改Minor；以模擬HTTP驗證初次與工具後兩筆實際框架請求，唯一system訊息完整含新提示。內容是否可靠仍由本次樣本與後續驗收裁定，review不替代語意判斷。

## Closure／下一 gate

**CT04-Q01：原B2省略主管查看範圍的重現案例已修復並發布，限定樣本PASS。**三行提示未更動ABC、schema、runtime、儲存、上限、Skill或C工具；可作隔離版局部保存點，不推翻production ADR。

**CT05-Q01／OPEN（尚待驗收，不是已證實產品發布故障）：**最後追加的C更正背景作業因實驗上限停在`consolidate`，B1产物及待執行checkpoint已保存，current revision3未改。下一步先沿這份證據檢查既有恢復點，再在新核准小額範圍接續該作業；不得重新抽取同批、重跑整組訪談或假設直接略過模型就能發布。也不趁此改成每輪強制整併。

**非阻塞品質觀察（先記錄，不本輪堆提示）：**C案首次回覆用「因入住至少兩晚」連到API逾時，語句暗示了來源未支持的因果；保存正文沒有該因果。新版小導覽把C待問事項指向「已更正／未知」，實際內容在「案例差異」，路由可再校準。這些代表尚不能宣稱零幻覺／所有品質問題已解決。

仍未驗：長訪談真正觸發native compaction、更多工作領域的語意可靠度、CT03精準原句多帶下一段的minor、WebUI與JD功能。重開條件：同類更正再次漏掉未變工作資訊，或真實訪談出現品質退化；不因另一個名詞重選Memory架構。未merge/push，不接production。
