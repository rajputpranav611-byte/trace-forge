import asyncio
import pytest
from app.db.seed import seed_graph
from app.mcp_server import mcp_server
from app.core.mcp_services import (
    trace_dependency_path_service,
    get_blast_radius_service,
    inspect_incident_evidence_service,
    compare_hypotheses_service,
    simulate_graph_intervention_service,
)
from app.db.client import db_client


@pytest.fixture(scope="session", autouse=True)
def setup_seed_data():
    """Ensure baseline FalkorDB graph state is seeded."""
    seed_graph("traceforge")


# -----------------------------------------------------------------------------
# Tool Registration & Schema Tests
# -----------------------------------------------------------------------------

def test_mcp_tool_registration():
    """Verify all 5 required tools are registered on the MCPServer with valid schemas."""
    tools = asyncio.run(mcp_server.list_tools())
    tool_names = [t.name for t in tools]

    expected = [
        "trace_dependency_path",
        "get_blast_radius",
        "inspect_incident_evidence",
        "compare_hypotheses",
        "simulate_graph_intervention",
    ]
    for name in expected:
        assert name in tool_names, f"Missing MCP tool: {name}"

    tool_map = {t.name: t for t in tools}
    # Verify parameter schemas
    assert "source_service_id" in tool_map["trace_dependency_path"].input_schema["properties"]
    assert "target_service_id" in tool_map["trace_dependency_path"].input_schema["properties"]
    assert "service_id" in tool_map["get_blast_radius"].input_schema["properties"]
    assert "incident_id" in tool_map["inspect_incident_evidence"].input_schema["properties"]
    assert "incident_id" in tool_map["compare_hypotheses"].input_schema["properties"]
    assert "action_type" in tool_map["simulate_graph_intervention"].input_schema["properties"]


# -----------------------------------------------------------------------------
# Tool 1: trace_dependency_path Tests
# -----------------------------------------------------------------------------

def test_trace_dependency_path_success():
    """Verify directed path discovery between real nodes in FalkorDB."""
    res = trace_dependency_path_service(
        source_service_id="nexus-edge-gateway",
        target_service_id="payment-core",
        max_depth=3,
    )
    assert res["path_found"] is True
    assert res["total_paths"] >= 1
    p = res["paths"][0]
    assert p["node_ids"][0] == "nexus-edge-gateway"
    assert p["node_ids"][-1] == "payment-core"
    assert "DEPENDS_ON" in p["rel_types"]


def test_trace_dependency_path_no_path():
    """Verify distinguishing non-existent path between disconnected / reverse nodes."""
    res = trace_dependency_path_service(
        source_service_id="payment-db-cluster",
        target_service_id="nexus-edge-gateway",
        max_depth=3,
    )
    assert res["path_found"] is False
    assert res["total_paths"] == 0
    assert res["paths"] == []


def test_trace_dependency_path_unknown_node():
    """Verify proper error on unknown source or target."""
    with pytest.raises(ValueError, match="does not exist in FalkorDB"):
        trace_dependency_path_service("nonexistent-service", "payment-core")

    with pytest.raises(ValueError, match="does not exist in FalkorDB"):
        trace_dependency_path_service("payment-core", "nonexistent-target")


def test_trace_dependency_path_depth_clamping():
    """Verify depth clamping enforces bounds 1..5."""
    res = trace_dependency_path_service("nexus-edge-gateway", "payment-core", max_depth=99)
    assert res["max_depth_enforced"] == 5

    res_min = trace_dependency_path_service("nexus-edge-gateway", "payment-core", max_depth=-5)
    assert res_min["max_depth_enforced"] == 1


# -----------------------------------------------------------------------------
# Tool 2: get_blast_radius Tests
# -----------------------------------------------------------------------------

def test_get_blast_radius_success():
    """Verify blast radius traversal follows downstream dependent directions."""
    res = get_blast_radius_service("payment-db-cluster", max_depth=3)
    assert res["total_affected_downstream_services"] >= 3
    aff_ids = [s["service_id"] for s in res["affected_services"]]
    assert "payment-core" in aff_ids

    # Hop distance should be positive and sorted
    for s in res["affected_services"]:
        assert s["hop_distance"] >= 1


def test_get_blast_radius_leaf_node():
    """Verify leaf service with no dependents returns clean empty list."""
    res = get_blast_radius_service("nexus-edge-gateway", max_depth=3)
    assert res["total_affected_downstream_services"] == 0
    assert res["affected_services"] == []


def test_get_blast_radius_unknown_node():
    """Verify unknown node raises informative ValueError."""
    with pytest.raises(ValueError, match="does not exist in FalkorDB"):
        get_blast_radius_service("nonexistent-service")


# -----------------------------------------------------------------------------
# Tool 3: inspect_incident_evidence Tests
# -----------------------------------------------------------------------------

def test_inspect_incident_evidence_success():
    """Verify incident evidence retrieval and transparent epistemic labeling."""
    res = inspect_incident_evidence_service("INC-2026-8821")
    assert res["incident"]["id"] == "INC-2026-8821"
    assert res["incident"]["severity"] == "SEV1"
    assert len(res["alerts"]) >= 1
    assert len(res["metric_observations"]) >= 1

    # Verify epistemic tags
    assert res["alerts"][0]["epistemic_status"] == "OBSERVED"
    assert res["metric_observations"][0]["epistemic_status"] == "OBSERVED"


def test_inspect_incident_evidence_unknown_id():
    """Verify error on unknown incident ID."""
    with pytest.raises(ValueError, match="not found in FalkorDB"):
        inspect_incident_evidence_service("INC-UNKNOWN-9999")


# -----------------------------------------------------------------------------
# Tool 4: compare_hypotheses Tests
# -----------------------------------------------------------------------------

def test_compare_hypotheses_consistency():
    """Verify deterministic scoring formula consistency and factor reasons."""
    res = asyncio.run(compare_hypotheses_service("INC-2026-8821"))
    assert res["incident_id"] == "INC-2026-8821"
    assert len(res["hypotheses"]) >= 2

    top = res["top_hypothesis"]
    assert top is not None
    assert top["rank"] == 1
    assert 0.05 <= top["deterministic_score"] <= 0.95
    assert len(top["score_factors"]) >= 4

    # Factors must have reasons
    for f in top["score_factors"]:
        assert f["reason"] is not None and len(f["reason"]) > 0


# -----------------------------------------------------------------------------
# Tool 5: simulate_graph_intervention Tests
# -----------------------------------------------------------------------------

def test_simulate_graph_intervention_safety_and_diffs():
    """Verify isolated graph copy, hypothesis rank shift, and zero baseline mutation."""
    baseline_graph = db_client.get_graph("traceforge")

    # Count edges in baseline before simulation
    before_edge_res = baseline_graph.ro_query("MATCH ()-[r:DEPENDS_ON]->() RETURN count(r)")
    baseline_edges_before = before_edge_res.result_set[0][0]

    # Run simulation
    sim = asyncio.run(simulate_graph_intervention_service(
        incident_id="INC-2026-8821",
        action_type="remove_dependency",
        source_id="payment-core",
        target_id="payment-db-cluster",
        justification="MCP verification test",
    ))

    assert sim["simulation"] is True
    assert sim["production_mutated"] is False
    assert sim["experiment_id"].startswith("exp_")
    assert sim["blast_radius_diff"]["service_id"] == "payment-db-cluster"
    assert sim["blast_radius_diff"]["baseline_downstream_count"] > sim["blast_radius_diff"]["experiment_downstream_count"]
    assert "payment-core" in sim["blast_radius_diff"]["severed_services"]

    # Verify baseline graph is 100% pristine and unmodified
    after_edge_res = baseline_graph.ro_query("MATCH ()-[r:DEPENDS_ON]->() RETURN count(r)")
    baseline_edges_after = after_edge_res.result_set[0][0]
    assert baseline_edges_before == baseline_edges_after, "Baseline graph was illegally mutated!"

    # Verify experiment graph was cleaned up reliably
    exp_graph_name = f"traceforge_{sim['experiment_id']}"
    client = db_client.get_client()
    active_graphs = client.execute_command("GRAPH.LIST")
    assert exp_graph_name not in active_graphs, f"Experiment graph {exp_graph_name} was not cleaned up!"


def test_simulate_graph_intervention_invalid_action():
    """Verify invalid or unsupported intervention types are rejected safely."""
    with pytest.raises(ValueError, match="Unsupported action_type"):
        asyncio.run(simulate_graph_intervention_service(
            incident_id="INC-2026-8821",
            action_type="reboot_datacenter",
            source_id="payment-core",
        ))
