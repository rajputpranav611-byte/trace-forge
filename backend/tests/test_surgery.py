import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.client import db_client
from app.core.config import get_settings
from app.schemas.surgery import CreateExperimentRequest, GraphSurgeryAction
from app.db.surgery import (
    create_isolated_experiment,
    cleanup_experiment,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    try:
        db_client.connect()
    except Exception:
        pytest.skip("FalkorDB container not available")


def test_baseline_remains_unchanged_after_experiment():
    """Safety requirement: An isolated experiment must never alter the baseline graph."""
    db = db_client.get_client()
    baseline = db.select_graph(get_settings().FALKORDB_GRAPH_NAME)

    # Record baseline state
    nodes_before = baseline.query("MATCH (n) RETURN count(n)").result_set[0][0]
    edges_before = baseline.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]

    # Run experiment that removes a dependency
    req = CreateExperimentRequest(
        baseline_incident_id="INC-2026-8821",
        experiment_name="Sever Core to DB Dependency",
        actions=[
            GraphSurgeryAction(
                action_type="remove_dependency",
                source_id="payment-core",
                target_id="payment-db-cluster",
                relationship_type="DEPENDS_ON",
                justification="Test if payment-db-cluster is causally required for SEV1 failure",
            )
        ],
    )

    exp_summary = create_isolated_experiment(req)
    assert exp_summary.experiment_id.startswith("exp_")
    assert exp_summary.total_edges < edges_before

    # Verify baseline is 100% identical
    nodes_after = baseline.query("MATCH (n) RETURN count(n)").result_set[0][0]
    edges_after = baseline.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]

    assert nodes_before == nodes_after
    assert edges_before == edges_after

    # Clean up
    cleaned = cleanup_experiment(exp_summary.experiment_id)
    assert cleaned is True


def test_relevant_relationship_change_alters_investigation_result():
    """Acceptance criteria: Removing relevant dependency alters the hypothesis ranking / score

    and downstream blast radius.
    """
    payload = {
        "baseline_incident_id": "INC-2026-8821",
        "experiment_name": "Counterfactual: Sever payment-core to payment-db-cluster",
        "actions": [
            {
                "action_type": "remove_dependency",
                "source_id": "payment-core",
                "target_id": "payment-db-cluster",
                "relationship_type": "DEPENDS_ON",
                "justification": "Simulate database isolation",
            }
        ],
    }

    response = client.post("/api/v1/surgery/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["baseline_incident_id"] == "INC-2026-8821"
    assert "Controlled graph counterfactual" in data["disclaimer"]
    assert len(data["hypothesis_diffs"]) > 0

    # Locate payment-db-cluster or database hypothesis
    db_diff = next(
        (d for d in data["hypothesis_diffs"] if "database" in d["title"].lower() or "db" in d["title"].lower() or "payment-db-cluster" in d["title"].lower()),
        None,
    )
    assert db_diff is not None, "Hypothesis regarding payment-db-cluster should exist"

    # Causal path or score must be altered
    assert db_diff["causal_path_changed"] is True or db_diff["score_delta"] < 0.0 or db_diff["experiment_score"] != db_diff["baseline_score"]

    # Blast radius diff must reflect severed downstream services
    assert data["blast_radius_diff"]["service_id"] == "payment-db-cluster"
    assert data["blast_radius_diff"]["baseline_downstream_count"] > data["blast_radius_diff"]["experiment_downstream_count"]
    assert "payment-core" in data["blast_radius_diff"]["severed_services"]


def test_unrelated_graph_changes_do_not_arbitrarily_alter_results():
    """Surgical precision: Removing an unrelated dependency on another tier does not alter the target incident ranking."""
    payload = {
        "baseline_incident_id": "INC-2026-9043",
        "experiment_name": "Unrelated Auth Change",
        "actions": [
            {
                "action_type": "remove_dependency",
                "source_id": "auth-service",
                "target_id": "session-cache-redis",
                "relationship_type": "DEPENDS_ON",
                "justification": "Unrelated edge removal",
            }
        ],
    }

    response = client.post("/api/v1/surgery/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    b_top = data["baseline_investigation"]["top_hypothesis"]
    e_top = data["experiment_investigation"]["top_hypothesis"]

    assert b_top is not None
    assert e_top is not None
    assert b_top["id"] == e_top["id"]
    assert b_top["deterministic_score"] == e_top["deterministic_score"]


def test_failed_experiment_cannot_corrupt_baseline():
    """Safety requirement: Disallowed or invalid actions raise an error and leave baseline untouched."""
    db = db_client.get_client()
    baseline = db.select_graph(get_settings().FALKORDB_GRAPH_NAME)
    edges_before = baseline.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]

    payload = {
        "baseline_incident_id": "INC-2026-8821",
        "experiment_name": "Malicious Action",
        "actions": [
            {
                "action_type": "remove_dependency",
                "source_id": "payment-core",
                "target_id": "payment-db-cluster",
                "relationship_type": "MALICIOUS_INJECTION",
                "justification": "Attack test",
            }
        ],
    }

    response = client.post("/api/v1/surgery/simulate", json=payload)
    assert response.status_code == 400

    # Verify baseline untouched
    edges_after = baseline.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    assert edges_before == edges_after


def test_adversarial_nonexistent_source_node():
    """Adversarial check: Attempting to operate on a nonexistent source node fails with 400 without baseline alteration."""
    db = db_client.get_client()
    baseline = db.select_graph(get_settings().FALKORDB_GRAPH_NAME)
    edges_before = baseline.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]

    payload = {
        "baseline_incident_id": "INC-2026-8821",
        "experiment_name": "Ghost Node Test",
        "actions": [
            {
                "action_type": "remove_dependency",
                "source_id": "phantom-service-does-not-exist",
                "target_id": "payment-db-cluster",
                "relationship_type": "DEPENDS_ON",
                "justification": "Adversarial test for nonexistent source",
            }
        ],
    }

    response = client.post("/api/v1/surgery/simulate", json=payload)
    assert response.status_code == 400
    assert "does not exist in graph" in response.json()["detail"]

    edges_after = baseline.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    assert edges_before == edges_after


def test_adversarial_nonexistent_target_node():
    """Adversarial check: Attempting to operate on a nonexistent target node fails with 400."""
    payload = {
        "baseline_incident_id": "INC-2026-8821",
        "experiment_name": "Ghost Target Test",
        "actions": [
            {
                "action_type": "remove_dependency",
                "source_id": "payment-core",
                "target_id": "imaginary-target-db",
                "relationship_type": "DEPENDS_ON",
                "justification": "Adversarial test for nonexistent target",
            }
        ],
    }

    response = client.post("/api/v1/surgery/simulate", json=payload)
    assert response.status_code == 400
    assert "does not exist in graph" in response.json()["detail"]


def test_adversarial_nonexistent_relationship():
    """Adversarial check: Valid nodes but no such relationship edge between them fails with 400."""
    payload = {
        "baseline_incident_id": "INC-2026-8821",
        "experiment_name": "Inverted Edge Removal",
        "actions": [
            {
                "action_type": "remove_dependency",
                "source_id": "payment-db-cluster",
                "target_id": "nexus-api-gateway",
                "relationship_type": "DEPENDS_ON",
                "justification": "Removing reversed non-existent dependency",
            }
        ],
    }

    response = client.post("/api/v1/surgery/simulate", json=payload)
    assert response.status_code == 400
    assert "does not exist in graph" in response.json()["detail"]


def test_adversarial_invalid_incident_id():
    """Adversarial check: Nonexistent incident ID returns 400 and does not leak cloned graphs."""
    payload = {
        "baseline_incident_id": "INC-NONEXISTENT-9999",
        "experiment_name": "Invalid Incident Run",
        "actions": [
            {
                "action_type": "remove_dependency",
                "source_id": "payment-core",
                "target_id": "payment-db-cluster",
                "relationship_type": "DEPENDS_ON",
                "justification": "Test invalid incident",
            }
        ],
    }

    response = client.post("/api/v1/surgery/simulate", json=payload)
    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()


def test_repeated_experiments_do_not_leak_state():
    """Adversarial check: Running identical or consecutive interventions does not leak state across runs."""
    db = db_client.get_client()
    baseline = db.select_graph(get_settings().FALKORDB_GRAPH_NAME)
    edges_baseline = baseline.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]

    payload = {
        "baseline_incident_id": "INC-2026-8821",
        "experiment_name": "State Leakage Check 1",
        "actions": [
            {
                "action_type": "remove_dependency",
                "source_id": "payment-core",
                "target_id": "payment-db-cluster",
                "relationship_type": "DEPENDS_ON",
                "justification": "First run of repeated experiment",
            }
        ],
    }

    res1 = client.post("/api/v1/surgery/simulate", json=payload)
    assert res1.status_code == 200
    exp1_id = res1.json()["experiment_id"]

    # Re-run immediately
    payload["experiment_name"] = "State Leakage Check 2"
    res2 = client.post("/api/v1/surgery/simulate", json=payload)
    assert res2.status_code == 200
    exp2_id = res2.json()["experiment_id"]

    assert exp1_id != exp2_id
    assert res1.json()["hypothesis_diffs"][0]["score_delta"] == res2.json()["hypothesis_diffs"][0]["score_delta"]

    # Verify baseline is completely intact
    edges_after = baseline.query("MATCH ()-[r]->() RETURN count(r)").result_set[0][0]
    assert edges_baseline == edges_after


def test_score_factor_diff_breakdown_auditability():
    """Audit verification: Score changes include honest factor contributions and explanations."""
    payload = {
        "baseline_incident_id": "INC-2026-8821",
        "experiment_name": "Audit Score Factor Verification",
        "actions": [
            {
                "action_type": "remove_dependency",
                "source_id": "payment-core",
                "target_id": "payment-db-cluster",
                "relationship_type": "DEPENDS_ON",
                "justification": "Audit factor contributions",
            }
        ],
    }

    response = client.post("/api/v1/surgery/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Find the hypothesis that shifted
    shifted = next((d for d in data["hypothesis_diffs"] if d["score_delta"] != 0.0), None)
    assert shifted is not None
    assert len(shifted["factor_diffs"]) > 0
    assert len(shifted["score_delta_explanation"]) > 0

    # Ensure each factor diff contains baseline and experiment reasons
    for fd in shifted["factor_diffs"]:
        assert fd["factor_name"] != ""
        assert isinstance(fd["contribution_delta"], float)
        assert len(fd["experiment_reason"]) > 0

