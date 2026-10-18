import pytest
from app.db.queries import (
    list_incidents,
    get_incident_with_alerts,
    traverse_dependencies,
    find_downstream_dependents,
    get_deployments_for_service,
    get_historical_incidents_for_service,
)
from app.db.seed import seed_graph


@pytest.fixture(scope="session", autouse=True)
def setup_seed_data():
    """Ensure seeded state is present before running graph query tests."""
    seed_graph("traceforge")


def test_list_incidents():
    incidents = list_incidents()
    assert len(incidents) >= 3
    ids = [inc["id"] for inc in incidents]
    assert "INC-2026-8821" in ids
    assert "INC-2026-7104" in ids
    assert "INC-2026-9043" in ids

    # Filter active
    active = list_incidents(status="active")
    active_ids = [inc["id"] for inc in active]
    assert "INC-2026-8821" in active_ids
    assert "INC-2026-7104" not in active_ids


def test_get_incident_with_alerts():
    inc = get_incident_with_alerts("INC-2026-8821")
    assert inc is not None
    assert inc["id"] == "INC-2026-8821"
    assert inc["severity"] == "SEV1"

    # Verify connected affected services
    svc_ids = [s["id"] for s in inc["affected_services"]]
    assert "payment-core" in svc_ids
    assert "checkout-orchestrator" in svc_ids
    assert "nexus-api-gateway" in svc_ids

    # Verify connected alerts
    alert_ids = [a["id"] for a in inc["alerts"]]
    assert "ALT-101" in alert_ids or "ALT-102" in alert_ids


def test_traverse_dependencies_multihop():
    """Test multi-hop traversal:

    nexus-edge-gateway -> nexus-api-gateway -> checkout-orchestrator ->
    payment-core -> payment-db-cluster
    """
    res = traverse_dependencies("nexus-edge-gateway", max_depth=4)
    nodes = {n["id"]: n for n in res["nodes"]}
    edges = res["edges"]

    # Verify multi-hop path reached deep storage and processing layers
    assert "nexus-edge-gateway" in nodes
    assert "nexus-api-gateway" in nodes
    assert "checkout-orchestrator" in nodes
    assert "payment-core" in nodes
    assert "payment-db-cluster" in nodes
    assert len(edges) >= 4


def test_find_downstream_dependents():
    """If payment-db-cluster fails, upstream callers (payment-core, checkout-orchestrator, etc.)

    must be detected in its blast radius.
    """
    blast = find_downstream_dependents("payment-db-cluster", max_depth=3)
    nodes = {n["id"]: n for n in blast["nodes"]}

    assert "payment-db-cluster" in nodes
    assert "payment-core" in nodes
    assert "checkout-orchestrator" in nodes


def test_get_deployments_for_service():
    deps = get_deployments_for_service("payment-core")
    assert len(deps) >= 1
    root_cause_dep = deps[0]
    assert root_cause_dep["id"] == "DEP-4012"
    assert root_cause_dep["version"] == "v4.1.0-rc2"


def test_get_historical_incidents_for_service():
    history = get_historical_incidents_for_service("ledger-service")
    assert len(history) >= 1
    assert any(h["id"] == "INC-2026-7104" for h in history)
    hist_inc = next(h for h in history if h["id"] == "INC-2026-7104")
    assert hist_inc["status"] == "resolved"
    assert len(hist_inc["recovery_actions"]) >= 1
    assert hist_inc["recovery_actions"][0]["action_type"] == "scale_workers"
