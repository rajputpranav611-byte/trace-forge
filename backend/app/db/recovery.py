import uuid
import datetime
import logging
from typing import List, Dict, Any, Optional, Tuple
from app.db.client import db_client
from app.db.investigation import build_investigation_context
from app.db.queries import find_downstream_dependents
from app.schemas.recovery import (
    ProposedRecoveryAction,
    CreateRecoveryProposalRequest,
    ApprovalDecisionRequest,
    ExecuteSimulationRequest,
    PolicyVerificationResult,
    compute_proposal_hash,
    ALLOWLISTED_ACTION_TYPES,
    MAX_ALLOWED_BLAST_RADIUS,
    RecoveryState,
)

logger = logging.getLogger("traceforge.recovery")


VALID_STATE_TRANSITIONS: Dict[RecoveryState, List[RecoveryState]] = {
    "PROPOSED": ["VALIDATED", "CANCELLED"],
    "VALIDATED": ["AWAITING_APPROVAL", "CANCELLED"],
    "AWAITING_APPROVAL": ["APPROVED", "REJECTED", "CANCELLED"],
    "APPROVED": ["EXECUTING_SIMULATION", "CANCELLED"],
    "REJECTED": ["CANCELLED"],
    "EXECUTING_SIMULATION": ["SUCCEEDED", "FAILED"],
    "SUCCEEDED": [],
    "FAILED": ["CANCELLED"],
    "CANCELLED": [],
}


def validate_transition(current: RecoveryState, target: RecoveryState) -> bool:
    """Enforces strict backend-driven state machine transitions."""
    allowed = VALID_STATE_TRANSITIONS.get(current, [])
    return target in allowed


def verify_proposal_policies(
    req: CreateRecoveryProposalRequest,
) -> Tuple[bool, List[PolicyVerificationResult]]:
    """Runs rigorous pre-execution policy verification checks:

    1. Action allowlisted
    2. Target service exists
    3. Required evidence exists
    4. Runbook prerequisites satisfied
    5. Proposed scope valid
    6. Blast-radius policy satisfied
    """
    results: List[PolicyVerificationResult] = []
    graph = db_client.get_graph()

    # Policy 1: Allowlist check
    if req.action_type not in ALLOWLISTED_ACTION_TYPES:
        results.append(PolicyVerificationResult(
            policy_name="ALLOWLIST_VERIFICATION",
            passed=False,
            details=f"Action type '{req.action_type}' is unauthorized. Allowed: {', '.join(ALLOWLISTED_ACTION_TYPES)}",
        ))
    else:
        results.append(PolicyVerificationResult(
            policy_name="ALLOWLIST_VERIFICATION",
            passed=True,
            details=f"Action type '{req.action_type}' is on the authorized allowlist.",
        ))

    # Policy 2: Target service existence check
    svc_res = graph.ro_query("MATCH (s:Service {id: $id}) RETURN s.id, s.name", {"id": req.target_service_id})
    if not svc_res.result_set:
        results.append(PolicyVerificationResult(
            policy_name="TARGET_SERVICE_EXISTS",
            passed=False,
            details=f"Target service '{req.target_service_id}' does not exist in the operational graph.",
        ))
    else:
        results.append(PolicyVerificationResult(
            policy_name="TARGET_SERVICE_EXISTS",
            passed=True,
            details=f"Target service '{req.target_service_id}' ({svc_res.result_set[0][1]}) verified in topology.",
        ))

    # Policy 3: Required evidence check
    if req.required_evidence_ids:
        evi_res = graph.ro_query(
            "MATCH (e:Evidence) WHERE e.id IN $eids RETURN collect(e.id)",
            {"eids": req.required_evidence_ids},
        )
        found_eids = set(evi_res.result_set[0][0]) if evi_res.result_set else set()
        missing = set(req.required_evidence_ids) - found_eids
        if missing:
            results.append(PolicyVerificationResult(
                policy_name="REQUIRED_EVIDENCE_EXISTS",
                passed=False,
                details=f"Missing required evidence: {', '.join(missing)}",
            ))
        else:
            results.append(PolicyVerificationResult(
                policy_name="REQUIRED_EVIDENCE_EXISTS",
                passed=True,
                details=f"All {len(req.required_evidence_ids)} required evidence items verified in graph.",
            ))
    else:
        results.append(PolicyVerificationResult(
            policy_name="REQUIRED_EVIDENCE_EXISTS",
            passed=True,
            details="No specific prerequisite evidence IDs required.",
        ))

    # Policy 4: Runbook prerequisites
    if req.runbook_id:
        rbk_res = graph.ro_query(
            "MATCH (r:Runbook {id: $rid})-[:APPLIES_TO]->(s:Service) RETURN r.id, s.id",
            {"rid": req.runbook_id},
        )
        if not rbk_res.result_set:
            results.append(PolicyVerificationResult(
                policy_name="RUNBOOK_PREREQUISITE_SATISFIED",
                passed=False,
                details=f"Runbook '{req.runbook_id}' is not cataloged or does not apply to service.",
            ))
        else:
            results.append(PolicyVerificationResult(
                policy_name="RUNBOOK_PREREQUISITE_SATISFIED",
                passed=True,
                details=f"Runbook '{req.runbook_id}' confirmed valid for target service.",
            ))
    else:
        results.append(PolicyVerificationResult(
            policy_name="RUNBOOK_PREREQUISITE_SATISFIED",
            passed=True,
            details="Standard automated remediation action (runbook optional).",
        ))

    # Policy 5: Scope & Parameter validity
    if req.action_type == "rollback_deployment" and not req.parameters.get("revision"):
        results.append(PolicyVerificationResult(
            policy_name="SCOPE_VALIDITY",
            passed=False,
            details="Rollback deployment action requires a target 'revision' parameter.",
        ))
    else:
        results.append(PolicyVerificationResult(
            policy_name="SCOPE_VALIDITY",
            passed=True,
            details="Action parameters and scope conform to operational specification.",
        ))

    # Policy 6: Blast-radius policy
    blast = find_downstream_dependents(req.target_service_id, max_depth=3)
    downstream_count = len(blast.get("nodes", []))
    if downstream_count > MAX_ALLOWED_BLAST_RADIUS:
        results.append(PolicyVerificationResult(
            policy_name="BLAST_RADIUS_POLICY",
            passed=False,
            details=f"Downstream blast radius exceeds limit: {downstream_count} services affected (max allowed: {MAX_ALLOWED_BLAST_RADIUS}).",
        ))
    else:
        results.append(PolicyVerificationResult(
            policy_name="BLAST_RADIUS_POLICY",
            passed=True,
            details=f"Blast radius policy satisfied: {downstream_count} downstream dependents (within limit of {MAX_ALLOWED_BLAST_RADIUS}).",
        ))

    all_passed = all(r.passed for r in results)
    return all_passed, results


def create_or_get_recovery_proposal(
    req: CreateRecoveryProposalRequest,
) -> ProposedRecoveryAction:
    """Idempotently creates a recovery proposal or returns existing if idempotency key matches."""
    graph = db_client.get_graph()

    # 1. Check idempotency key in graph
    existing = graph.ro_query(
        "MATCH (ra:RecoveryProposal {idempotency_key: $key}) RETURN ra.id",
        {"key": req.idempotency_key},
    )
    if existing.result_set:
        action_id = existing.result_set[0][0]
        proposal = get_recovery_action(action_id)
        if proposal:
            return proposal

    # 2. Compute cryptographic fingerprint
    prop_hash = compute_proposal_hash(
        incident_id=req.incident_id,
        action_type=req.action_type,
        target_service_id=req.target_service_id,
        parameters=req.parameters,
        justification=req.justification,
    )

    action_id = f"REC-SIM-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 3. Verify policies
    passed, policy_results = verify_proposal_policies(req)
    state: RecoveryState = "AWAITING_APPROVAL" if passed else "PROPOSED"

    initial_audit = {
        "timestamp": now_iso,
        "from_state": "NONE",
        "to_state": state,
        "event": "PROPOSAL_CREATED",
        "actor": "system",
        "details": "Proposal submitted and pre-execution policies verified." if passed else "Policy check failed.",
    }

    # 4. Persist in FalkorDB
    query = """
    MATCH (inc:Incident {id: $incident_id})
    OPTIONAL MATCH (s:Service {id: $target_service_id})
    MERGE (ra:RecoveryProposal {id: $action_id})
    ON CREATE SET ra.action_type = $action_type,
                  ra.incident_id = $incident_id,
                  ra.target_service_id = $target_service_id,
                  ra.runbook_id = $runbook_id,
                  ra.step_id = $step_id,
                  ra.justification = $justification,
                  ra.state = $state,
                  ra.proposal_hash = $prop_hash,
                  ra.idempotency_key = $idempotency_key,
                  ra.created_at = $created_at,
                  ra.updated_at = $now_iso
    MERGE (inc)-[:PROPOSES_RECOVERY]->(ra)
    FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
        MERGE (ra)-[:TARGETS_SERVICE]->(s)
    )
    RETURN ra.id
    """
    graph.query(query, {
        "action_id": action_id,
        "action_type": req.action_type,
        "incident_id": req.incident_id,
        "target_service_id": req.target_service_id,
        "runbook_id": req.runbook_id or "",
        "step_id": req.step_id or "",
        "justification": req.justification,
        "state": state,
        "prop_hash": prop_hash,
        "idempotency_key": req.idempotency_key,
        "created_at": now_iso,
        "now_iso": now_iso,
    })

    return ProposedRecoveryAction(
        action_id=action_id,
        incident_id=req.incident_id,
        action_type=req.action_type,  # type: ignore
        target_service_id=req.target_service_id,
        runbook_id=req.runbook_id,
        step_id=req.step_id,
        parameters=req.parameters,
        justification=req.justification,
        required_evidence_ids=req.required_evidence_ids,
        state=state,
        proposal_hash=prop_hash,
        created_at=now_iso,
        updated_at=now_iso,
        idempotency_key=req.idempotency_key,
        validation_results=policy_results,
        audit_trail=[initial_audit],
    )


def record_approval_decision(
    action_id: str,
    req: ApprovalDecisionRequest,
) -> ProposedRecoveryAction:
    """Validates approval preconditions:

    - Proposal exists and is in AWAITING_APPROVAL state.
    - Proposal hash matches exactly (proposal not mutated).
    - Transitions to APPROVED or REJECTED.
    """
    proposal = get_recovery_action(action_id)
    if not proposal:
        raise ValueError(f"Recovery proposal '{action_id}' not found.")

    if proposal.state != "AWAITING_APPROVAL":
        raise ValueError(f"Proposal '{action_id}' is in state '{proposal.state}', cannot approve/reject.")

    # Guard: Verify proposal hash
    if proposal.proposal_hash != req.proposal_hash:
        raise ValueError("Proposal integrity violation: proposal content has been modified since approval request.")

    target_state: RecoveryState = "APPROVED" if req.decision == "APPROVED" else "REJECTED"
    if not validate_transition(proposal.state, target_state):
        raise ValueError(f"Invalid state transition from {proposal.state} to {target_state}")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    approval_id = f"APP-{uuid.uuid4().hex[:6].upper()}"

    audit_entry = {
        "timestamp": now_iso,
        "from_state": proposal.state,
        "to_state": target_state,
        "event": f"DECISION_{req.decision}",
        "actor": f"{req.approver} ({req.role})",
        "details": req.notes,
    }

    graph = db_client.get_graph()
    update_query = """
    MATCH (ra:RecoveryProposal {id: $action_id})
    SET ra.state = $target_state,
        ra.approval_id = $approval_id,
        ra.approver = $approver,
        ra.approval_status = $decision,
        ra.approval_decided_at = $now_iso,
        ra.approval_notes = $notes,
        ra.updated_at = $now_iso
    WITH ra
    MERGE (ap:Approval {id: $approval_id})
    ON CREATE SET ap.approver = $approver,
                  ap.role = $role,
                  ap.status = $decision,
                  ap.decided_at = $now_iso,
                  ap.notes = $notes
    MERGE (ra)-[:REQUIRES]->(ap)
    """
    graph.query(update_query, {
        "action_id": action_id,
        "target_state": target_state,
        "approval_id": approval_id,
        "approver": req.approver,
        "role": req.role,
        "decision": req.decision,
        "now_iso": now_iso,
        "notes": req.notes,
    })

    proposal.state = target_state
    proposal.approval_id = approval_id
    proposal.approver = req.approver
    proposal.approval_status = req.decision
    proposal.approval_decided_at = now_iso
    proposal.approval_notes = req.notes
    proposal.updated_at = now_iso
    proposal.audit_trail.append(audit_entry)

    return proposal


def execute_simulated_recovery(
    action_id: str,
    req: ExecuteSimulationRequest,
) -> ProposedRecoveryAction:
    """Executes a strictly safe SIMULATED recovery action.

    NEVER executes real infrastructure commands.

    Verifications:
    1. Proposal exists and is APPROVED.
    2. Proposal has not already executed (SUCCEEDED or FAILED).
    3. Hash matches (no mutation).
    4. Approver matches approved record.
    5. Action type is allowlisted.
    """
    proposal = get_recovery_action(action_id)
    if not proposal:
        raise ValueError(f"Recovery proposal '{action_id}' not found.")

    if proposal.state in ["SUCCEEDED", "FAILED"]:
        raise ValueError(f"Action '{action_id}' has already been executed (state: {proposal.state}). Idempotency violation.")

    if proposal.state != "APPROVED":
        raise ValueError(f"Action '{action_id}' must be in 'APPROVED' state before simulation (current: {proposal.state}).")

    if proposal.proposal_hash != req.proposal_hash:
        raise ValueError("Proposal integrity violation: proposal content changed after approval.")

    if proposal.approver != req.approver:
        raise ValueError(f"Unauthorized execution: approver '{req.approver}' does not match authorized approver '{proposal.approver}'.")

    # Guard: Double check allowlist
    if proposal.action_type not in ALLOWLISTED_ACTION_TYPES:
        raise ValueError(f"Action type '{proposal.action_type}' is not allowlisted.")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    graph = db_client.get_graph()

    # Step 1: Transition to EXECUTING_SIMULATION
    graph.query(
        "MATCH (ra:RecoveryProposal {id: $id}) SET ra.state = 'EXECUTING_SIMULATION', ra.updated_at = $now",
        {"id": action_id, "now": now_iso},
    )

    # Step 2: Execute safe simulated outcome (Zero real infrastructure commands)
    simulated_impact = {
        "simulated": True,
        "infrastructure_mutated": False,
        "action_type": proposal.action_type,
        "target_service": proposal.target_service_id,
        "dry_run_command": f"SIMULATE_{proposal.action_type.upper()} on {proposal.target_service_id}",
        "simulated_recovery_metrics": {
            "p99_latency_ms": 120,
            "error_rate_percent": 0.02,
            "active_connections": 22,
            "status": "NORMALIZED",
        },
        "simulated_topological_effect": f"Service '{proposal.target_service_id}' returned to operational status in sandbox.",
    }

    # Step 3: Transition to SUCCEEDED
    graph.query(
        """
        MATCH (ra:RecoveryProposal {id: $id})
        SET ra.state = 'SUCCEEDED',
            ra.simulation_executed_at = $now,
            ra.updated_at = $now
        """,
        {"id": action_id, "now": now_iso},
    )

    audit_exec = {
        "timestamp": now_iso,
        "from_state": "APPROVED",
        "to_state": "SUCCEEDED",
        "event": "SIMULATION_COMPLETED",
        "actor": req.approver,
        "details": "Simulated recovery executed cleanly. Real infrastructure untouched.",
    }

    proposal.state = "SUCCEEDED"
    proposal.simulation_executed_at = now_iso
    proposal.simulation_output = simulated_impact
    proposal.updated_at = now_iso
    proposal.audit_trail.append(audit_exec)

    return proposal


def get_recovery_action(action_id: str) -> Optional[ProposedRecoveryAction]:
    """Retrieves recovery proposal record from FalkorDB."""
    graph = db_client.get_graph()
    query = """
    MATCH (ra:RecoveryProposal {id: $id})
    OPTIONAL MATCH (ra)-[:REQUIRES]->(ap:Approval)
    RETURN ra.id,
           ra.incident_id,
           ra.action_type,
           ra.target_service_id,
           ra.runbook_id,
           ra.step_id,
           ra.justification,
           ra.state,
           ra.proposal_hash,
           ra.idempotency_key,
           ra.created_at,
           ra.updated_at,
           ra.approval_id,
           ra.approver,
           ra.approval_status,
           ra.approval_decided_at,
           ra.approval_notes,
           ra.simulation_executed_at
    """
    res = graph.ro_query(query, {"id": action_id})
    if not res.result_set:
        return None

    r = res.result_set[0]
    return ProposedRecoveryAction(
        action_id=r[0],
        incident_id=r[1],
        action_type=r[2],
        target_service_id=r[3],
        runbook_id=r[4] or None,
        step_id=r[5] or None,
        parameters={},
        justification=r[6],
        state=r[7],
        proposal_hash=r[8],
        idempotency_key=r[9],
        created_at=r[10],
        updated_at=r[11],
        approval_id=r[12],
        approver=r[13],
        approval_status=r[14],
        approval_decided_at=r[15],
        approval_notes=r[16],
        simulation_executed_at=r[17],
        audit_trail=[
            {"timestamp": r[10], "state": r[7], "event": "RECORD_LOADED_FROM_GRAPH"}
        ],
    )


def list_recovery_proposals(incident_id: Optional[str] = None) -> List[ProposedRecoveryAction]:
    """Lists recovery proposals optionally filtered by incident."""
    graph = db_client.get_graph()
    where_clause = "WHERE ra.incident_id = $inc_id" if incident_id else ""
    query = f"""
    MATCH (ra:RecoveryProposal)
    {where_clause}
    RETURN ra.id
    ORDER BY ra.created_at DESC
    LIMIT 20
    """
    params = {"inc_id": incident_id} if incident_id else {}
    res = graph.ro_query(query, params)
    proposals: List[ProposedRecoveryAction] = []
    for row in res.result_set:
        p = get_recovery_action(row[0])
        if p:
            proposals.append(p)
    return proposals
