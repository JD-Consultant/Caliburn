"""Application-scoped dependencies for the sole consultant API."""

from fastapi import Request

from app.adapters.langgraph.postgres import PostgresConsultantRuntime
from app.consultant.run_service import ConsultantTurnProcessor


def get_consultant_runtime(request: Request) -> PostgresConsultantRuntime:
    return request.app.state.consultant_runtime


def get_consultant_turn_processor(request: Request) -> ConsultantTurnProcessor:
    return request.app.state.consultant_turn_processor
