"""離線匯出正式 HTTP 契約，供前端生成使用。"""

import argparse
import asyncio
import json
from pathlib import Path

from caliburn.host.app import build_app
from caliburn.modules.occupation_reference.configuration import ReferenceConfiguration


async def export_openapi(destination: Path) -> None:
    # 僅組裝 routes，不連線資料庫，也不讀部署設定。
    app = build_app(
        database_url="postgresql+psycopg://localhost:1/openapi",
        reference_configuration=ReferenceConfiguration(collection="openapi"),
    )
    async with app.router.lifespan_context(app):
        document = app.openapi()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("output/openapi.json"))
    arguments = parser.parse_args()
    asyncio.run(export_openapi(arguments.output))


if __name__ == "__main__":
    main()
