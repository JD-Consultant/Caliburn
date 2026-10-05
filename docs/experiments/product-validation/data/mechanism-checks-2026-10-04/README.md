# 核心保存與恢復反例

從現行測試選取與專題報告直接相關的 13 個檔案，補跑保存、取消、來源核對、固定 Context、長文更新與定位身分的反例。**163 項通過、0 失敗、0 跳過**；[原始 JUnit](results.xml)保留每個測例名稱、時間與結果。測試不呼叫 OpenAI，也不編輯正式資料。

| 範圍 | 數量 | 測試回答的問題 |
|---|---:|---|
| 回應恢復 | 10 | 保存失敗仍承接完整原結果，晚到結果不能復活失效工作 |
| 壓縮保存及恢復 | 12 | 保存與採用邊界、完整返回視窗、重進不另行壓縮 |
| 顧問工具 | 19 | 讀差異不等於核對；非法工具與不合法保存請求被拒絕 |
| 原生保存視窗 | 5 | 完整 output items 及工具結果配對仍可取回 |
| strict 工具契約 | 33 | 封閉參數及生成格式符合契約 |
| 跨程序恢復 | 4 | 在 count 保存、response 保存、tool 提交、final 保存四邊界退出程序，重入不重複已保存工作 |
| JD 來源動作 | 5 | 精確核對／重播、錯誤整組回滾，不留下部分效果 |
| 執行准入 | 12 | 同檔案競爭者只有一個可執行、寫入資格一致 |
| 角色歷史與完成競爭 | 40 | 取消／完成競爭、準備／完成歷史及採納邊界 |
| 顧問 Context 固定 | 6 | 背景發布不換同輪基準；未預載原話仍可按需讀取 |
| 放棄歷史 | 2 | 新輸入不承接取消輪的內容，保留原輪前安全基底 |
| Memory 長文與整組修改 | 10 | 歧義拒絕整組操作、權限隔離及提交回覆遺失後重播 |
| JD 短定位 | 5 | 跨檔與刪除不轉指、並行配置及持久性 |

整合測試使用 loopback、以 `_test` 結尾的隔離 PostgreSQL，每個測例建立自己的隨機 schema，結束只清理該測例的 namespace；Memory 真模型實驗另有 schema，未被清除。程序中斷測試實際退出子程序，但 provider 回應為固定替身。通過支持系統規則與保存效果，不代表模型語意、真使用者省時或效能已達標。

程式基準為 `13c0663a7d42e2e73b5c2ef45d20faa9e1b1fa11`；同時存在 Docker 與獨立 OCS 研究的未提交工作，不將這個 HEAD 當成乾淨工作樹聲明。下面命令取自實際執行，資料庫憑證由環境指定、不寫入報告。

```powershell
uv run --project apps/api --locked pytest apps/api/tests/unit/test_response_recovery.py apps/api/tests/unit/test_context_compaction.py apps/api/tests/unit/test_consultant_tools.py apps/api/tests/unit/test_saved_context_windows.py apps/api/tests/contracts/test_tool_schema_strictness.py apps/api/tests/integration/test_consultant_process_recovery.py apps/api/tests/integration/test_jd_source_tool_actions.py apps/api/tests/integration/test_execution_admission.py apps/api/tests/integration/test_context_histories.py apps/api/tests/integration/test_consultant_context_binding.py apps/api/tests/integration/test_role_context_history.py apps/api/tests/integration/test_memory_write_tools.py apps/api/tests/integration/test_jd_short_references.py -q --junitxml=docs/experiments/product-validation/data/mechanism-checks-2026-10-04/results.xml
```

JUnit 是當次結果，不因後續改程式而改寫；新的驗證需另存檔案。模組定位與分析能力的邊界見[報告證據索引](../../2026-10-04-report-evidence-audit.md)。
