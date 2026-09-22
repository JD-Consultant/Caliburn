# CT50：採用已測配置與前景讀取餘裕

LLM-Q019／G7–G8，Owner 已委任可逆的 effort／工具／輸出校準；非架構改變，不接 production/JD。

## 證據與短設計

- [CT49](../specs/2026-09-09-ct49-fixed-long-interview-results.md)：固定 source `309eaf21`，11輪全職位訪談與B全部完成；空近期Context只讀回查用15模型/14工具，超過前景12/11。該讀者原設定19/18，不冒稱A預設已通過。
- 只將既有 `build_conversation`／`AnalysisService` 預設升至16模型/15工具；維持LangChain middleware、每輸入含resume共用額度、錯誤與停止機制。不是新增平行agent、無界重試或預先承諾每次用滿。
- API預設A／B2 effort改成high；B1已是high。仍允許各角色明確覆寫medium。CT49測過high／8192；輸出額度仍須顯式設定，不偷偷給必填環境參數新default。README列已測profile，不稱medium4096也已通過。
- 不改Memory prompt、路由、儲存／權威。CT49的冗餘措辭與導覽舊詳記路徑另列，不在本次中途疊prompt。

## 官方依據與本案取捨

- [LangChain Model／Tool limits](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)：官方提供可設定限制與停止行為，限制失控呼叫／成本；具體16/15是本案依實測採用，不是官方共同數字。
- [OpenAI GPT-5.6](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6)：比較成功率、完整、證據、tokens、延遲和費用；只在品質維持時把少步數視為進步。high不是所有任務普遍較佳，本案完整通過的設定先作可逆基準。

## 工作與驗證

- [x] 先以真graph／service及合成HTTP重現14工具+final被過早截斷；同時驗跑偏的第16工具不執行、不偽造完成。真composition root驗角色high預設與明確medium覆寫。
- [x] 只改3個預設入口；上述測試轉綠，564離線＋41真PG回歸通過。
- [x] CT49原DB/帳本closed不改；複製到新隔離DB做真服務續談回查，並以新預設上限做空近期context只讀回查。20請求／US$0.01970424，僅合成資料；未重跑全部11輪。
- [x] 原失敗、設定、結果、實際費用、限制與獨立review寫入[結果](../specs/2026-09-09-ct50-tested-profile-results.md)。本地commit/tag收尾；無push／merge。

退出：已測設定確實到模型、查讀可完成且超限仍正確停止。這是CT49代表性驗收的接線補驗，不宣稱跨職位／百輪成功率。
