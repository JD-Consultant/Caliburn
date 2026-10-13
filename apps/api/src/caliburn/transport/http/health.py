"""Process liveness, deliberately separate from database/model readiness."""

from fastapi import APIRouter

from caliburn.transport.http.models.consultant import HealthStatus

router = APIRouter()


@router.get("/api/health", response_model=HealthStatus, tags=["health"], operation_id="read_health")
def read_health() -> HealthStatus:
    return HealthStatus(status="ok")
