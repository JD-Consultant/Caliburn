# PDF 解析測試原件

本目錄從本專案既有職能基準語料選取六份原始 PDF，固定代表性表格版型。檔案以原始位元組保存，沒有重新排版或人工改寫正文；測試不連網，也不依賴本機語料目錄。這些樣本不代表整批 PDF 品質驗收。

| 檔案 | 用途 | SHA-256 |
|---|---|---|
| [AIoT應用工程師-職能基準.pdf](profile_pdfs/AIoT應用工程師-職能基準.pdf) | 職業別多行、名稱內頓號與單碼分類回歸 | `462b2f1d7a60cca993f12f7b857d0c6e29088b7eafa295b7a48c998b6f67ebad` |
| [供應鏈管理人員-職能基準.pdf](profile_pdfs/供應鏈管理人員-職能基準.pdf) | 職業別多行、名稱內頓號與單碼分類回歸 | `e57fbccb6f32fbdf3cfb54c319d8ad4486be7b7d319aa63d14937dc9391ab9cd` |
| [3D列印積層製造工程師-職能基準.pdf](sample_pdfs/3D列印積層製造工程師-職能基準.pdf) | 既有三份完整轉換／Golden 基線 | `4e5176cd0beac152f8f791b6a42c28ddc516d9d79c55e1e34b8f698e161a8c7f` |
| [3D列印設備配修人員-職能基準.pdf](sample_pdfs/3D列印設備配修人員-職能基準.pdf) | 既有三份完整轉換／Golden 基線 | `1adc394e15dd7d6d1402ed216e9e9e78b0af0428c3d3bcff3fa92a7370c86639` |
| [3D珠寶設計人員-職能基準.pdf](sample_pdfs/3D珠寶設計人員-職能基準.pdf) | 既有三份完整轉換／Golden 基線 | `61756c11f6b25410f1d031bd349485482275b732881f4fcc7bbacb6300f5b883` |
| [工具機軟體人機介面工程師-職能基準.pdf](task_pdfs/工具機軟體人機介面工程師-職能基準.pdf) | 跨頁多任務及任務名稱續段回歸 | `f856893a8c310b17749b87ed5d2cd839c3b750e8196d084fb9cf78d733cc0638` |

`golden/` 是三份 sample_pdfs 的預期完整 JSON。本輪只依 PDF 原文修正職業別分類；新增的 profile_pdfs／task_pdfs 採明確欄位斷言，避免把錯誤輸出直接生成為新標準。全部908份來源與清洗結果不屬於這些測試 fixture。
