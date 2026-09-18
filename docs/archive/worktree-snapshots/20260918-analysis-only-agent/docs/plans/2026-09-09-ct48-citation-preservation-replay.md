# CT48：新增詳記不應取代仍有效的舊引用

LLM-Q019／G5。Owner已授權局部同模型／prompt／額度優化；不進production/JD。只驗[CT45-Q02](../specs/2026-09-09-ct45-fixed-long-interview-results.md)尚存引用缺陷，不重新研究Memory架構。

- 使用CT45第7輪已成功B1＋第7輪寫前revision6，當時維護／估算的正確引用仍在；原PG只讀複製。重建官方InMemorySaver的已完成B1 handoff，Store中實際詳記／候選全文必須等於已記錄產物，不重新抽取，不造來源。
- 使用已測CT47的**相同**候選提示、高推理、8192輸出，16模型／15工具；無再加規則。獨立24次／US$0.15帳本，同合成資料與官方OpenAI endpoint。
- 成功須保留維護／估算的有效舊引用 `cc78445…`，新增交付依據 `4f9e69…`，不互相冒充；既有重要子句、兩案差異與未知仍正確。字串存在與format pass不等於語意通過，人工審實際before／after及摘要。
- 失敗保留、不更改原資料、不增加無關Agent／schema或自訂matcher；不能從單例宣稱穩定。結果回到CT46–48報告，下一gate才決定隔離app採用及回歸。

依據：[GPT-5.6 prompting](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)的來源grounding與tool-route局部校準；[CT47計畫](2026-09-09-ct47-edit-routing-candidate.md)已載SDK與官方patch細節。這是產品引用保留要求映射，不稱廠商規定每次保留所有歷史引用。
