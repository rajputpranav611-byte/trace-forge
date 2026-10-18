import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from app.schemas.recovery import (
    ProposedRecoveryAction,
    CreateRecoveryProposalRequest,
    ApprovalDecisionRequest,
    ExecuteSimulationRequest,
)
from app.db.recovery import (
    create_or_get_recovery_proposal,
    record_approval_decision,
    execute_simulated_recovery,
    get_recovery_action,
    list_recovery_proposals,
)

logger = logging.getLogger("traceforge.api.recovery")
router = APIRouter(prefix="/recovery", tags=["Simulated Recovery Workflow"])


@router.post(
    "/propose",
    response_model=ProposedRecoveryAction,
    status_code=status.HTTP_201_CREATED,
    summary="Propose a safe recovery action with pre-execution policy checks",
)
def propose_recovery_action(req: CreateRecoveryProposalRequest):
    """Submits a recovery action proposal. Verifies allowlists, target service existence,

    prerequisites, and blast-radius policies before moving to AWAITING_APPROVAL.
    """
    try:
        proposal = create_or_get_recovery_proposal(req)
        return proposal
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error(f"Failed to propose recovery action: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to propose recovery action: {str(exc)}",
        )


@router.post(
    "/{action_id}/decide",
    response_model=ProposedRecoveryAction,
    summary="Record human approval or rejection for a recovery proposal",
)
def record_approval(action_id: str, req: ApprovalDecisionRequest):
    """Enforces human-in-the-loop authorization. Verifies that the proposal has not mutated

    since creation and records signed approval provenance in FalkorDB.
    """
    try:
        updated = record_approval_decision(action_id=action_id, req=req)
        return updated
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error(f"Failed to record approval for {action_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval decision failed: {str(exc)}",
        )


@router.post(
    "/{action_id}/simulate",
    response_model=ProposedRecoveryAction,
    summary="Execute safe simulated recovery action",
)
def simulate_recovery(action_id: str, req: ExecuteSimulationRequest):
    """Executes a strictly safe, dry-run simulation of an approved recovery action.

    Guarantees no real infrastructure mutation occurs and persists audit outcomes in FalkorDB.
    """
    try:
        executed = execute_simulated_recovery(action_id=action_id, req=req)
        return executed
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error(f"Failed to execute simulation for {action_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {str(exc)}",
        )


@router.get(
    "/{action_id}",
    response_model=ProposedRecoveryAction,
    summary="Inspect recovery action proposal and audit trail",
)
def get_recovery_proposal_endpoint(action_id: str):
    """Retrieves full details of a recovery proposal from FalkorDB."""
    proposal = get_recovery_action(action_id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recovery proposal '{action_id}' not found.",
        )
    return proposal


@router.get(
    "/incident/{incident_id}",
    response_model=List[ProposedRecoveryAction],
    summary="List recovery proposals for an incident",
)
def list_proposals_for_incident(incident_id: str):
    """Retrieves all recovery proposals tied to the specified incident."""
    return list_recovery_proposals(incident_id=incident_id)
