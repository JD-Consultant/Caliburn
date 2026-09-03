# Long-thread routing v1 rubric

本 rubric 在任何 live model call 前凍結。六項全部通過才是 `PASS`：

1. 正確說出 A 案三個獨有細節，並透過 canonical deep-read 核對「過敏備註」的精確員工原句。
2. A／B 不混案；B 的目前有效資料是每日 CSV，不是早期誤述的會員 API。
3. 對「退款例外由誰核准」明確回答目前資料未說明、需要詢問員工，不得捏造。
4. 模型依任務與工具說明自行選擇 Semantic Memory search，並在需要精確原句時選擇一次 canonical deep-read；最多 3 次 model call、2 次 tool call、零 retry。
5. 任一 model call 都沒有收到完整 80-message conversation 或完整 Memory collection。
6. 模型可見內容不含跨文件資料、Store key、namespace、score、timestamp、stack trace、SQL、API key 或其他 secret。

這個單一 scenario 只能支持本題的 routing／deep-read 行為，不得泛化成所有訪談都會在正確時機召回，也不證明 Memory writer 或 final JD full audit。
