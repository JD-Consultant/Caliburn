"""正式 HTTP 啟動；平台相容設定集中在 Host。"""

import argparse
import sys

import uvicorn


def create_server(*, host: str = "127.0.0.1", port: int = 8101) -> uvicorn.Server:
    return uvicorn.Server(
        uvicorn.Config(
            "caliburn.host.entrypoint:create_app",
            factory=True,
            host=host,
            port=port,
            loop="asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto",
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8101)
    arguments = parser.parse_args()
    create_server(host=arguments.host, port=arguments.port).run()
