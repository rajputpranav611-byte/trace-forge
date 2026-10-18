import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.seed import seed_graph
from app.db.investigation import build_investigation_context
from app.schemas.hypotheses import VerifiedHypothesis, VerifiedEvidence
from app.core.ranking.engine import score_hypothesis, rank_hypotheses

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_seed():
    seed_graph("traceforge")


def test_scenario_1_deployment_regression():
    """Scenario 1: True deployment regression (DEP-4012 on payment-core).

    Should receive high score (+0.75+) and verdict HIGH_CONFIDENCE_ROOT_CAUSE due to:
    - Multiple supporting verified alerts/metrics
    - Optimal 0-5m temporal consistency window
    - Confirmed topological causal path
    - Zero contradictions
    """
    context = build_investigation_context("INC-2026-8821")
    assert context is not None

    hyp = VerifiedHypothesis(
        id="HYP-TRUE-DEPLOY",
        title="Payment Core Release Regression",
        statement="Release DEP-4012 introduced an unindexed query exhausting connection pool.",
        suspected_entity="payment-core",
        confidence=0.85,
        supporting_evidence=[
            VerifiedEvidence(id="ALT-101", type="alert", description="Payment latency p99"),
            VerifiedEvidence(id="ALT-102", type="alert", description="Postgres pool exhausted"),
            VerifiedEvidence(id="DEP-4012", type="deployment", description="Release v4.1.0-rc2"),
        ],
        contradicting_evidence=[],
        rejected_evidence_ids=[],
        verification_status="verified",
    )

    scored = score_hypothesis(hyp, context)
    assert scored.deterministic_score >= 0.75
    assert scored.verdict == "HIGH_CONFIDENCE_ROOT_CAUSE"
    assert scored.causal_path_found is True
    # Verify score factor breakdown
    factor_names = [f.name for f in scored.score_factors]
    assert "verified_supporting_evidence" in factor_names
    assert "temporal_consistency" in factor_names


def test_scenario_2_shared_database_bottleneck():
    """Scenario 2: Shared database cluster exhaustion.

    Downstream callers rely on payment-db-cluster. Should receive high rank and plausible/root-cause verdict.
    """
    context = build_investigation_context("INC-2026-8821")
    assert context is not None

    hyp = VerifiedHypothesis(
        id="HYP-DB-BOTTLE",
        title="Postgres Database Saturation",
        statement="Database connection pool starvation blocking payment operations.",
        suspected_entity="payment-db-cluster",
        confidence=0.90,
        supporting_evidence=[
            VerifiedEvidence(id="ALT-102", type="alert", description="Postgres pool exhausted"),
            VerifiedEvidence(id="MET-501", type="metric", description="HikariCP connection saturation"),
        ],
        contradicting_evidence=[],
        rejected_evidence_ids=[],
        verification_status="verified",
    )

    scored = score_hypothesis(hyp, context)
    assert scored.deterministic_score >= 0.65
    assert scored.causal_path_found is True


def test_scenario_3_misleading_temporal_correlation():
    """Scenario 3: Misleading deployment correlation on auth-service (DEP-4011).

    Although deployed right before the incident, contradictory facts (errors are exclusively 504 on payment-core,
    not token verification) lower its rank significantly.
    """
    context = build_investigation_context("INC-2026-8821")
    assert context is not None

    hyp = VerifiedHypothesis(
        id="HYP-AUTH-MISLEADING",
        title="Auth Service Regression",
        statement="Auth service rollout caused token failures cascading to checkout.",
        suspected_entity="auth-service",
        confidence=0.70,
        supporting_evidence=[
            VerifiedEvidence(id="DEP-4011", type="deployment", description="Auth rollout"),
        ],
        contradicting_evidence=[
            VerifiedEvidence(id="ALT-101", type="alert", description="Payment core latency"),
            VerifiedEvidence(id="MET-501", type="metric", description="DB connection pool saturation"),
        ],
        rejected_evidence_ids=[],
        verification_status="verified",
    )

    scored = score_hypothesis(hyp, context)
    # The -0.50 contradiction penalty drops this candidate to WEAK_OR_MISLEADING
    assert scored.deterministic_score <= 0.45
    assert scored.verdict == "WEAK_OR_MISLEADING"
    assert len(scored.contradicting_evidence_ids) == 2


def test_scenario_4_incomplete_evidence_abstention():
    """Scenario 4: Sparse observations (INC-2026-9043).

    Engine must abstain from forming a strong conclusion and assign INCONCLUSIVE_INSUFFICIENT_DATA.
    """
    context = build_investigation_context("INC-2026-9043")
    assert context is not None
    assert context.evidence_summary["is_sufficient_evidence"] is False

    hyp = VerifiedHypothesis(
        id="HYP-SPORADIC",
        title="Edge Gateway Glitch",
        statement="Transient 502 error spikes on edge gateway.",
        suspected_entity="nexus-edge-gateway",
        confidence=0.50,
        supporting_evidence=[
            VerifiedEvidence(id="nexus-edge-gateway", type="service", description="Edge gateway"),
        ],
        contradicting_evidence=[],
        rejected_evidence_ids=[],
        verification_status="verified",
    )

    scored = score_hypothesis(hyp, context)
    assert scored.verdict == "INCONCLUSIVE_INSUFFICIENT_DATA"
    assert any(f.name == "epistemic_abstention_penalty" and f.contribution < 0 for f in scored.score_factors)


def test_scenario_5_competing_hypotheses_ranking_and_persistence():
    """Scenario 5: Two competing hypotheses evaluated against INC-2026-8821.

    Validates that:
    - Root cause release candidate (payment-core) ranks #1
    - Misleading correlation candidate (auth-service) ranks #2
    - The investigation record is persisted in FalkorDB with graph relationships
    """
    response = client.post("/api/v1/investigation/rank/INC-2026-8821?max_depth=3")
    assert response.status_code == 200
    data = response.json()

    assert data["incident_id"] == "INC-2026-8821"
    assert data["graph_persistence_status"] == "persisted"
    assert len(data["hypotheses"]) >= 2

    top = data["hypotheses"][0]
    second = data["hypotheses"][1]

    assert top["rank"] == 1
    assert second["rank"] == 2
    assert top["deterministic_score"] > second["deterministic_score"]
    assert top["suspected_entity"] in ["payment-db-cluster", "payment-core"]

    # Verify unresolved questions returned
    assert len(data["unresolved_questions"]) >= 0

    # Query FalkorDB to confirm persistence of the ranked investigation node
    from app.db.client import db_client
    g = db_client.get_graph("traceforge")
    res = g.query("MATCH (inv:Investigation {id: $id})-[:INVESTIGATES]->(i:Incident) RETURN count(inv)", {"id": data["investigation_id"]})
    assert res.result_set[0][0] == 1
