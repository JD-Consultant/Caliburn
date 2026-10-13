"""離線匯出 HTTP 契約，不啟動 lifespan 或讀取環境設定。"""

import json
import sys

from caliburn.bootstrap import create_app
from caliburn.settings import Settings


def main() -> None:
    json.dump(create_app(Settings()).openapi(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
