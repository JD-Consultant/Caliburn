"""沿正式 A worker，在已存 raw R 與 routing projection 之間硬退出。"""

import asyncio
import sys

from caliburn.agent_execution import native_agent
from tests.fixtures.consultant_crash_worker import run, stop_process

if __name__ == "__main__":
    boundary, *arguments = sys.argv[1:]
    if boundary == "projection":

        def stop_projection(snapshot):
            stop_process("projection")

        native_agent.project_native_response = stop_projection
    asyncio.run(run(boundary, *arguments), loop_factory=asyncio.SelectorEventLoop)
