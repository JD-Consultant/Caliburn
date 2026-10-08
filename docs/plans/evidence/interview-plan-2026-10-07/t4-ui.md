# T4：HTTP、候選預覽與唯讀 Web 規劃筆記

日期：2026-10-07。責任依 [實作計畫](../../2026-10-07-interview-plan-implementation-and-comparison.md) T4，以及 [設計](../../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md) §5、§6.4、§6.6、§6.8、§6.9。

## 已交付效果

`GET /api/job-files/{job_file_id}/interview-plan` 只讀目前正式 frontier 採用的規劃，wire 為 `{job_file_id, plan}` 並設定 `Cache-Control: no-store`。未建立回 `null`，刻意清空保留 `""`，Markdown 與空白逐字保留。未知檔案回有型別的 404；損壞或不可讀狀態回不可用錯誤，不冒充空筆記。

`ConsultantTurn.plan_preview` 是 required nullable。active／paused 在原 status session 與原 execution scope 讀候選；終局不輸出候選。HTTP allowlist 只投影 `{plan}`，不包含 plan position／revision／operation 等內部資訊。舊 execution 沒有候選時 outer null 仍相容。

Web 使用原本 composer 驗證與輪詢的 Turn cache，沒有新增輪詢或 SSE。只有同檔案已驗證 active／paused 顯示候選；終局的當次 render 即撤下候選。正式筆記用同一 query key，依序 default cancel（revert、不 silent）、invalidate `refetchType: 'none'`、`query({...options, staleTime: 0})` 讀正式筆記。queryFn 消費 AbortSignal。相同終局觀察共用 in-flight Promise，失敗釋放標記可主動重試；GET 契約驗證成功且原 file／execution 仍受觀察才標記 confirmed。

正文只放 query cache。重讀 pending／error 保留原正式筆記並標「上一採用版，等待更新」；沒有舊 cache 時明示不可用，不顯示候選或推定空筆記。未建立、刻意清空與不可用分別呈現。區塊沿既有 SafeMarkdown，原生 details 可折疊，沒有人工編輯入口，也不宣稱訪談完成。

## Red → Green

| 行為反例 | Red 證據 | Green |
| --- | --- | --- |
| 舊 Turn wire 也必須明列 nullable preview | unit `assert 'plan_preview' in wire` 失敗，原 DTO 沒有此欄 | generated DTO 與 HTTP allowlist 接線後通過 |
| Idle 的正式筆記要有唯讀呈現 | InterviewPane 找不到 role region「訪談規劃」 | 新区塊接線後通過，Markdown／null／blank 分別測試 |
| 正式讀取 API 與型別 404 | 真 PG 既有檔案 GET 404 != 200；未知檔案 generic 404 != `job_file_not_found` | router、read workflow、bootstrap 接線後通過 |
| 終局無舊 cache 不能聲稱已有上一採用版 | 新測試發現 loading 呈現推定上一採用版 | 明示「採用版尚待確認／目前不可用」後通過 |

前期 Node subprocess／uv cache 權限、並行生成時 schema ref 尚未就位、測試呼叫把 ExecutionScope 誤傳 WriterHandle，均屬環境或測試接線問題，沒有列為產品行為 Red。最終合併 pytest 發現 unit／integration 同名 module 收集衝突；unit 改成 `test_interview_plan_http_projection.py` 後消除衝突，保留另一代理的 `test_interview_plan_projection.py`。

## 最終驗證

| 指令／範圍 | 實際結果 |
| --- | --- |
| `pnpm --filter @caliburn/frontend test` | 48 files，301 passed；25.73s |
| `pnpm --filter @caliburn/frontend lint` | exit 0 |
| `pnpm --filter @caliburn/frontend build` | TypeScript 與 Vite exit 0；既有單一 bundle 約 988 kB，保留 >500 kB 非阻擋提示 |
| 核心 UI／query／guard／新 E2E 的 `prettier --check` | 全部通過 |
| 全 Web `format:check` | 14 個既有檔案格式提示；未改寫既有工作。新核心切片格式通過 |
| HTTP/status 3 個 source 的 mypy | `Success: no issues found in 3 source files` |
| HTTP/status 與新 unit／PG test 的 Ruff | `All checks passed!` |
| `git diff --check` | exit 0；僅 Windows autocrlf 提示 |
| 真 PG：`test_interview_plan_http.py`、`test_consultant_status.py`、`test_current_consultant_turn.py`、unit `test_interview_plan_http_projection.py`、兩份 Turn contract tests | 41 passed；23.45s |
| Playwright：`test:e2e interview-plan.spec.ts` | Chromium 4 passed；11.6s |

真 PG 指令使用本次自有 `caliburn_intplan_test`，每個 fixture 建新隨機 namespace。新 HTTP 7 個 cases 包含未建立／空字串／含空白 Markdown、active／paused scope、complete 之後採用、cancelled／failed 候選不取代原採用版、另一檔案隔離，以及 no-store 與 typed 404。這些是保存与讀取資格證據，不是模型品質證據。

Vitest 包含 terminal pending/error render、同 scope 共用 fresh GET、取消初次 GET 與晚到 response、wrong-file／malformed／missing-plan 回覆拒收、重試，以及切換 file／下一輪時舊成功不能確認新 scope。末次 UI 切片為 16 cases（9 component、5 query、2 scope hook），後由全 suite 覆蓋。

Chromium 使用正式 `apps/web/dist`、本次自有 loopback `8117`、新 namespace `intplan_ui_0ce06630185743d7ae510c44af7ae370`。直接 uvicorn 入口沒有讀 `.env`，子程序移除 `OPENAI_API_KEY`，沒有外送模型請求。瀏覽器實際建立合成職務檔案並驗真 GET 的 null／no-model idle；其餘 status／plan 用 Playwright controlled transport 驗畫面、折疊、terminal 與 503 重試。terminal 回覆刻意保留 stale preview，驗 render 不採用。execution 資格與採用由上述真 PG 覆蓋；此 browser double 不代表真 provider 品質或完整 LLM 旅程。Chromium binary 153.0.8010.12 與鎖定 Playwright 1.63.0 的 browsers.json 相符。自有 Uvicorn PID 7392 已由原 exec session Ctrl+C 結束，事後查無該程序。

已檢視兩張實際 screenshot：

- [刻意清空的唯讀規劃](t4-ui-empty.png)
- [終局成功重讀的正式規劃](t4-ui-adopted.png)

## query(options) 工程裁決

鎖定 `@tanstack/query-core@5.104.0` 的 `src/queryClient.ts` 已把 `fetchQuery` 標為 deprecated，官方替代是 `query(options)`。原碼的 query 同樣 build 同 key、以 staleTime 判斷並用 query.fetch 讀取；此切片明確 staleTime 0，保留設計要求的 fresh read。cancelQueries 預設 revert；invalidateQueries `none` 不觸發額外 refetch。依原碼完成效果等價替換，由主代理同步設計／計畫，沒有 lint suppression，也沒有新刷新引擎。

來源：[QueryClient 官方參考](https://tanstack.com/query/latest/docs/reference/QueryClient)、[Query Cancellation 官方契約](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation)，並核鎖定原碼 `node_modules/.pnpm/@tanstack+query-core@5.104.0/node_modules/@tanstack/query-core/src/queryClient.ts`（cancelQueries、invalidateQueries、query、fetchQuery）。

## 範圍界線

T4 完成只證明 canonical wire、保存讀取資格、UI 選擇與刷新生命週期。規劃內容是否改善真訪談／JD 分析品質，由主代理 T5 真 API 比較另行驗證。本切片沒有 commit／push／merge，也沒有改寫其他代理或使用者的既有工作。
