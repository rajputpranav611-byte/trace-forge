from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class RawHypothesis(BaseModel):
    id: str = Field(..., description="Unique hypothesis identifier, e.g. HYP-01")
    title: str = Field(..., description="Short title of the hypothesis")
    statement: str = Field(..., description="Causal statement explaining the anomaly/incident")
    suspected_entity: str = Field(..., description="Target service, database, or deployment ID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of alerts, metrics, deployments, or edges supporting this theory")
    contradicting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of evidence that weakens or refutes this theory")
    recommended_action: Optional[str] = Field(None, description="Suggested mitigation action from available runbooks")


class LLMHypothesisOutput(BaseModel):
    hypotheses: List[RawHypothesis] = Field(..., min_length=1, max_length=5)
    reasoning_summary: str = Field(..., description="High-level engineering triage reasoning")


class VerifiedEvidence(BaseModel):
    id: str
    type: str  # alert, metric, deployment, edge, runbook
    description: str
    is_valid: bool = True


class VerifiedHypothesis(BaseModel):
    id: str
    title: str
    statement: str
    suspected_entity: str
    confidence: float
    supporting_evidence: List[VerifiedEvidence]
    contradicting_evidence: List[VerifiedEvidence]
    rejected_evidence_ids: List[str] = Field(default_factory=list, description="Hallucinated or invalid evidence IDs rejected by the verification layer")
    recommended_action: Optional[str] = None
    verification_status: str = Field(..., description="verified | partially_verified | unverified")


class HypothesisGenerationResponse(BaseModel):
    incident_id: str
    provider: str
    model_name: str
    is_fallback: bool
    hypotheses: List[VerifiedHypothesis]
    rejected_evidence_total: int
    missing_evidence_notes: List[str] = Field(default_factory=list)
    reasoning_summary: str
    disclaimer: str = "Candidate explanations generated for engineer verification. Do not treat as proven root cause."
