"""由顯式連線設定建立 PostgreSQL 資源，不執行 schema 變更。"""

from sqlalchemy import URL, Engine, create_engine, make_url
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(url: str | URL) -> Engine:
    """只接受明示的 psycopg URL；連線與 schema 操作留待呼叫者執行。"""
    database_url = make_url(url)
    if database_url.drivername != "postgresql+psycopg":
        raise ValueError("資料庫 URL 必須使用 postgresql+psycopg")
    return create_engine(database_url, pool_pre_ping=True, hide_parameters=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """每次建立獨立 Session，關閉後不能再次取得資料庫資源。"""
    return sessionmaker(engine, close_resets_only=False)
