import pytest
from app.db.seed import seed_graph
from app.core.orchestrator import orchestrator
from app.schemas.orchestration import InvestigationOrchestrationResponse


@pytest.fixture(scope="module", autouse=True)
def setup_seed():
    seed_graph()


@pytest.mark.anyio
async def test_adaptive_orchestration_payment_incident():
    """Validates that INC-2026-8821 triggers cascading payment dependency path tracing and counterfactual intervention."""
    res = await orchestrator.run_investigation("INC-2026-8821")
    assert isinstance(res, InvestigationOrchestrationResponse)
    assert res.incident_id == "INC-2026-8821"
    assert res.total_steps >= 4
    
    tool_sequence = [s.tool_name for s in res.steps]
    # For INC-2026-8821: starts with inspect_incident_evidence, then trace_dependency_path, get_blast_radius, compare_hypotheses, simulate_graph_intervention
    assert tool_sequence[0] == "inspect_incident_evidence"
    assert "trace_dependency_path" in tool_sequence
    assert "get_blast_radius" in tool_sequence
    assert "compare_hypotheses" in tool_sequence
    assert "simulate_graph_intervention" in tool_sequence
    assert res.intervention_simulated is True
    assert res.top_hypothesis_title is not None
    assert res.simulation_blast_reduction is not None
    assert res.simulation_blast_reduction > 0


@pytest.mark.anyio
async def test_adaptive_orchestration_kafka_incident():
    """Validates that INC-2026-7104 triggers blast radius of message bus and NO unnecessary intervention."""
    res = await orchestrator.run_investigation("INC-2026-7104")
    assert isinstance(res, InvestigationOrchestrationResponse)
    assert res.incident_id == "INC-2026-7104"
    
    tool_sequence = [s.tool_name for s in res.steps]
    assert tool_sequence[0] == "inspect_incident_evidence"
    # Adaptive difference: immediately computes blast radius on event-stream-kafka
    assert tool_sequence[1] == "get_blast_radius"
    assert "trace_dependency_path" in tool_sequence
    assert "compare_hypotheses" in tool_sequence
    # Because it is a resolved historical Kafka lag incident, no intervention is simulated
    assert "simulate_graph_intervention" not in tool_sequence
    assert res.intervention_simulated is False


@pytest.mark.anyio
async def test_orchestration_provenance_and_epistemics():
    """Validates that all steps have strict epistemic categorization and valid duration."""
    res = await orchestrator.run_investigation("INC-2026-8821")
    for step in res.steps:
        assert step.epistemic_status in ["OBSERVED", "INFERRED", "HISTORICAL", "SYNTHETIC", "SIMULATED"]
        assert step.status == "SUCCEEDED"
        assert step.duration_ms >= 0.0
        assert len(step.selection_rationale) > 10
        assert step.result_summary is not None
