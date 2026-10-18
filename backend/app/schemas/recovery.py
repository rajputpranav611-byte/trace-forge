import hashlib
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


RecoveryState = Literal[
    "PROPOSED",
    "VALIDATED",
    "AWAITING_APPROVAL",
    "APPROVED",
    "REJECTED",
    "EXECUTING_SIMULATION",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED"
]

RecoveryActionType = Literal[
    "rollback_deployment",
    "restart_service",
    "scale_replicas",
    "drain_connections",
    "toggle_circuit_breaker",
    "isolate_cluster"
]

ALLOWLISTED_ACTION_TYPES = [
    "rollback_deployment",
    "restart_service",
    "scale_replicas",
    "drain_connections",
    "toggle_circuit_breaker",
    "isolate_cluster"
]

MAX_ALLOWED_BLAST_RADIUS = 8  # Policy limit: recovery cannot disrupt more than 8 downstream services


class PolicyVerificationResult(BaseModel):
    policy_name: str
    passed: bool
    details: str


class ProposedRecoveryAction(BaseModel):
    action_id: str
    incident_id: str
    action_type: str
    target_service_id: str
    runbook_id: Optional[str] = None
    step_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    justification: str
    required_evidence_ids: List[str] = Field(default_factory=list)
    state: RecoveryState = "PROPOSED"
    proposal_hash: str = Field(..., description="Cryptographic SHA-256 fingerprint of the proposal content")
    created_at: str
    updated_at: str
    idempotency_key: str
    validation_results: List[PolicyVerificationResult] = Field(default_factory=list)
    approval_id: Optional[str] = None
    approver: Optional[str] = None
    approval_status: Optional[Literal["APPROVED", "REJECTED"]] = None
    approval_decided_at: Optional[str] = None
    approval_notes: Optional[str] = None
    simulation_executed_at: Optional[str] = None
    simulation_output: Optional[Dict[str, Any]] = None
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)


def compute_proposal_hash(
    incident_id: str,
    action_type: str,
    target_service_id: str,
    parameters: Dict[str, Any],
    justification: str,
) -> str:
    """Computes a deterministic SHA-256 hash to guarantee proposal has not changed between proposal and execution."""
    raw = f"{incident_id}:{action_type}:{target_service_id}:{sorted(parameters.items())}:{justification}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CreateRecoveryProposalRequest(BaseModel):
    incident_id: str = Field(..., description="Target incident ID, e.g. INC-2026-8821")
    action_type: str = Field(..., description="Allowlisted action type")
    target_service_id: str = Field(..., description="Target service entity ID")
    runbook_id: Optional[str] = Field(None, description="Linked runbook, e.g. RBK-PAY-01")
    step_id: Optional[str] = Field(None, description="Linked runbook step, e.g. STP-02")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters, e.g. revision=DEP-4010")
    justification: str = Field(..., min_length=5, description="Engineering rationale")
    required_evidence_ids: List[str] = Field(default_factory=list)
    idempotency_key: str = Field(..., description="Client-provided unique key to prevent duplicate submissions")


class ApprovalDecisionRequest(BaseModel):
    approver: str = Field(..., description="Authorizing engineer username or email")
    role: str = Field(..., description="Engineering role, e.g. Staff SRE, Incident Commander")
    decision: Literal["APPROVED", "REJECTED"] = Field(..., description="Decision")
    notes: str = Field(..., min_length=3, description="Audit justification for approval or rejection")
    proposal_hash: str = Field(..., description="Client submitted hash ensuring proposal has not mutated")


class ExecuteSimulationRequest(BaseModel):
    approver: str = Field(..., description="Must match the authorized approver")
    idempotency_key: str = Field(..., description="Unique execution attempt token")
    proposal_hash: str = Field(..., description="Verifies proposal integrity prior to execution")
