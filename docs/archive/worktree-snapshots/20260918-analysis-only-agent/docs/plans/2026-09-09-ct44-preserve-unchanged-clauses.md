# CT44：整併写入前核對未變子句

2026-09-09 · LLM-Q019／CT42-R01 · G7/G8隔離局部優化。

**目前結論：局部採用，G8仍OPEN。**續測20次Luna high估US$0.04937714；8模型失敗保留，12模型／11工具完成並保留主要既有細節。採候選提示及B2預設12模型／12工具，不改effort預設。完整證據、官方來源及限制見[CT44結果](../specs/2026-09-09-ct44-preservation-results.md)。下方外傳拒絕／候選還原是採用前歷史，不是目前阻塞。

## 問題與已知證據

[CT42](../specs/2026-09-09-ct42-long-interview-results.md) medium與high皆漏「依案一次主要操作說明」，high另漏「API文件不清楚先問後端／不假定能力」；最後B1並未撤銷。兩組寫入前都看到完整33行正文，產生的write_file本身就漏，非框架截斷。寫後只讀新版不能知道舊子句被省。提高推理與單純回讀不足，**不採原high結果**。

Owner已授權局部持續優化。方法依[OpenAI GPT-5.6官方提示](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)的 Preserve factual claims／Simplify prompts／Surgical edit：先明確保留標準，修改一組指令後重走相同實例；不是全域max、不另造語意驗證器。

## 最小候選

不更换whole-write／SDK patch選擇，不變schema、資料分層、工具、模型數與引用規則。只把一般「保留未變內容」改成可執行的寫前判斷：以已讀正文為底稿，僅更新有依據的子句；整段重排時對照刪除部分，只有更正或等義去重才可移除，不能因本批沒提而刪。用既有寫入前Context即可，不另生成鏈式思考／結構欄位。

同一事實過時未知仍須清除，不因保留規則而永遠留下舊說法。這是依案例失敗校準的工作約束，不能宣稱官方保證模型每次都遵從。

## 執行邊界／歷史暫停與續測

**2026-09-09續測授權：**Owner回覆「同意 繼續優化」明確核准上一則所列合成CT42訪談及其Memory送往 `https://api.openai.com/v1/responses`，Luna／high，最多24次／US$0.10。僅移除外部處理阻塞，不改其他資料／模型／架構邊界；下列拒絕是已保留的歷史，不再是目前未決。先沿原候選與相同輸入驗證，不重做廣泛研究。前景12模型／11工具已由CT43採用；B2本輪維持8模型／12工具，以trace判斷是否真的碰額度。

候選SDK接線先RED，再45項整併／錯誤恢復測試GREEN，僅代表指令送達。兩次CT44付費命令均在process啟動前被工具安全審查拒絕，理由為外部API資料處理授權不足；第二次已附上本地核對：11輪全等於agent自編fixture、CT42 canonical audit為true，仍被拒。不再重試或繞道。**0次CT44付費請求**。

候選已保存於[fixture](../../experiments/analysis-agent/tests/fixtures/ct44-prewrite-candidate.json)，B2產品提示還原；不讓未真測候選成為預設。下一步需要明確允許將這批合成訪談／既有記憶送往相同OpenAI API，以Luna high完成最多24次／US$0.10的對照；不是要求改架構。取得權限後續原計畫，不重做研究。

## 驗證與停止

第一個候選high對照8模型／8工具後觸發ModelCallLimit（最後一次為validate_memory，尚無final／publication），估US$0.01701013；failed staging仍可能漏初次操作說明，不能只升額度就宣稱語意通過。下一個局部對照僅測試8→12模型，工具仍12、提示／來源不變，從相同基準另開複本，總24次／US$0.10不追加；原失敗保留。依既有LangChain call-limit configuration，不清零原job計數，不改產品預設。

- [x] SDK提示RED→GREEN；後續真測支持局部採用，不改工具schema與既有格式修復迴圈。
- [x] 相同CT42最後B1與寫前Memory，複製Store／Saver唯讀原PG，對照候選high；不重跑原11輪、不冒充自然訪談。
- [x] 核對全部既有工作／兩案差異／低頻範圍，不只兩句標靶；已解未知更新，真正未知保留，引用有實際地址。Minor泛稱「其他專案」保留於結果，不藏起來。
- [ ] 下一gate：新補充／明確撤銷情境及固定版長訪談；沒有新資訊不造事實。本次剩餘4請求不足完整驗收，不為用完額度而做半套。
- [x] 最多24次／US$0.10內，20次估US$0.04937714，帳本closed；沿真SDK、既有工具，原失敗保留。只有high語意真測，effort預設不變。
- [x] 收尾：結果、獨立review無新增Critical／Important、558離線＋41真PG回歸通過，本地保存點 `analysis-agent-ct44-consolidation-20260909`；只有新固定版長訪談才可判G8代表情境通過，不混原失敗／維護重播。

不進production／JD，不改原始訪談或直接修成理想Memory，不新增Agent、狀態、ID、validator或重試loop。保留CT41／42／43已封存證據。
