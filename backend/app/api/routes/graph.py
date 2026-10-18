from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.db import queries

router = APIRouter(prefix="/graph", tags=["operational-graph"])


@router.get("/incidents")
def get_incidents(
    status: Optional[str] = Query(None, description="Filter by status: active, resolved, or investigating"),
    limit: int = Query(50, ge=1, le=100),
):
    """List operational incidents and their impacted services."""
    return queries.list_incidents(status=status, limit=limit)


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    """Retrieve full incident details, affected services, and connected alerts."""
    inc = queries.get_incident_with_alerts(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return inc


@router.get("/services/{service_id}/dependencies")
def get_dependencies(
    service_id: str,
    max_depth: int = Query(3, ge=1, le=5),
):
    """Traverse upstream dependencies the service relies on."""
    return queries.traverse_dependencies(service_id, max_depth=max_depth)


@router.get("/services/{service_id}/downstream")
def get_downstream(
    service_id: str,
    max_depth: int = Query(3, ge=1, le=5),
):
    """Find downstream services affected if this service degrades (blast radius)."""
    return queries.find_downstream_dependents(service_id, max_depth=max_depth)


@router.get("/services/{service_id}/deployments")
def get_deployments(
    service_id: str,
    limit: int = Query(10, ge=1, le=50),
):
    """List recent production deployments for the specified service."""
    return queries.get_deployments_for_service(service_id, limit=limit)


@router.get("/services/{service_id}/historical-incidents")
def get_historical_incidents(service_id: str):
    """Retrieve historical incidents and their recorded recovery actions."""
    return queries.get_historical_incidents_for_service(service_id)
