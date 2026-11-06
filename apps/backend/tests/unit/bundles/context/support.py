"""上下文策略測試的原生壓縮窗口，保留 user 與不透明項目。"""


def compacted_payload() -> dict[str, object]:
    return {
        "id": "cmp_offline",
        "object": "response.compaction",
        "created_at": 1793491200,
        "future_response_field": {"retained": True},
        "output": [
            {
                "id": "user_retained",
                "type": "message",
                "role": "user",
                "status": "completed",
                "content": [{"type": "input_text", "text": "保留的原話"}],
                "future_user_field": {"retained": True},
            },
            {
                "id": "cmp_item",
                "type": "compaction",
                "encrypted_content": "opaque-compacted-window",
                "future_compaction_field": ["retained"],
            },
        ],
        "usage": {
            "input_tokens": 128000,
            "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
            "output_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 128020,
        },
    }
