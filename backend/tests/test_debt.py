import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.client import db_client
from app.db.debt import evaluate_evidence_debt, record_debt_resolution
from app.schemas.debt import ResolveDebtRequest

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    try:
        db_client.connect()
    except Exception:
        pytest.skip("FalkorDB container not available")


def test_missing_dependency_relationship_debt():
    """Validates that uncataloged runtime dependencies (e.g. risk-scoring-engine to merchant-config-service)

    are correctly identified as BLOCKING Evidence Debt.
    """
    report = evaluate_evidence_debt("INC-2026-8821")
    assert report is not None
    assert report.incident_id == "INC-2026-8821"

    # Verify missing dependency gap
    dep_gap = next((g for g in report.gaps if g.category == "MISSING_DEPENDENCY_VERIFICATION"), None)
    assert dep_gap is not None
    assert dep_gap.severity == "BLOCKING"
    assert "risk-scoring-engine" in dep_gap.affected_entities
    assert "merchant-config-service" in dep_gap.affected_entities
    assert "trace" in dep_gap.resolving_evidence.lower()
    assert len(report.blocked_recovery_actions) > 0


def test_contradictory_evidence_debt():
    """Validates that contradictory observations are captured as WARNING debt."""
    report = evaluate_evidence_debt("INC-2026-8821")
    assert report is not None

    # Check for contradictions
    contra_gap = next((g for g in report.gaps if g.category == "CONTRADICTORY_EVIDENCE"), None)
    assert contra_gap is not None
    assert contra_gap.severity == "WARNING"
    assert "EVI-03" in contra_gap.affected_entities

    # Check for unlinked alert debt
    auth_alert = next((g for g in report.gaps if g.category == "UNLINKED_ALERT" and "auth-service" in g.affected_entities), None)
    assert auth_alert is not None
    assert auth_alert.severity == "WARNING"


def test_insufficient_telemetry_epistemic_debt():
    """Validates that sparse incidents (e.g. INC-2026-9043) generate INSUFFICIENT_TELEMETRY debt

    that blocks automated resolution.
    """
    report = evaluate_evidence_debt("INC-2026-9043")
    assert report is not None

    sparse_gap = next((g for g in report.gaps if g.category == "INSUFFICIENT_TELEMETRY"), None)
    assert sparse_gap is not None
    assert sparse_gap.severity == "BLOCKING"
    assert "Autonomous incident auto-mitigation" in report.blocked_recovery_actions


def test_resolved_evidence_gap_persisted_in_graph():
    """Validates that resolving an evidence gap persists an EvidenceDebt node in FalkorDB

    and transitions the gap from ACTIVE to RESOLVED.
    """
    incident_id = "INC-2026-8821"
    gap_id = "DEBT-MISSING-DEP-01"

    req = ResolveDebtRequest(
        gap_id=gap_id,
        resolution_evidence_id="OTEL-TRACE-8821-99B",
        notes="Verified distributed trace spans confirming gRPC downstream channel",
    )

    # 1. Resolve via service / API
    success = record_debt_resolution(incident_id, req)
    assert success is True

    # 2. Re-evaluate report and verify status
    report = evaluate_evidence_debt(incident_id)
    assert report is not None

    resolved_gap = next((g for g in report.gaps if g.id == gap_id), None)
    assert resolved_gap is not None
    assert resolved_gap.status == "RESOLVED"
    assert report.summary.resolved_count >= 1

    # 3. Verify graph node existence
    graph = db_client.get_graph()
    res = graph.query("MATCH (d:EvidenceDebt {id: $gap_id, status: 'RESOLVED'}) RETURN count(d)", {"gap_id": gap_id})
    assert res.result_set[0][0] == 1


def test_debt_report_api_endpoint():
    """Tests the FastAPI GET /api/v1/debt/report/{incident_id} endpoint."""
    response = client.get("/api/v1/debt/report/INC-2026-8821")
    assert response.status_code == 200
    data = response.json()

    assert data["incident_id"] == "INC-2026-8821"
    assert "summary" in data
    assert "BLOCKING > WARNING > INFORMATIONAL" in data["summary"]["priority_rule_explanation"]
    assert len(data["gaps"]) > 0
