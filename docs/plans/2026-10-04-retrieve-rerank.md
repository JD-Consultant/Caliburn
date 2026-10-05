# 廣蒐＋精搜隔離實驗計畫

**Goal:** 找到在本輪員工工作主題覆蓋下，資料量與計算時間較低的候選參數；保留反例及全部結果。

**Architecture:** 實驗目錄使用前輪封存資料、離線 exact dense 與本機 GPU cross-encoder。所有改動限研究原件及入口文件，沒有 production 接線。

**Spec:** [實驗協定](../experiments/2026-10-04-retrieve-rerank/protocol.md)。使用者已授權測試及參數比較，直接在本輪完成，不另作產品審批或 commit。

## 切片與驗收

- [x] 固定工作主題標註、混合情境及來源 hashes；核對正文支持，區分已觀察 regression 與新情境 holdout。
- [x] 本機模型 spike：revision／權重、無截斷長度契約、GPU與 FP16；下載／冷啟動分開記錄。
- [x] 寫實驗評分測試：多主題含次要工作、候選／分数过滤造成漏失、空候選、不同 score 尺度、超長分窗完整性。以 Red–Green 完成實驗計算，保存 test evidence。
- [x] 實跑廣蒐與 rerank 參數 sweep，未 rerank 基線並列；固定 development 選參數後讀新 holdout，不重新調整它。
- [x] 全量與候選 rerank 計時、保存每個輸入／候選／分數／被排除主題／時間，審查結果与封存 hashes；報告品質與時間的實際取捨，更新入口。

實驗程式分為 `download_model.py`（機制 spike）、`evaluate.py`（覆蓋／門檻／選參數）、`run.py`（資料準備／結果保存）、`gpu_worker.py`（GPU 推論與計時）；測試 `test_evaluate.py`。模型／配置與生成物依開發規範不製作假 Red，純文件只查差異與連結。

## 特別核對

主職位有找到但次要工作被刪掉；負向／未來工作不能變成正向真值；不同查詢／模型的分數不能混用；長文件不能靜默截斷；cache 計時不能當 cold-start／真負載。舊資料作回歸，新情境只有固定選參數後一次評估；無真實員工 gate 就不正式採納。

## 實測狀態

整體表示無設定通過開發支持主題覆蓋；追加各段原話表示，開發選N200／cosine0.65／K20／無sigmoid門檻，開發10/10正例完整，保留情境只有1/2。M04盤點第12名／cosine0.63576被初搜門檻刪掉。此為實驗完成但涵蓋驗收未過，不以降低門檻重作保留情境驗收。結果、時間界線與下一輪要求見[完整原件](../experiments/2026-10-04-retrieve-rerank/README.md)。

10個反例測試、兩份逐筆audit及86份本輪封存檔案hash核對通過；獨立審查无未解除Critical／Important。自有研究服務已停。此計畫的實驗工作完成，並不等於檢索涵蓋驗收完成或授權接入產品。
