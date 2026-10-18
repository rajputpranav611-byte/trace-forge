from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from app.schemas.ranking import RankedInvestigationResponse, ScoredHypothesis


class GraphSurgeryAction(BaseModel):
    action_type: Literal[
        "remove_dependency",
        "remove_evidence",
        "isolate_service",
        "rollback_deployment"
    ] = Field(..., description="Controlled, non-arbitrary counterfactual modification type")
    source_id: str = Field(..., description="Source entity ID, e.g. payment-core or DEP-4012")
    target_id: Optional[str] = Field(None, description="Target entity ID for relationship removal, e.g. payment-db-cluster")
    relationship_type: Optional[str] = Field("DEPENDS_ON", description="Target relationship type, e.g. DEPENDS_ON, PRODUCES_ALERT, DEPLOYED_TO")
    justification: str = Field(..., description="Engineering rationale for counterfactual test")


class CreateExperimentRequest(BaseModel):
    baseline_incident_id: str = Field(..., description="Incident to test counterfactual against, e.g. INC-2026-8821")
    experiment_name: str = Field(..., description="Human-readable title for experiment")
    actions: List[GraphSurgeryAction] = Field(..., min_length=1, max_length=5, description="Controlled graph surgery operations to apply")


class ExperimentStateSummary(BaseModel):
    experiment_id: str
    experiment_name: str
    baseline_incident_id: str
    graph_name: str
    created_at: str
    applied_actions: List[GraphSurgeryAction]
    total_nodes: int
    total_edges: int
    modified_elements: List[Dict[str, Any]] = Field(default_factory=list)


class ScoreFactorDiff(BaseModel):
    factor_name: str
    baseline_contribution: float
    experiment_contribution: float
    contribution_delta: float
    baseline_reason: str
    experiment_reason: str


class HypothesisDiff(BaseModel):
    hypothesis_id: str
    title: str
    baseline_rank: Optional[int] = None
    experiment_rank: Optional[int] = None
    baseline_score: Optional[float] = None
    experiment_score: Optional[float] = None
    score_delta: float = 0.0
    baseline_verdict: Optional[str] = None
    experiment_verdict: Optional[str] = None
    causal_path_changed: bool = False
    evidence_diff_summary: str
    score_delta_explanation: str = ""
    factor_diffs: List[ScoreFactorDiff] = Field(default_factory=list)


class BlastRadiusDiff(BaseModel):
    service_id: str
    baseline_downstream_count: int
    experiment_downstream_count: int
    severed_services: List[str] = Field(default_factory=list)
    added_services: List[str] = Field(default_factory=list)


class CounterfactualComparisonResponse(BaseModel):
    experiment_id: str
    experiment_name: str
    baseline_incident_id: str
    created_at: str
    actions_applied: List[GraphSurgeryAction]
    causal_change_explanation: str
    hypothesis_diffs: List[HypothesisDiff]
    blast_radius_diff: BlastRadiusDiff
    baseline_investigation: RankedInvestigationResponse
    experiment_investigation: RankedInvestigationResponse
    disclaimer: str = "Controlled graph counterfactual under explicit assumptions. Not a real-world causal proof."
