"""Process liveness, deliberately separate from database/model readiness."""

from fastapi import APIRouter

from caliburn.contracts.generated.health_status import HealthStatus

router = APIRouter()


@router.get("/api/health", response_model=HealthStatus, tags=["health"])
def read_health() -> HealthStatus:
    return HealthStatus(status="ok")
