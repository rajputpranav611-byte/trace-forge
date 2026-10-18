import pytest
from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_list_historical_investigations_persisted_in_falkordb():
    """Verify that completed investigations are stored in FalkorDB and retrievable."""
    response = client.get("/api/v1/memory/investigations?limit=25")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

    first = data[0]
    assert "investigation_id" in first
    assert "incident_id" in first
    assert "incident_title" in first
    assert "provenance" in first
    assert "epistemic_status" in first["provenance"]
    assert first["provenance"]["epistemic_status"] in [
        "VERIFIED_OBSERVATION",
        "UNVERIFIED_CLAIM",
        "SIMULATED_DRY_RUN",
        "REJECTED_HYPOTHESIS",
    ]


def test_compare_historical_memory_identifies_relevant_and_irrelevant_incidents():
    """Verify that comparing historical memory:

    1. Identifies relevant historical incidents through graph dependencies (e.g. INC-2026-7104 via Kafka).
    2. Identifies irrelevant historical cases (e.g. INC-2026-9043 edge gateway).
    3. Explains why a case is relevant or not relevant.
    """
    response = client.get("/api/v1/memory/compare/INC-2026-8821?max_depth=3")
    assert response.status_code == 200
    data = response.json()
    assert data["current_incident_id"] == "INC-2026-8821"
    assert "payment-core" in data["current_affected_services"]

    comparisons = data["historical_comparisons"]
    assert len(comparisons) >= 2

    # Check for INC-2026-7104 (Kafka dependency link)
    kafka_match = next((c for c in comparisons if c["historical_incident_id"] == "INC-2026-7104"), None)
    assert kafka_match is not None
    assert kafka_match["is_relevant"] is True
    assert kafka_match["relevance_score"] >= 0.25
    assert "topological" in kafka_match["relevance_explanation"].lower() or "dependencies" in kafka_match["relevance_explanation"].lower()
    assert "event-stream-kafka" in kafka_match["common_affected_services"]

    # Check for INC-2026-9043 (Edge gateway unrelated)
    edge_match = next((c for c in comparisons if c["historical_incident_id"] == "INC-2026-9043"), None)
    assert edge_match is not None
    assert edge_match["is_relevant"] is False
    assert edge_match["relevance_score"] < 0.25
    assert "not relevant" in edge_match["relevance_explanation"].lower()


def test_epistemic_guardrail_unverified_claims_not_treated_as_verified_facts():
    """Ensures LLM-generated claims, unverified actions, and simulated outcomes

    are NEVER marked as VERIFIED_OBSERVATION.
    """
    response = client.get("/api/v1/memory/investigations?limit=50")
    assert response.status_code == 200
    investigations = response.json()

    for inv in investigations:
        prov = inv["provenance"]
        # If there are no real verified recovery actions, it must NOT be marked verified
        if not inv.get("verified_recovery_actions"):
            assert prov["verified"] is False
            assert prov["epistemic_status"] != "VERIFIED_OBSERVATION"

    # Also verify disclaimer in comparison response
    comp_resp = client.get("/api/v1/memory/compare/INC-2026-8821")
    assert comp_resp.status_code == 200
    for comp in comp_resp.json()["historical_comparisons"]:
        assert "NOT treated as verified real-world operational truth" in comp["epistemic_disclaimer"]


def test_runbook_prerequisites_checked_against_current_incident():
    """Verifies that the historical comparison checks runbook prerequisites

    against the active incident's evidence and services.
    """
    response = client.get("/api/v1/memory/compare/INC-2026-8821")
    assert response.status_code == 200
    comparisons = response.json()["historical_comparisons"]
    assert len(comparisons) > 0

    first_comp = comparisons[0]
    prereqs = first_comp["runbook_prerequisite_checks"]
    assert len(prereqs) > 0
    step1_check = next((p for p in prereqs if p["required_step_id"] == "STP-01"), None)
    assert step1_check is not None
    assert step1_check["runbook_id"] == "RBK-PAY-01"
    assert step1_check["is_satisfied"] is True
    assert "satisfied" in step1_check["reason"].lower()


def test_compare_nonexistent_incident_returns_404():
    """Verifies that an unknown incident ID returns HTTP 404."""
    response = client.get("/api/v1/memory/compare/INC-NONEXISTENT-9999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
