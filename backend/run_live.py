"""Launcher for the v3 live CopilotKit app.

On Windows, psycopg's async connection (used by AsyncPostgresSaver checkpointer)
cannot run on the default ProactorEventLoop — it requires the SelectorEventLoop.
The loop policy must be set BEFORE uvicorn creates the event loop, so this
launcher sets it before importing/running uvicorn.

    backend>  .venv\\Scripts\\python run_live.py            # port 8001
"""
import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn  # noqa: E402  (must import after the policy is set)

if __name__ == "__main__":
    uvicorn.run(
        "app.copilotkit_live_app:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8001")),
        log_level="info",
        reload=True,
        reload_dirs=["app"],
    )
