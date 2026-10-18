from fastapi import APIRouter, HTTPException, Query, status
from typing import List
from app.schemas.memory import (
    HistoricalInvestigationRecord,
    HistoricalComparison,
    InvestigationMemoryResponse,
)
from app.db.memory import (
    list_historical_investigations,
    retrieve_and_compare_historical_memory,
)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get(
    "/investigations",
    response_model=List[HistoricalInvestigationRecord],
    summary="List historical incident investigations persisted in FalkorDB",
)
def get_historical_investigations(limit: int = Query(25, ge=1, le=100)):
    """Retrieves all previously completed investigations from FalkorDB, including

    hypotheses, ranked scores, verified real outcomes, simulated actions, and epistemic provenance.
    """
    try:
        return list_historical_investigations(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve historical investigations: {str(exc)}",
        )


@router.get(
    "/compare/{incident_id}",
    response_model=InvestigationMemoryResponse,
    summary="Retrieve and compare historical incident memory for an active incident",
)
def compare_historical_incidents(
    incident_id: str,
    max_depth: int = Query(3, ge=1, le=4),
):
    """Compares the current incident against historical investigations in FalkorDB:

    - Identifies relevant historical precedents through graph dependency relationships
    - Identifies concrete similarities and differences in evidence
    - Retrieves verified historical outcomes (strictly distinguishing real vs simulation)
    - Validates runbook prerequisites satisfaction on current incident
    - Explains why historical cases are relevant or not relevant.
    """
    try:
        return retrieve_and_compare_historical_memory(current_incident_id=incident_id, max_depth=max_depth)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare historical memory: {str(exc)}",
        )
