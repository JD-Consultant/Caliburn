"""測試資料庫設定須先拒絕可能改寫實際連線目標的參數。"""

import pytest

from tests.database_configuration import validated_test_database_url


@pytest.fixture(autouse=True)
def isolated_database_routing_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """本檔只驗合成設定，不受執行測試者的 libpq 路由環境影響。"""
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("PGSERVICE", raising=False)


@pytest.mark.parametrize(
    "query",
    [
        "host=remote.invalid&dbname=existing_data",
        "service=external",
        "application_name=workspace_tests",
    ],
)
def test_test_database_url_rejects_query_parameters(query: str) -> None:
    """外部 URL 一律不接受 query，避免 driver 覆寫已驗證的目標。"""
    with pytest.raises(pytest.fail.Exception, match="query"):
        validated_test_database_url(
            f"postgresql+psycopg://localhost/workspace_test?{query}"
        )


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_test_database_url_accepts_explicit_loopback_target(host: str) -> None:
    """明示 loopback 與專用測試資料庫的 URL 可直接交給 Engine。"""
    raw_url = f"postgresql+psycopg://{host}:5432/workspace_test"

    assert str(validated_test_database_url(raw_url)) == raw_url


@pytest.mark.parametrize(
    "raw_url",
    [
        "postgresql+psycopg://remote.invalid/workspace_test",
        "postgresql+psycopg://localhost/existing_data",
    ],
)
def test_test_database_url_rejects_unapproved_target(raw_url: str) -> None:
    """外部 host 或非測試資料庫仍須在建立連線前拒絕。"""
    with pytest.raises(pytest.fail.Exception, match="local dedicated"):
        validated_test_database_url(raw_url)


@pytest.mark.parametrize(
    ("variable", "value"),
    [("PGHOSTADDR", "192.0.2.1"), ("PGSERVICE", "synthetic_external_service")],
)
def test_test_database_url_rejects_environment_routing(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    """環境路由須先拒絕，診斷只指出變數名稱而不回顯設定值。"""
    monkeypatch.setenv(variable, value)

    with pytest.raises(pytest.fail.Exception, match=variable) as error:
        validated_test_database_url("postgresql+psycopg://localhost/workspace_test")

    assert value not in str(error.value)


def test_test_database_url_allows_empty_routing_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """空字串未指定額外路由，不阻擋明示的本機測試目標。"""
    monkeypatch.setenv("PGHOSTADDR", "")
    monkeypatch.setenv("PGSERVICE", "")
    raw_url = "postgresql+psycopg://localhost/workspace_test"

    assert str(validated_test_database_url(raw_url)) == raw_url
