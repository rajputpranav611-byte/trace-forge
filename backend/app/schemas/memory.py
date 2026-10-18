import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class EpistemicProvenance(BaseModel):
    source_type: str = Field(..., description="graph_node | metric_stream | runbook_rule | simulation_engine | operator_audit")
    source_id: str
    verified: bool = Field(False, description="Whether this operational knowledge has deterministic proof")
    epistemic_status: str = Field(..., description="VERIFIED_OBSERVATION | UNVERIFIED_CLAIM | SIMULATED_DRY_RUN | REJECTED_HYPOTHESIS")
    notes: Optional[str] = None


class HistoricalInvestigationRecord(BaseModel):
    investigation_id: str
    incident_id: str
    incident_title: str
    incident_severity: str
    incident_status: str
    started_at: str
    ranked_at: Optional[str] = None
    abstained: bool = False
    top_hypothesis_title: Optional[str] = None
    top_hypothesis_score: Optional[float] = None
    top_hypothesis_verdict: Optional[str] = None
    hypotheses_count: int = 0
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    verified_recovery_actions: List[Dict[str, Any]] = Field(default_factory=list)
    simulated_outcomes: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_gaps: List[str] = Field(default_factory=list)
    provenance: EpistemicProvenance


class RunbookPrerequisiteMatch(BaseModel):
    runbook_id: str
    runbook_title: str
    service_id: str
    required_step_id: str
    required_action: str
    is_satisfied: bool
    reason: str


class HistoricalComparison(BaseModel):
    historical_incident_id: str
    historical_title: str
    historical_investigation_id: Optional[str] = None
    is_relevant: bool
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    relevance_explanation: str
    common_affected_services: List[str] = Field(default_factory=list)
    evidence_similarities: List[str] = Field(default_factory=list)
    evidence_differences: List[str] = Field(default_factory=list)
    verified_recovery_outcomes: List[Dict[str, Any]] = Field(default_factory=list)
    simulated_outcomes_summary: List[Dict[str, Any]] = Field(default_factory=list)
    runbook_prerequisite_checks: List[RunbookPrerequisiteMatch] = Field(default_factory=list)
    unresolved_questions_carried_over: List[str] = Field(default_factory=list)
    epistemic_disclaimer: str = Field(
        default="Simulated dry-run successes and LLM hypotheses are historical references and NOT treated as verified real-world operational truth."
    )


class InvestigationMemoryResponse(BaseModel):
    current_incident_id: str
    current_affected_services: List[str]
    retrieved_at: str
    historical_comparisons: List[HistoricalComparison]
    total_relevant_found: int
