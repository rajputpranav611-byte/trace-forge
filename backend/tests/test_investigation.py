import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.db.seed import seed_graph

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_seed():
    seed_graph("traceforge")


def test_investigation_valid_incident_end_to_end():
    """Tests full investigation context resolution for active SEV1 incident INC-2026-8821."""
    response = client.get("/api/v1/investigation/context/INC-2026-8821?max_depth=3")
    assert response.status_code == 200
    data = response.json()

    # 1. Incident details
    inc = data["incident"]
    assert inc["id"] == "INC-2026-8821"
    assert inc["severity"] == "SEV1"
    assert inc["status"] == "active"

    # 2. Associated alerts and metrics
    alerts = data["alerts"]
    assert len(alerts) >= 3
    alert_names = [a["name"] for a in alerts]
    assert "PaymentCore_HighLatency_p99" in alert_names
    assert "Postgres_PoolExhausted" in alert_names

    metrics = data["metrics"]
    assert len(metrics) >= 1
    metric_names = [m["metric_name"] for m in metrics]
    assert "hikaricp_active_connections" in metric_names

    # 3. Topology & bounded dependency traversal
    topology = data["topology"]
    affected_ids = [s["id"] for s in topology["affected_services"]]
    assert "payment-core" in affected_ids
    assert "checkout-orchestrator" in affected_ids
    assert "nexus-api-gateway" in affected_ids

    # Deep dependencies reached
    traversed_ids = [s["id"] for s in topology["traversed_services"]]
    assert "payment-db-cluster" in traversed_ids
    assert "card-vault" in traversed_ids

    # Traversed paths exist and are structured
    assert len(topology["traversed_paths"]) >= 1
    assert any(len(p["node_ids"]) >= 2 for p in topology["traversed_paths"])

    # 4. Deployments (candidate root causes)
    deployments = data["deployments"]
    assert len(deployments) >= 1
    dep_ids = [d["id"] for d in deployments]
    assert "DEP-4012" in dep_ids  # True root cause release on payment-core
    assert "DEP-4011" in dep_ids  # Misleading deployment candidate on auth-service

    # 5. Applicable runbooks
    runbooks = data["runbooks"]
    assert len(runbooks) >= 1
    rbk_ids = [r["id"] for r in runbooks]
    assert "RBK-PAY-01" in rbk_ids
    pay_runbook = next(r for r in runbooks if r["id"] == "RBK-PAY-01")
    assert len(pay_runbook["steps"]) == 3
    assert pay_runbook["steps"][0]["step_number"] == 1

    # 6. Evidence summary
    summary = data["evidence_summary"]
    assert summary["source_incident_id"] == "INC-2026-8821"
    assert summary["is_sufficient_evidence"] is True


def test_investigation_unknown_incident_404():
    """Tests that querying a non-existent incident ID yields an explicit 404."""
    response = client.get("/api/v1/investigation/context/INC-NON-EXISTENT")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_investigation_missing_relationships_detected():
    """Tests that the investigation detects missing/unregistered catalog relationships

    when relevant services (such as risk-scoring-engine) are involved in traversal.
    """
    # Trigger context retrieval for incident that traverses risk engine if present
    # We can also test direct topology helper
    from app.db.investigation import get_topology_for_services
    topo = get_topology_for_services(["fraud-detection-service"], max_depth=2)
    node_ids = [n["id"] for n in topo["nodes"]]
    assert "risk-scoring-engine" in node_ids

    # Verify build_investigation_context includes the missing relationship message
    from app.db.investigation import build_investigation_context
    with patch("app.db.investigation.get_incident_alerts_and_metrics") as mock_base:
        mock_base.return_value = {
            "incident": {
                "id": "TEST-INC",
                "title": "Test",
                "severity": "SEV2",
                "status": "active",
                "started_at": "2026-10-15T12:00:00Z",
                "resolved_at": "",
                "summary": "Mock",
            },
            "affected_services": [{"id": "fraud-detection-service", "name": "Fraud Detection", "tier": 1, "team": "Risk", "status": "operational"}],
            "alerts": [],
            "metrics": [],
        }
        res = build_investigation_context("TEST-INC", max_depth=2)
        assert res is not None
        assert len(res.topology.missing_relationships_detected) >= 1
        assert "risk-scoring-engine" in res.topology.missing_relationships_detected[0]


def test_investigation_database_failure_handling():
    """Tests that unexpected FalkorDB connection/query errors return 500 with useful error details."""
    with patch("app.db.client.db_client.get_graph", side_effect=RuntimeError("FalkorDB socket timeout")):
        response = client.get("/api/v1/investigation/context/INC-2026-8821")
        assert response.status_code == 500
        assert "database query error" in response.json()["detail"].lower()
