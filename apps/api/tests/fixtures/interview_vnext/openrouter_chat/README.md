# OpenRouter Chat fixture bodies(synthetic, test-only)

- 來源:OpenRouter 官方 OpenAPI(`https://openrouter.ai/openapi.json`)、Chat Completions
  overview、Models/Endpoints API、Router Metadata 與 Response Caching 文件;
  核對日期 **2026-07-19**。
- 全部 **人工最小化、synthetic**;無真實 API key、員工內容或 hidden reasoning 原文
  (`success-with-reasoning.json` 的 reasoning 是假字串,用來驗證 redaction)。
- 檔案保持 provider wire shape;status code、`x-request-id`/`x-generation-id` headers、
  用途等 metadata 放 sidecar `manifest.json`。
- 測試一律經 `httpx.MockTransport` + adapter 的真 JSON decoder 消費這些 body;
  §10 stable error_type 矩陣與 routing 污染案例以 table-driven / in-test 變異建構,
  避免近乎重複的檔案爆量。
- **endpoints shape(2026-07-19 官方核對)**:canonical shape 是巢狀
  `endpoints: {total, available: [{provider, model, selected}]}`(`success.json`
  用這個);歷史捕獲的 flat array(如 `resolved-model-mismatch.json`)仍保留,
  `openrouter_routing.py` 的 pure normalizer 依官方 additive/permissive decode
  要求同時支援兩者,不得刪除 flat decoder。
