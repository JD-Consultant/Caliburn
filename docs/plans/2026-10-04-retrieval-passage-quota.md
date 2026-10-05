# 各段保留候選實驗計畫

> 本輪依已同意範圍沿用 superpowers:executing-plans，由主代理在隔離實驗目錄執行；reviewer唯讀審查。沒有production改動或commit／push。

**Goal:** 比較全域前K與每段前K是否保留員工所有已標註支持主題，固定配置後以新情境驗證，保存品質與時間取捨。

**Architecture:** 805正文／既有向量與逐段rerank cache → 每段候選排序／quota或全域基線 → 同一員工的去重參考集合；新情境在development配置固定後才產生排名。

**Tech Stack:** Python既有indexer venv、NumPy、qdrant-client、httpx；Docker本機torch／transformers／RTX4060公開model cache。

**Spec:** [本輪協定](../experiments/2026-10-04-retrieval-passage-quota/protocol.md)。用途是檢索涵蓋驗收；後續另一次決策模型、主LLM及JD完成不在本輪。

## 切片

- [x] 固定18回歸情境與4個新混合情境的原話／逐項正文支持／source hash；新情境沒有embedding或排名。
- [x] `selection.py`：per-passage候選／保留quota與global基線；`test_selection.py`先以已存在global行为重現次要工作被擠掉，再Red–Green驗配額、去重、低分不絕對刪除、缺pair拒絕。
- [x] `prepare.py`：重算64主題的每段full805排名，核既有paircache；本輪需用且缺少的pair列manifest。`gpu_worker.py`只補實際缺pair、不生成標註。`analyze.py`只依18情境重算全部設定與選擇。
- [x] 固定`selection-development.json`／hash後，`run_holdout.py`產生新情境embedding及真Qdrant原生結果，worker補選定方案需要的pair，逐項保存新22支持主題的結果；不重調配置。
- [x] `benchmark.py`量本輪選定配置E01／M04及E01全805，兩次暖機；保存各階段實測與實際pair工作量。
- [x] `verify.py`獨立從保存的原生排名／pair／凍結標註重算候選、去重、主題、摘要、選擇與時間欄位；重要篡改反例Red–Green。唯讀review，報告與入口更新，停止自有研究服務並封存。

**完成證據：** [本輪報告](../experiments/2026-10-04-retrieval-passage-quota/README.md)、[最終核對](../experiments/2026-10-04-retrieval-passage-quota/verification-final.txt)、[唯讀審查](../experiments/2026-10-04-retrieval-passage-quota/review.md)。開發64/64、新合成情境22/22支持主題通過，候選N20／每段rerank K5；真實訪談、Memory切分、正式採納與JD完成仍未驗收。

## 反例焦點

晚出現且低頻的責任不能因全域quota被主工作擠掉；不同段命中同一文件仍保留段落來源；低sigmoid仍可能正確，缺分數不能當0；新holdout不能混入調參；段落內多項工作的覆蓋與分數不是職位／本人責任判定。

純來源標註、配置與模型spike不製作假Red，程式選擇／核對行為保留有意義反例。舊原件不改；無完整標註／真實員工品質gate即不正式採納。
