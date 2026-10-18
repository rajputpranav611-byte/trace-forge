import json
import logging
from typing import Dict, Any, List
from app.schemas.investigation import InvestigationContextResponse
from app.schemas.hypotheses import RawHypothesis, LLMHypothesisOutput

logger = logging.getLogger("traceforge.llm.fallback")


def generate_deterministic_fallback_hypotheses(context: InvestigationContextResponse) -> LLMHypothesisOutput:
    """Deterministic, rule-based fallback generating competing hypotheses directly from graph context.

    Ensures TraceForge remains fully functional even when external LLM APIs fail, time out,
    or credentials are unset.
    """
    hypotheses: List[RawHypothesis] = []

    # Map candidate entities from alerts and metrics
    alerts = context.alerts
    metrics = context.metrics
    deployments = context.deployments
    affected_services = context.topology.affected_services
    edges = context.topology.dependency_edges

    # Check for database saturation / slow query patterns (e.g., INC-2026-8821)
    db_metrics = [m for m in metrics if "connection" in m.metric_name.lower() or "pool" in m.metric_name.lower()]
    db_alerts = [a for a in alerts if "db" in a.name.lower() or "postgres" in a.name.lower() or "pool" in a.name.lower()]

    root_deployments = [d for d in deployments if d.service_id == "payment-core" or "v4" in d.version]

    if db_metrics or db_alerts:
        supporting_ids = [a.id for a in db_alerts] + [m.id for m in db_metrics]
        if root_deployments:
            supporting_ids.append(root_deployments[0].id)

        hypotheses.append(
            RawHypothesis(
                id="HYP-01",
                title="Database Connection Pool Starvation & Saturation",
                statement="High connection pool saturation on backend database cluster causing cascading timeouts and 504 errors on upstream orchestrator.",
                suspected_entity="payment-db-cluster",
                confidence=0.88 if len(supporting_ids) >= 2 else 0.65,
                supporting_evidence_ids=supporting_ids,
                contradicting_evidence_ids=[],
                recommended_action="Rollback recent release via ArgoCD and verify connection pool metrics with runbook RBK-PAY-01",
            )
        )

    # Check for misleading deployment correlation (e.g. auth-service release)
    auth_deployments = [d for d in deployments if d.service_id == "auth-service"]
    auth_alerts = [a for a in alerts if a.service_id == "auth-service"]
    if auth_deployments:
        auth_dep = auth_deployments[0]
        supp_ids = [auth_dep.id] + [a.id for a in auth_alerts]
        contra_ids = [m.id for m in metrics if m.value > 0]  # Errors are database timeouts, not auth failures

        hypotheses.append(
            RawHypothesis(
                id="HYP-02",
                title="Candidate Release Regression (Auth Session Service)",
                statement=f"Deployment {auth_dep.id} ({auth_dep.version}) to {auth_dep.service_name} coincided with incident start, but downstream failures are predominantly latency timeouts on database calls.",
                suspected_entity=auth_dep.service_id,
                confidence=0.28,
                supporting_evidence_ids=supp_ids,
                contradicting_evidence_ids=contra_ids,
                recommended_action="Inspect token latency and verify whether errors cascade past auth gateway.",
            )
        )

    # Check for missing relationship or unknown root cause in sparse incidents
    if context.topology.missing_relationships_detected or not hypotheses:
        hypotheses.append(
            RawHypothesis(
                id="HYP-03",
                title="Uncataloged Dependency or External Transit Degradation",
                statement="Sporadic latency anomalies may originate from undocumented synchronous service dependencies or transient network transit blips.",
                suspected_entity=affected_services[0].id if affected_services else "unknown",
                confidence=0.35,
                supporting_evidence_ids=[a.id for a in alerts],
                contradicting_evidence_ids=[],
                recommended_action="Trace cross-service headers and confirm registration of runtime dependency catalog.",
            )
        )

    summary = (
        f"Deterministic rule engine analyzed {len(alerts)} alerts, {len(metrics)} statistical anomalies, "
        f"and {len(deployments)} candidate deployments across {len(affected_services)} affected services. "
        "Generated candidate theories for human inspection."
    )

    return LLMHypothesisOutput(
        hypotheses=hypotheses,
        reasoning_summary=summary,
    )
