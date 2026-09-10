"""Explicit additive metadata setup for the isolated JD database; no model."""
import os

from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from analysis_agent.catalog import Catalog
from analysis_agent.jd_store import JdStore


def main():
    params = conninfo_to_dict(os.environ['Q019_TEST_DATABASE_URL'])
    if params.get('dbname') != 'q019_jd_app_20260910' or params.get('host') not in {'127.0.0.1', 'localhost'}:
        raise ValueError('Only the dedicated local JD database is supported')
    params.update(connect_timeout='5')
    engine = create_engine(URL.create('postgresql+psycopg'), connect_args=params, hide_parameters=True)
    try:
        catalog = Catalog(engine)
        catalog.setup()
        catalog.upgrade_document_metadata()
        JdStore(engine).setup()
        print('Isolated JD catalog metadata and storage ready; existing rows preserved.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
