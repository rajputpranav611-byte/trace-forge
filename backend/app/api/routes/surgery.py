import logging
from fastapi import APIRouter, HTTPException, status
from app.schemas.surgery import (
    CreateExperimentRequest,
    ExperimentStateSummary,
    CounterfactualComparisonResponse,
)
from app.db.surgery import (
    create_isolated_experiment,
    cleanup_experiment,
    execute_counterfactual_comparison,
)

logger = logging.getLogger("traceforge.api.surgery")
router = APIRouter(prefix="/surgery", tags=["Graph Surgery"])


@router.post(
    "/experiments",
    response_model=ExperimentStateSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create isolated experiment graph from baseline with surgical alterations",
)
def create_experiment_endpoint(req: CreateExperimentRequest):
    """Creates a byte-for-byte FalkorDB clone of the baseline graph and applies controlled,

    parameterized graph surgery operations without touching historical memory.
    """
    try:
        summary = create_isolated_experiment(req)
        return summary
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error(f"Failed to create experiment graph: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create experiment graph: {str(exc)}",
        )


@router.post(
    "/simulate",
    response_model=CounterfactualComparisonResponse,
    summary="Simulate counterfactual incident investigation on isolated graph",
)
async def simulate_counterfactual_endpoint(req: CreateExperimentRequest):
    """Executes the full real investigation pipeline against both baseline and genuinely modified

    FalkorDB experiment graph, comparing hypothesis rankings, scores, evidence, blast radius, and recovery actions.
    """
    try:
        comparison = await execute_counterfactual_comparison(req)
        return comparison
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.error(f"Counterfactual simulation failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Counterfactual simulation failed: {str(exc)}",
        )


@router.delete(
    "/experiments/{experiment_id}",
    summary="Clean up and delete isolated experiment graph",
)
def delete_experiment_endpoint(experiment_id: str):
    """Deletes an isolated experiment graph from FalkorDB. Guardrails ensure baseline is never deleted."""
    try:
        success = cleanup_experiment(experiment_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Experiment graph '{experiment_id}' could not be deleted or does not exist.",
            )
        return {"status": "deleted", "experiment_id": experiment_id}
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(val_err),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting experiment: {str(exc)}",
        )
