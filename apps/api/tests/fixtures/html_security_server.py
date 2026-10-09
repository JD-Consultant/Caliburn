"""Standalone synthetic HTML served through the production security middleware; no DB."""

import json
import socket

import uvicorn
from fastapi import FastAPI
from starlette.responses import HTMLResponse

from caliburn.transport.http.security import LocalHttpSecurityMiddleware


def main() -> None:
    app = FastAPI()
    app.add_middleware(LocalHttpSecurityMiddleware)

    @app.get("/")
    def html() -> HTMLResponse:
        return HTMLResponse('<html><body><main id="protected">Synthetic HTML</main></body></html>')

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        print(json.dumps({"origin": f"http://127.0.0.1:{listener.getsockname()[1]}"}), flush=True)
        uvicorn.Server(uvicorn.Config(app, log_level="error")).run(sockets=[listener])


if __name__ == "__main__":
    main()
