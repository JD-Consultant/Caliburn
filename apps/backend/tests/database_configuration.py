"""真 PostgreSQL 測試使用的明示連線設定。"""

import os

import pytest
from sqlalchemy import URL, make_url


def validated_test_database_url(raw_url: str) -> URL:
    """驗證測試資料庫目標，尚不建立 Engine 或連線。"""
    for variable in ("PGHOSTADDR", "PGSERVICE"):
        if os.environ.get(variable):
            pytest.fail(f"Integration tests require {variable} to be unset or empty")
    url = make_url(raw_url)
    if url.query:
        pytest.fail("Integration test database URL must not include query parameters")
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not (
        url.database and url.database.endswith("_test")
    ):
        pytest.fail("Integration tests require a local dedicated *_test database")
    return url
