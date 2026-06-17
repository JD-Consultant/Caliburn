"""獨立的 v3 CopilotKit demo app（stub-first）。不動既有 main.py / 舊 graph。
跑：uvicorn app.copilotkit_app:app --port 8000"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ag_ui_langgraph import add_langgraph_fastapi_endpoint

from app.graph_v3.serving import build_demo_agent

app = FastAPI(title="jobintel v3 CopilotKit demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

add_langgraph_fastapi_endpoint(app, build_demo_agent(), "/copilotkit")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
