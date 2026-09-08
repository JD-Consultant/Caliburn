# CT44：整併写入前核對未變子句

2026-09-09 · LLM-Q019／CT42-R01 · G7/G8隔離局部優化。

## 問題與已知證據

[CT42](../specs/2026-09-09-ct42-long-interview-results.md) medium與high皆漏「依案一次主要操作說明」，high另漏「API文件不清楚先問後端／不假定能力」；最後B1並未撤銷。兩組寫入前都看到完整33行正文，產生的write_file本身就漏，非框架截斷。寫後只讀新版不能知道舊子句被省。提高推理與單純回讀不足，**不採原high結果**。

Owner已授權局部持續優化。方法依[OpenAI GPT-5.6官方提示](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)的 Preserve factual claims／Simplify prompts／Surgical edit：先明確保留標準，修改一組指令後重走相同實例；不是全域max、不另造語意驗證器。

## 最小候選

不更换whole-write／SDK patch選擇，不變schema、資料分層、工具、模型數與引用規則。只把一般「保留未變內容」改成可執行的寫前判斷：以已讀正文為底稿，僅更新有依據的子句；整段重排時對照刪除部分，只有更正或等義去重才可移除，不能因本批沒提而刪。用既有寫入前Context即可，不另生成鏈式思考／結構欄位。

同一事實過時未知仍須清除，不因保留規則而永遠留下舊說法。這是依案例失敗校準的工作約束，不能宣稱官方保證模型每次都遵從。

## 執行邊界／暫停原因

候選SDK接線先RED，再45項整併／錯誤恢復測試GREEN，僅代表指令送達。兩次CT44付費命令均在process啟動前被工具安全審查拒絕，理由為外部API資料處理授權不足；第二次已附上本地核對：11輪全等於agent自編fixture、CT42 canonical audit為true，仍被拒。不再重試或繞道。**0次CT44付費請求**。

候選已保存於[fixture](../../experiments/analysis-agent/tests/fixtures/ct44-prewrite-candidate.json)，B2產品提示還原；不讓未真測候選成為預設。下一步需要明確允許將這批合成訪談／既有記憶送往相同OpenAI API，以Luna high完成最多24次／US$0.10的對照；不是要求改架構。取得權限後續原計畫，不重做研究。

## 驗證與停止

- [x] 先驗SDK提示RED→GREEN，不改工具schema與既有格式修復迴圈；候選還原未採用。
- [ ] 相同CT42最後B1與寫前Memory，复制Store／Saver唯讀原PG，只對照候選high；不重跑原11輪、不冒充自然訪談。
- [ ] 核對全部既有工作／兩案差異／低頻範圍，不只兩句標靶；已解未知消除，真正未知保留，引用可回查。
- [ ] 若通過，用新補充情境再驗同一寫法；沒有新資訊不造事實。若仍漏，不堆同義禁令，保留失敗再檢查編輯粒度選擇。
- [ ] 暫設最多24次／US$0.10，含局部兩案；沿真SDK、既有工具、獨立帳本，達限保留中斷。模型仍Luna，A/B1/B2預設不在結果前改。
- [ ] 更新結果、review、完整回歸與保存點；最後新的固定版長訪談才可判G8代表情境通過，不混原失敗／維護重播。

不進production／JD，不改原始訪談或直接修成理想Memory，不新增Agent、狀態、ID、validator或重試loop。保留CT41／42／43已封存證據。
