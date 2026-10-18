from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ScoreFactor(BaseModel):
    name: str = Field(..., description="Factor identifier, e.g. supporting_evidence, contradiction, temporal")
    contribution: float = Field(..., description="Numerical score adjustment, positive or negative")
    reason: str = Field(..., description="Human-readable explanation of why this factor was applied")


class ScoredHypothesis(BaseModel):
    rank: int = Field(..., description="Ordinal rank (1 being most plausible)")
    id: str
    title: str
    statement: str
    suspected_entity: str
    raw_confidence: float = Field(..., description="Original model-generated claim score")
    deterministic_score: float = Field(..., ge=0.0, le=1.0, description="Independently computed score")
    verdict: str = Field(..., description="HIGH_CONFIDENCE_ROOT_CAUSE | PLAUSIBLE_CONTRIBUTOR | WEAK_OR_MISLEADING | INCONCLUSIVE_INSUFFICIENT_DATA")
    score_factors: List[ScoreFactor] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    rejected_evidence_ids: List[str] = Field(default_factory=list)
    causal_path_found: bool = False
    causal_path: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None


class RankedInvestigationResponse(BaseModel):
    investigation_id: str
    incident_id: str
    ranked_at: str
    abstained: bool = Field(False, description="True if evidence was too sparse to form a conclusion")
    top_hypothesis: Optional[ScoredHypothesis] = None
    hypotheses: List[ScoredHypothesis]
    unresolved_questions: List[str] = Field(default_factory=list)
    graph_persistence_status: str = Field("persisted", description="persisted | error")
    explanation: str
