from fastapi import APIRouter, HTTPException, Query, status
from app.db.investigation import build_investigation_context
from app.schemas.investigation import InvestigationContextResponse
from app.schemas.hypotheses import HypothesisGenerationResponse
from app.schemas.ranking import RankedInvestigationResponse
from app.schemas.orchestration import InvestigationOrchestrationResponse
from app.core.orchestrator import orchestrator
from app.core.llm.verifier import execute_hypothesis_generation_workflow
from app.core.ranking.engine import rank_hypotheses
from app.db.persistence import persist_ranked_investigation
import uuid
import datetime

router = APIRouter(prefix="/investigation", tags=["investigation"])


@router.get(
    "/context/{incident_id}",
    response_model=InvestigationContextResponse,
    responses={
        404: {"description": "Incident not found in graph"},
        500: {"description": "Database query failure or timeout"},
    },
)
def get_investigation_context(
    incident_id: str,
    max_depth: int = Query(3, ge=1, le=4, description="Bounded traversal depth"),
):
    """Retrieves full structured operational investigation context for a given synthetic incident ID.

    Traverses affected services, upstream dependencies, alerts, metrics, candidate deployments,
    historical incident precedents, runbooks, and detects unregistered missing relationships.
    """
    try:
        context = build_investigation_context(incident_id=incident_id, max_depth=max_depth)
        if not context:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with ID '{incident_id}' not found in FalkorDB graph.",
            )
        return context
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query error during investigation traversal: {str(exc)}",
        )


@router.post(
    "/hypotheses/{incident_id}",
    response_model=HypothesisGenerationResponse,
    responses={
        404: {"description": "Incident not found in graph"},
        500: {"description": "Hypothesis generation or verification failed"},
    },
)
async def generate_incident_hypotheses(
    incident_id: str,
    max_depth: int = Query(3, ge=1, le=4),
):
    """Generates structured competing hypotheses for an incident and strictly verifies all evidence references against the graph."""
    context = build_investigation_context(incident_id=incident_id, max_depth=max_depth)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found in FalkorDB graph.",
        )

    try:
        response = await execute_hypothesis_generation_workflow(context)
        return response
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hypothesis generation failed: {str(exc)}",
        )


@router.post(
    "/rank/{incident_id}",
    response_model=RankedInvestigationResponse,
    responses={
        404: {"description": "Incident not found in graph"},
        500: {"description": "Ranking computation or persistence failed"},
    },
)
async def rank_incident_hypotheses(
    incident_id: str,
    max_depth: int = Query(3, ge=1, le=4),
):
    """Generates candidate hypotheses, applies deterministic factor scoring, ranks competitors,

    identifies contradictions and uncertainty, and persists the investigation graph in FalkorDB.
    """
    context = build_investigation_context(incident_id=incident_id, max_depth=max_depth)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID '{incident_id}' not found in FalkorDB graph.",
        )

    try:
        # 1. Generate & verify hypotheses against graph
        verified_resp = await execute_hypothesis_generation_workflow(context)

        # 2. Score and rank hypotheses deterministically
        ranked_list, abstained, unresolved = rank_hypotheses(verified_resp.hypotheses, context)

        # 3. Persist investigation & ranking relationships in FalkorDB
        investigation_id = f"INV-{incident_id}-{uuid.uuid4().hex[:6].upper()}"
        persisted = persist_ranked_investigation(
            investigation_id=investigation_id,
            incident_id=incident_id,
            scored_hypotheses=ranked_list,
            abstained=abstained,
            unresolved_questions=unresolved,
        )

        top_hyp = ranked_list[0] if ranked_list else None
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        explanation = (
            f"Deterministic ranking evaluated {len(ranked_list)} competing hypotheses. "
            f"Top candidate '{top_hyp.id if top_hyp else 'None'}' scored {top_hyp.deterministic_score if top_hyp else 0.0} ({top_hyp.verdict if top_hyp else 'None'}). "
            f"Identified {sum(len(h.contradicting_evidence_ids) for h in ranked_list)} contradicting observations."
        )

        return RankedInvestigationResponse(
            investigation_id=investigation_id,
            incident_id=incident_id,
            ranked_at=now_iso,
            abstained=abstained,
            top_hypothesis=top_hyp,
            hypotheses=ranked_list,
            unresolved_questions=unresolved,
            graph_persistence_status="persisted" if persisted else "persistence_failed",
            explanation=explanation,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hypothesis ranking failed: {str(exc)}",
        )


@router.post(
    "/orchestrate/{incident_id}",
    response_model=InvestigationOrchestrationResponse,
    summary="Execute multi-step adaptive graph investigation using MCP tools",
)
async def orchestrate_investigation(incident_id: str):
    """Executes a real adaptive graph investigation using the 5 MCP tools in sequence.

    Adapts tool selection based on discovered graph evidence and uncertainty.
    """
    try:
        res = await orchestrator.run_investigation(incident_id=incident_id)
        return res
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent investigation orchestration failed: {str(exc)}",
        )

