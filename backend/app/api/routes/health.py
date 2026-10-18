from fastapi import APIRouter, status, Response
from app.core.config import get_settings
from app.db.client import db_client
from app.schemas.health import HealthResponse, DatabaseHealthResponse, DatabaseHealthDetail

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_service_health():
    """Basic service liveness check."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        service="traceforge-backend",
        environment=settings.ENVIRONMENT,
    )


@router.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    responses={503: {"model": DatabaseHealthResponse, "description": "Database unreachable"}},
)
def get_database_health(response: Response):
    """Deep database health check querying FalkorDB via Cypher."""
    db_status = db_client.check_health()
    is_connected = db_status.get("connected", False)

    if not is_connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return DatabaseHealthResponse(
            status="unhealthy",
            details=DatabaseHealthDetail(**db_status),
        )

    return DatabaseHealthResponse(
        status="healthy",
        details=DatabaseHealthDetail(**db_status),
    )
