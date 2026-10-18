from typing import List, Optional, Literal
from pydantic import BaseModel, Field


DebtSeverity = Literal["BLOCKING", "WARNING", "INFORMATIONAL"]
DebtCategory = Literal[
    "MISSING_DEPENDENCY_VERIFICATION",
    "UNLINKED_ALERT",
    "TIMESTAMP_ANOMALY",
    "UNVERIFIED_RESOLUTION",
    "STALE_METRIC",
    "MISSING_RUNBOOK_PREREQUISITE",
    "CONTRADICTORY_EVIDENCE",
    "INSUFFICIENT_TELEMETRY"
]


class EvidenceDebtGap(BaseModel):
    id: str = Field(..., description="Unique deterministic identifier, e.g. DEBT-MISSING-DEP-01")
    title: str = Field(..., description="Concise description of the debt gap")
    category: DebtCategory
    severity: DebtSeverity = Field(..., description="BLOCKING: Prevents automated safe action; WARNING: Limits confidence; INFORMATIONAL: Minor hygiene gap")
    affected_incident_id: str
    affected_hypotheses: List[str] = Field(default_factory=list, description="IDs of candidate hypotheses weakened or blocked by this gap")
    affected_entities: List[str] = Field(default_factory=list, description="Service, deployment, or metric IDs tied to the debt")
    why_it_matters: str = Field(..., description="Operational explanation of how this gap restricts the investigation or ranking")
    resolving_evidence: str = Field(..., description="Specific telemetry, trace span, git commit, or runbook verification needed to clear the debt")
    status: Literal["ACTIVE", "RESOLVED"] = Field("ACTIVE", description="Whether the evidence debt is unresolved or cleared")
    provenance: str = Field(..., description="FalkorDB graph relationship provenance or origin system")


class EvidenceDebtSummary(BaseModel):
    total_gaps: int
    blocking_count: int
    warning_count: int
    informational_count: int
    active_count: int
    resolved_count: int
    has_blocking_debt: bool
    priority_rule_explanation: str = Field(
        "Priority Rule: BLOCKING > WARNING > INFORMATIONAL. "
        "Gaps that sever causal paths or prevent automated rollback are classified as BLOCKING. "
        "Uncorrelated alerts and telemetry staleness are classified as WARNING. "
        "Missing runbook version metadata is INFORMATIONAL."
    )


class EvidenceDebtReport(BaseModel):
    incident_id: str
    evaluated_at: str
    summary: EvidenceDebtSummary
    gaps: List[EvidenceDebtGap]
    blocked_recovery_actions: List[str] = Field(default_factory=list)


class ResolveDebtRequest(BaseModel):
    gap_id: str = Field(..., description="ID of the evidence gap to resolve")
    resolution_evidence_id: str = Field(..., description="ID of verified evidence resolving the gap")
    notes: str = Field(..., description="Audit rationale for resolving debt")
