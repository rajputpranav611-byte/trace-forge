import logging
from fastapi import APIRouter, HTTPException, status
from app.schemas.debt import (
    EvidenceDebtReport,
    ResolveDebtRequest,
)
from app.db.debt import evaluate_evidence_debt, record_debt_resolution

logger = logging.getLogger("traceforge.api.debt")
router = APIRouter(prefix="/debt", tags=["Evidence Debt"])


@router.get(
    "/report/{incident_id}",
    response_model=EvidenceDebtReport,
    summary="Evaluate and retrieve Evidence Debt report for an incident",
)
def get_evidence_debt_report(incident_id: str):
    """Evaluates missing, stale, contradictory, or unverified operational knowledge

    limiting an incident investigation, using documented priority rules (BLOCKING > WARNING > INFORMATIONAL).
    """
    report = evaluate_evidence_debt(incident_id=incident_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found.",
        )
    return report


@router.post(
    "/resolve/{incident_id}",
    summary="Record verified resolution of an evidence debt gap in FalkorDB",
)
def resolve_evidence_debt_endpoint(incident_id: str, req: ResolveDebtRequest):
    """Persists an evidence debt resolution in FalkorDB with audit provenance and clears the gap."""
    success = record_debt_resolution(incident_id=incident_id, req=req)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record resolution for debt gap '{req.gap_id}'.",
        )
    # Return updated report
    report = evaluate_evidence_debt(incident_id=incident_id)
    return {
        "status": "resolved",
        "gap_id": req.gap_id,
        "incident_id": incident_id,
        "updated_report": report,
    }
