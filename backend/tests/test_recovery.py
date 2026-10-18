import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.db.client import db_client
from app.schemas.recovery import compute_proposal_hash

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    try:
        db_client.connect()
    except Exception:
        pytest.skip("FalkorDB container not available")


def test_unauthorized_action_blocked_by_allowlist():
    """Safety requirement: An action type not on the allowlist is blocked."""
    payload = {
        "incident_id": "INC-2026-8821",
        "action_type": "drop_production_tables_malicious",
        "target_service_id": "payment-core",
        "parameters": {},
        "justification": "Malicious drop action",
        "idempotency_key": f"key-{uuid.uuid4().hex[:8]}",
    }
    response = client.post("/api/v1/recovery/propose", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == "PROPOSED"
    allowlist_policy = next((p for p in data["validation_results"] if p["policy_name"] == "ALLOWLIST_VERIFICATION"), None)
    assert allowlist_policy is not None
    assert allowlist_policy["passed"] is False


def test_missing_target_service_blocked():
    """Safety requirement: Actions targeting non-existent services are blocked."""
    payload = {
        "incident_id": "INC-2026-8821",
        "action_type": "restart_service",
        "target_service_id": "ghost-phantom-service-404",
        "parameters": {},
        "justification": "Restart non-existent service",
        "idempotency_key": f"key-{uuid.uuid4().hex[:8]}",
    }
    response = client.post("/api/v1/recovery/propose", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["state"] == "PROPOSED"
    svc_policy = next((p for p in data["validation_results"] if p["policy_name"] == "TARGET_SERVICE_EXISTS"), None)
    assert svc_policy is not None
    assert svc_policy["passed"] is False


def test_missing_prerequisite_scope_blocked():
    """Safety requirement: Rollback actions without required revision parameter fail validation."""
    payload = {
        "incident_id": "INC-2026-8821",
        "action_type": "rollback_deployment",
        "target_service_id": "payment-core",
        "parameters": {},  # missing 'revision'
        "justification": "Rollback without specifying target revision",
        "idempotency_key": f"key-{uuid.uuid4().hex[:8]}",
    }
    response = client.post("/api/v1/recovery/propose", json=payload)
    assert response.status_code == 201
    data = response.json()
    scope_policy = next((p for p in data["validation_results"] if p["policy_name"] == "SCOPE_VALIDITY"), None)
    assert scope_policy is not None
    assert scope_policy["passed"] is False


def test_idempotency_prevents_duplicate_proposals():
    """Idempotency requirement: Submitting identical idempotency_key returns the exact same proposal record."""
    shared_key = f"idemp-{uuid.uuid4().hex[:8]}"
    payload = {
        "incident_id": "INC-2026-8821",
        "action_type": "rollback_deployment",
        "target_service_id": "payment-core",
        "runbook_id": "RBK-PAY-01",
        "step_id": "STP-02",
        "parameters": {"revision": "DEP-4010"},
        "justification": "Rollback recent canary release DEP-4012 on payment-core",
        "idempotency_key": shared_key,
    }

    res1 = client.post("/api/v1/recovery/propose", json=payload)
    assert res1.status_code == 201
    data1 = res1.json()

    res2 = client.post("/api/v1/recovery/propose", json=payload)
    assert res2.status_code == 201
    data2 = res2.json()

    assert data1["action_id"] == data2["action_id"]
    assert data1["proposal_hash"] == data2["proposal_hash"]


def test_rejected_approval_blocks_execution():
    """State Machine: Rejected proposals transition to REJECTED and cannot be simulated."""
    key = f"key-reject-{uuid.uuid4().hex[:8]}"
    payload = {
        "incident_id": "INC-2026-8821",
        "action_type": "rollback_deployment",
        "target_service_id": "payment-core",
        "runbook_id": "RBK-PAY-01",
        "step_id": "STP-02",
        "parameters": {"revision": "DEP-4010"},
        "justification": "Rollback payment-core release",
        "idempotency_key": key,
    }
    prop_res = client.post("/api/v1/recovery/propose", json=payload)
    proposal = prop_res.json()
    action_id = proposal["action_id"]

    # Reject proposal
    decide_payload = {
        "approver": "incident-commander@nexuspay.io",
        "role": "Incident Commander",
        "decision": "REJECTED",
        "notes": "Rejected: Peak checkout traffic hour, wait for off-peak window.",
        "proposal_hash": proposal["proposal_hash"],
    }
    dec_res = client.post(f"/api/v1/recovery/{action_id}/decide", json=decide_payload)
    assert dec_res.status_code == 200
    rejected_data = dec_res.json()
    assert rejected_data["state"] == "REJECTED"

    # Attempt execution -> must be blocked
    sim_payload = {
        "approver": "incident-commander@nexuspay.io",
        "idempotency_key": f"exec-{uuid.uuid4().hex[:6]}",
        "proposal_hash": proposal["proposal_hash"],
    }
    sim_res = client.post(f"/api/v1/recovery/{action_id}/simulate", json=sim_payload)
    assert sim_res.status_code == 400
    assert "must be in 'APPROVED' state" in sim_res.json()["detail"]


def test_changed_proposal_hash_mismatch_blocks_approval():
    """Integrity requirement: If a proposal is tampered with or submitted with wrong hash, approval fails."""
    key = f"key-hash-{uuid.uuid4().hex[:8]}"
    payload = {
        "incident_id": "INC-2026-8821",
        "action_type": "restart_service",
        "target_service_id": "checkout-orchestrator",
        "parameters": {},
        "justification": "Restart checkout orchestrator worker pods",
        "idempotency_key": key,
    }
    prop_res = client.post("/api/v1/recovery/propose", json=payload)
    proposal = prop_res.json()
    action_id = proposal["action_id"]

    # Try approving with corrupted hash
    decide_payload = {
        "approver": "sre-lead@nexuspay.io",
        "role": "Staff SRE",
        "decision": "APPROVED",
        "notes": "Approved restart",
        "proposal_hash": "corrupted_hash_99999999999999999999999999999999",
    }
    dec_res = client.post(f"/api/v1/recovery/{action_id}/decide", json=decide_payload)
    assert dec_res.status_code == 400
    assert "Proposal integrity violation" in dec_res.json()["detail"]


def test_full_successful_simulated_recovery_lifecycle():
    """Acceptance criteria: Valid proposal -> approved -> simulated -> audited in FalkorDB."""
    key = f"key-success-{uuid.uuid4().hex[:8]}"
    payload = {
        "incident_id": "INC-2026-8821",
        "action_type": "rollback_deployment",
        "target_service_id": "payment-core",
        "runbook_id": "RBK-PAY-01",
        "step_id": "STP-02",
        "parameters": {"revision": "DEP-4010"},
        "justification": "Rollback recent canary release DEP-4012 on payment-core",
        "idempotency_key": key,
    }

    # 1. Propose
    p_res = client.post("/api/v1/recovery/propose", json=payload)
    assert p_res.status_code == 201
    proposal = p_res.json()
    action_id = proposal["action_id"]
    assert proposal["state"] == "AWAITING_APPROVAL"

    # 2. Approve
    decide_payload = {
        "approver": "staff-sre@nexuspay.io",
        "role": "Staff SRE",
        "decision": "APPROVED",
        "notes": "Verified DEP-4012 introduced unindexed scan. Authorized rollback to DEP-4010.",
        "proposal_hash": proposal["proposal_hash"],
    }
    dec_res = client.post(f"/api/v1/recovery/{action_id}/decide", json=decide_payload)
    assert dec_res.status_code == 200
    approved = dec_res.json()
    assert approved["state"] == "APPROVED"
    assert approved["approval_id"] is not None

    # 3. Simulate Execution
    sim_payload = {
        "approver": "staff-sre@nexuspay.io",
        "idempotency_key": f"exec-token-{uuid.uuid4().hex[:6]}",
        "proposal_hash": proposal["proposal_hash"],
    }
    sim_res = client.post(f"/api/v1/recovery/{action_id}/simulate", json=sim_payload)
    assert sim_res.status_code == 200
    executed = sim_res.json()
    assert executed["state"] == "SUCCEEDED"
    assert executed["simulation_output"]["infrastructure_mutated"] is False
    assert executed["simulation_output"]["simulated"] is True

    # 4. Double Execution Idempotency Block
    retry_res = client.post(f"/api/v1/recovery/{action_id}/simulate", json=sim_payload)
    assert retry_res.status_code == 400
    assert "already been executed" in retry_res.json()["detail"]

    # 5. Persisted in FalkorDB
    fetch_res = client.get(f"/api/v1/recovery/{action_id}")
    assert fetch_res.status_code == 200
    fetched = fetch_res.json()
    assert fetched["action_id"] == action_id
    assert fetched["state"] == "SUCCEEDED"
