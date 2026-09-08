# CT50：已測配置與前景額度接線

2026-09-09 · LLM-Q019 · **局部採用，限定驗收完成**。不是新的一整場訪談，也不是production／JD實作。

## 為什麼改

[CT49完整結果](2026-09-09-ct49-fixed-long-interview-results.md)在固定309eaf21完成11輪與三層記憶；清空近期對話的深入回查15模型／14工具，比A12/11多。該probe本來19/18，不能冒稱A預設通過；因此補[CT50計畫](../plans/2026-09-09-ct50-tested-profile-and-foreground-budget.md)。Owner已委任同模型effort／上限局部优化，不再重開框架或Memory架構。

## 採用與不變

- 前景 `build_conversation`、`AnalysisService` 預設16模型／15工具；B2已是16／15，這次不再提高。依既有LangChain middleware計數及停止，同一輸入續跑不重置額度，新輸入才換額度。
- API的A／B2預設改high，B1維持high。可明確各自覆寫medium，並非所有場景high一定最好。沿同一Luna／client／budgethook／all_turns；沒有新增Agent、工具、schema或外層重試。
- 輸出仍必填顯式配置；**已測profile為8192、native compaction12000**。README說明這是本案實測，不是官方通用預設。沒有把8192寫成隱含default，也不修改使用者金鑰。
- 不改任何Memory prompt、既有Memory或JD。CT49原DB／closed帳本不動，新DB由CT49完整複製、開場snapshot完全相等。

## 官方依據，不混同本案數字

1. [LangChain Model／Tool Call Limit](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)，2026-09-09重新核對官方全文相關段落：提供可設定的模型、工具呼叫限制及超限處理；是上限，不要求每輪用滿。16/15是本案依實測的可逆容量選擇，不是大廠共識的精確數字。
2. [OpenAI GPT-5.6指引](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6)：按成功、完整、證據、tokens、延遲、費用比較，少步數只有品質仍符合時才有價值。CT46已證明只升xhigh不能解編輯問題；本次採用已通過完整情境的high，不再盲升max。

## 實際結果

[完整帳本、工具trace、來源audit及可重現腳本](evidence/2026-09-09-ct50-tested-profile.json)。40次／US$0.15新護欄，實際 **20次／US$0.01970424**，帳本closed；含所有本次生成，usage估算不是帳單。

| 測法 | 結果 |
|---|---|
| CT49複製後，用真FastAPI入口續談回查 | 9模型／8工具，completed，背景idle |
| 空近期Context、只讀reader使用新預設16/15（非舊19/18） | 11模型／10工具，completed |
| 回答品質 | 候補名單未開發、兩案原因／責任／驗收差異、雲岸鍵盤檢查、每兩週週五且所有專案、每日分流、原句均正確 |
| 記憶與原文 | 兩次皆沒有改Memory；原CT49 PG與帳本未變；新舊完整可見問答相等；3個實際read_conversation返回頁逐段等於canonical原文 |
| 模型接線 | 全20次實際請求high＋all_turns；sourcehash全程不變 |

正常A有先前對話，reader無；reader的短instructions仍與A不同，不能只用它代表真正服務。這次两條都做，不將9/8、11/10的隨機差異歸因於提高上限，因兩者本身都低於舊12。

## 測試、review與原失敗

- TDD：先新增真graph14讀取＋final、超限不偽裝完成、service預設接線及high／medium override，舊src得到**5個預期失敗／2通過**；改3個預設入口後75項針對測試通過。
- 首次受限Windows暫存ACL失敗不算RED證据；換新專用目錄及核准執行後才取得上述預期斷言失敗，未清除舊資料。
- 完整suite先發現CT43測試仍寫死12/11，已改成以service真預設完成14次讀取+final，而非單測常數。最後 **564離線通過／41真PG測試在離線run skip**。
- 真PG先有3個舊medium預期失敗，更新新預設並清除測試環境effort干擾；**最終41真PG通過**。輸出／context／timeout／native計數斷言都保留，未放寬為任意值。
- 唯一warning為Starlette依賴的AnyIO棄用別名，非模型或資料失敗；不為此次配置變更順帶升級框架。
- 獨立review CT50-R01（上述寫死12/11）已CLOSED，無未處理Critical／Important code/test finding。語意與逐字audit由主agent另外執行，不假稱reviewer重跑生成。

## 結論／後續邊界

CT49＋CT50共 **135次／US$0.16871788**。可把隔離分析版以此profile交付試用；不再因同一能力重跑全部舊實驗。這是代表性全職位訪談＋引用回查成立，不宣稱所有職位、百輪或所有模型皆100%正確。

CT49的Minor仍按原報告保留：導覽繞路、重複段落、主體與代詞措辭，以及兩次修補的長延遲。若進一步優化，針對這些實測問題做局部對照，不無限加cap、不重設Memory分層；重大流程更動才回Owner討論。不merge／push、不做JD。
