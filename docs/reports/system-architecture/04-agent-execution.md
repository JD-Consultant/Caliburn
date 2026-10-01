# 四、一次訪談如何執行

[報告目錄](README.md) · 上一章：[程式分工](03-components.md) · 下一章：[工作記憶](05-work-memory.md)

## Turn、Step 與訪談訊息

**Turn 是顧問處理一次員工輸入的完整執行；Step 是其中一次模型回應，以及該次要求的工具處理。**一個 Turn 可以有多個 Step；一次 API 成功不等於整輪完成。LangGraph 內部的節點／super-step 又是框架排程概念，不能直接拿來當訪談序號。

訪談訊息則是一則完整發話，具有說話者、原文與身分。正式序號在同一職務檔案中表示前後順序；取消的輸入不占正式序號。已接受但尚未完成的本次輸入可以支持本輪候選編輯，只有完成後才成為正式可引用的訪談。

## 一輪執行的時間順序

![圖四：A 的模型與工具往返](diagrams/04-consultant-turn.png)

圖四描述正常執行中的主要保存邊界。工具可讀取資料或修改本輪候選；圖中的保存不是把全部工作包成一個長時間資料庫交易。模型請求及工具結果往返的基本模式來自 [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)；候選、訪談正式化及完成交易則是 Caliburn 的產品設計。

開場引導本身是明確標示出處的正式訪談第一則。之後每輪開始，App 先確認執行資格與必要的歷史準備，再綁定這輪可讀的已發布 Memory。即使背景整理在 Step 中途發布新版，A 仍使用原本綁定的版本；同輪恢復也不能偷偷刷新基準。

一次模型回應可以含文字與工具要求。App 保存完整可接續結果，按順序執行允許的工具，再把各工具結果與原 `call_id` 配對加入 Context。需要更多工作便繼續請求模型，不以「出現文字」當成最後答案。

模型提供最終答覆後，還要可靠保存並完成業務提交：正式訪談、候選 JD 的採用與本輪完成資格相互一致。Graph 到達 END、UI 顯示最後一個字，或 OpenAI 回傳 `response.completed`，都不是這筆產品提交本身。

## App 實際提供什麼 Context

下列是結構示意，不是可以直接送出的 API payload，也不是承諾每次內容長度相同。

```text
固定角色指令與工具契約

接續視窗：先前原生歷史，或已採用的完整 compaction 視窗
user：App 參考資料
      工作情境導覽、工作理解導覽
      近期歷史訪談：序號、說話者、訪談原文
      必要的範圍／失敗提示
user：本次員工原始輸入

assistant 原生項目 → 工具結果 → assistant 原生項目 → …
```

App 參考資料以資料角色加入，不提高成系統指令；仍要配合工具授權與程式檢查，不能只靠訊息角色防止提示詞注入。**JD 導覽是按需工具讀取，不是每輪固定塞入整份 JD。**

近期歷史訪談的起點由本輪固定 Memory 的處理邊界決定，並保留必要前問；本次員工輸入另行提供。例如 Memory 已處理到序號 8，歷史資料通常從其後有效訊息組裝；模型需要更早原話時，以序號或範圍按需讀取，而不是讓模型猜資料庫版本。

預載不能無限擴大。基準程式已具備實際超量時的有界縮減：保留完整的近期訊息與必要語境，說明未預載範圍並允許回查；不是默默截斷一句話，也不是任意刪除原生推論歷史。容量可用不等於模型一定讀對，第七章有相應反例。

## 四種延續方式各有用途

| 機制 | 延續什麼 | 不取代什麼 |
| --- | --- | --- |
| 原生 reasoning 接續項目 | 供模型沿用先前推論的相容項目 | 可引用的訪談原文、業務結果 |
| 工具呼叫與結果 | 模型要求及實際觀察／修改結果 | 由模型自行想像的成功敘述 |
| Compaction | 壓縮後的模型接續視窗 | 正式訪談保存、Memory 來源鏈 |
| Checkpoint | 已保存的執行位置及所需 State | 外部業務交易的唯一成功判據 |

產品使用 `store=false`、不使用 `previous_response_id`，並設定 `reasoning.context="all_turns"`；需要接續的原生項目由 App 保存並以合法 input 形式送回，包括適用的 `phase` 與加密 reasoning 資料。這不表示供應商會替 App 找回未傳送的歷史，也不保證推理永遠記得所有細節。保存原件和轉為下次請求可接受格式是兩件事，不能只把 `output_text` 當作全部歷史。實際參數見 [OpenAI adapter](../../../apps/api/src/caliburn/adapters/openai_responses.py)。

## 壓縮是容量管理，不是刪掉產品事實

App 呼叫 standalone compaction，採用其完整返回視窗，而不是自行抽出一段摘要。供應商說明其返回可能包含保留項目及加密 compaction 項目；這部分不能當作普通文字任意拆寫。[OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction)

目前 A／B1／B2 在工作開始前檢查 128K 門檻；A 也能要求在下一輪開始前壓縮。完整 Step 後、下次模型請求前另有 160K 容量保險。這是產品設定，不是模型容量宣稱。不中斷尚未配對完成的工具往返，不開啟供應商自動壓縮兜底。既有長旅程已觀察 A 的自然輪前壓縮；B1／B2 的證據來自調低門檻的探針，壓縮後的批次發布仍未完成驗證，詳見[第七章](07-evaluation.md)。

工作前已採用的壓縮不包含本次輸入，因此取消這輪不必撤銷它；執行中壓縮若包含本輪內容，則不能隨取消把它帶到下一次新輸入。這個差別是安全恢復的關鍵。

## 使用者看到的是公開進度，不是內部推理

`commentary` 類訊息供 UI 呈現中間說明，完成後可在歷史中展開。它不是 reasoning 原文，也不取得正式訪談序號，不供 Memory／JD 當成員工事實。正式答覆另有完成及保存邊界；生成中的串流片段不承諾永久逐 token 恢復。

### 追到實作與證據

- Context 與容量：[執行接線](../../implementation/agent-execution.md)、[context_binding.py](../../../apps/api/src/caliburn/agents/job_consultant/context_binding.py)、[request_capacity.py](../../../apps/api/src/caliburn/agent_execution/request_capacity.py)。
- 完成交易：[consultant_completion.py](../../../apps/api/src/caliburn/workflows/consultant_completion.py)。
- 已驗與未驗：[T06](../../plans/2026-09-29-target-rebuild/evidence/t06-agent-execution.md)、[T08](../../plans/2026-09-29-target-rebuild/evidence/t08-consultant-turn.md)、[T16](../../plans/2026-09-29-target-rebuild/evidence/t16-compaction-continuity.md)。
