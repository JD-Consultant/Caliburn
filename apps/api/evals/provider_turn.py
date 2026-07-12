"""promptfoo Python provider(T11;實作驗證報告 H3a):包訪談引擎「一回合」。

- 引擎照常獨立跑(`npm run up` 起 api:8001)——provider 只打 HTTP,六邊形邊界不破。
- promptfooconfig 設 `workers: 1` 保 worker 內狀態(H3a:persistent worker;
  session 已 start 的 profile 記在 module 級,不重複 start)。
- 回傳 output = JSON 字串 {say, turn, doc, turns}——assertions/ 的確定性斷言吃這包。

config(promptfooconfig providers[].config):
    base_url:   預設 http://127.0.0.1:8001/api/v1
    profile_id: 測試 profile(或由 test vars 給 profile_id)
"""
from __future__ import annotations

import json
import urllib.request

_STARTED: set[str] = set()


def _req(method: str, url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_api(prompt: str, options: dict, context: dict) -> dict:
    cfg = (options or {}).get("config") or {}
    base = cfg.get("base_url", "http://127.0.0.1:8001/api/v1")
    pid = ((context or {}).get("vars") or {}).get("profile_id") or cfg.get("profile_id")
    if not pid:
        return {"error": "缺 profile_id(test vars 或 provider config)"}
    try:
        if pid not in _STARTED:
            _req("POST", f"{base}/job-profiles/{pid}/interview:start")
            _STARTED.add(pid)
        turn = _req("POST", f"{base}/job-profiles/{pid}/interview:turn", {"text": prompt})
        doc = _req("GET", f"{base}/job-profiles/{pid}/document")
        view = _req("GET", f"{base}/job-profiles/{pid}/interview")
        turns = {t["seq"]: t["text"] for t in view.get("turns", [])
                 if t.get("role") == "employee"}
        return {"output": json.dumps(
            {"say": turn.get("say", ""), "turn": turn,
             "doc": doc.get("content") or {}, "turns": turns}, ensure_ascii=False)}
    except Exception as exc:  # noqa: BLE001  (promptfoo 慣例:error 欄回報)
        return {"error": f"{type(exc).__name__}: {exc}"}
