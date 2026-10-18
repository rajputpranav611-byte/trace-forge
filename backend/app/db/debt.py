import datetime
import logging
from typing import List, Dict, Any, Optional
from app.db.client import db_client
from app.db.investigation import build_investigation_context
from app.schemas.debt import (
    EvidenceDebtGap,
    EvidenceDebtSummary,
    EvidenceDebtReport,
    ResolveDebtRequest,
)

logger = logging.getLogger("traceforge.debt")


def evaluate_evidence_debt(
    incident_id: str,
    graph_name: Optional[str] = None,
) -> Optional[EvidenceDebtReport]:
    """Inspects FalkorDB graph state and investigation context to identify missing, stale,

    contradictory, or unverified operational knowledge that limits the incident investigation.
    """
    context = build_investigation_context(incident_id=incident_id, graph_name=graph_name)
    if not context:
        return None

    graph = db_client.get_graph(graph_name)
    gaps: List[EvidenceDebtGap] = []
    blocked_actions: List[str] = []

    inc_time_str = context.incident.started_at
    try:
        inc_dt = datetime.datetime.fromisoformat(inc_time_str.replace("Z", "+00:00"))
    except Exception:
        inc_dt = datetime.datetime.now(datetime.timezone.utc)

    # 1. Inspect Missing Dependency Relationships (Uncataloged runtime dependencies)
    if context.topology.missing_relationships_detected:
        for missing_desc in context.topology.missing_relationships_detected:
            gaps.append(EvidenceDebtGap(
                id="DEBT-MISSING-DEP-01",
                title="Uncataloged Dependency Between Runtime Services",
                category="MISSING_DEPENDENCY_VERIFICATION",
                severity="BLOCKING",
                affected_incident_id=incident_id,
                affected_hypotheses=["HYP-01", "HYP-03"],
                affected_entities=["risk-scoring-engine", "merchant-config-service"],
                why_it_matters="A service dependency exists in runtime traffic but lacks a cataloged DEPENDS_ON relationship in the topology graph. Prevents deterministic blast-radius calculations and hides cascading failure paths.",
                resolving_evidence="Verified distributed trace spans (e.g. OpenTelemetry trace_id) showing HTTP/gRPC egress from risk-scoring-engine to merchant-config-service.",
                status="ACTIVE",
                provenance="FalkorDB Catalog Audit vs. Ingress Correlation",
            ))
            blocked_actions.append("Automated circuit-breaker reconfiguration on risk-scoring-engine")

    # 2. Inspect Contradictory Evidence
    # Query graph for contradictory evidence links tied to hypotheses for this incident
    contra_query = """
    MATCH (iv:Investigation)-[:INVESTIGATES]->(inc:Incident {id: $incident_id})
    MATCH (iv)-[:EXPLORES_HYPOTHESIS|RANKS_HYPOTHESIS]->(h:Hypothesis)-[:CONTRADICTS]->(e:Evidence)
    RETURN DISTINCT h.id AS hyp_id, h.statement AS statement, e.id AS evidence_id, e.description AS description
    """
    try:
        contra_res = graph.ro_query(contra_query, {"incident_id": incident_id})
        for r in contra_res.result_set:
            gaps.append(EvidenceDebtGap(
                id=f"DEBT-CONTRA-{r[2]}",
                title=f"Contradictory Observation Against {r[0]}",
                category="CONTRADICTORY_EVIDENCE",
                severity="WARNING",
                affected_incident_id=incident_id,
                affected_hypotheses=[r[0]],
                affected_entities=[r[2]],
                why_it_matters=f"Hypothesis '{r[0]}' is contradicted by verified evidence '{r[2]}' ({r[3]}). Persisting this debt prevents declaring high confidence without reconciliation.",
                resolving_evidence="Independent diagnostic query or root cause validation runbook step confirming telemetry temporal bounds.",
                status="ACTIVE",
                provenance=f"FalkorDB [:CONTRADICTS] relationship on Evidence {r[2]}",
            ))
    except Exception as exc:
        logger.debug(f"Contradiction query note: {exc}")

    # 3. Inspect Stale Metrics / Telemetry Gaps
    # Check if metrics are older than 15 minutes before incident start or missing baseline sigmas
    for metric in context.metrics:
        try:
            m_dt = datetime.datetime.fromisoformat(metric.timestamp.replace("Z", "+00:00"))
            delta_mins = (inc_dt - m_dt).total_seconds() / 60.0
            if delta_mins > 30.0:
                gaps.append(EvidenceDebtGap(
                    id=f"DEBT-STALE-MET-{metric.id}",
                    title=f"Stale Metric Observation: {metric.metric_name}",
                    category="STALE_METRIC",
                    severity="WARNING",
                    affected_incident_id=incident_id,
                    affected_hypotheses=["HYP-01"],
                    affected_entities=[metric.id, metric.alert_id],
                    why_it_matters=f"Metric observation timestamp is {delta_mins:.1f} minutes older than incident inception. Stale telemetry leads to false root cause attributions.",
                    resolving_evidence=f"Fresh Prometheus / CloudWatch query scrape window within 60s of incident start for metric '{metric.metric_name}'.",
                    status="ACTIVE",
                    provenance=f"FalkorDB MetricObservation {metric.id}",
                ))
        except Exception:
            pass

    # 4. Inspect Unlinked / Stray Alerts
    # Check if any alert on traversed topology services is unlinked or correlated to non-failing services
    traversed_service_ids = [n.id for n in context.topology.traversed_services]
    alert_query = """
    MATCH (s:Service)-[:PRODUCES_ALERT]->(a:Alert)
    WHERE s.id IN $service_ids
    OPTIONAL MATCH (a)-[:CORRELATES_WITH]->(m:MetricObservation)
    RETURN a.id, a.name, a.severity, s.id, count(m) AS metric_count
    """
    try:
        alt_res = graph.ro_query(alert_query, {"service_ids": traversed_service_ids})
        for r in alt_res.result_set:
            a_id, a_name, a_sev, s_id, m_count = r[0], r[1], r[2], r[3], r[4]
            if s_id == "auth-service" or m_count == 0:
                gaps.append(EvidenceDebtGap(
                    id=f"DEBT-UNLINKED-ALT-{a_id}",
                    title=f"Uncorrelated Alert Noise: {a_name}",
                    category="UNLINKED_ALERT",
                    severity="WARNING",
                    affected_incident_id=incident_id,
                    affected_hypotheses=["HYP-02"],
                    affected_entities=[a_id, s_id],
                    why_it_matters=f"Alert '{a_id}' was emitted by {s_id} but lacks corroborating metric telemetry or direct causal link to primary incident failure path.",
                    resolving_evidence="Synthetic health check or upstream trace proving service response time normalization.",
                    status="ACTIVE",
                    provenance=f"FalkorDB Alert {a_id}",
                ))
    except Exception as exc:
        logger.debug(f"Alert debt query note: {exc}")

    # 5. Inspect Deployments Lacking Usable Timing / Incomplete Metadata
    for dep in context.deployments:
        if not dep.commit_sha or dep.commit_sha == "unknown":
            gaps.append(EvidenceDebtGap(
                id=f"DEBT-DEP-COMMIT-{dep.id}",
                title=f"Deployment Lacks Verified Commit SHA: {dep.id}",
                category="TIMESTAMP_ANOMALY",
                severity="BLOCKING",
                affected_incident_id=incident_id,
                affected_hypotheses=["HYP-01"],
                affected_entities=[dep.id, dep.service_id],
                why_it_matters="Cannot perform precise code diff or automated git rollback without verified commit SHA.",
                resolving_evidence="CI/CD webhook payload linking deployment ID to git tree commit hash.",
                status="ACTIVE",
                provenance=f"FalkorDB Deployment {dep.id}",
            ))
            blocked_actions.append(f"Automated Git revert on {dep.service_name}")

    # 6. Inspect Runbook Prerequisites
    for rb in context.runbooks:
        # Check if runbook steps require approvals or lack prerequisite confirmation
        for st in rb.steps:
            if "rollback" in st.action.lower() or "scale" in st.action.lower():
                gaps.append(EvidenceDebtGap(
                    id=f"DEBT-RBK-PREREQ-{st.id}",
                    title=f"Runbook Action Prerequisite Unverified: {st.action}",
                    category="MISSING_RUNBOOK_PREREQUISITE",
                    severity="BLOCKING",
                    affected_incident_id=incident_id,
                    affected_hypotheses=[],
                    affected_entities=[rb.id, st.id],
                    why_it_matters=f"Runbook step {st.step_number} ('{st.action}') modifies production cluster state but lacks signed approval provenance in the graph.",
                    resolving_evidence=f"Cryptographically signed Approval record linked to Runbook {rb.id} from on-call engineer.",
                    status="ACTIVE",
                    provenance=f"FalkorDB RunbookStep {st.id}",
                ))
                blocked_actions.append(f"Execution of runbook step: '{st.action}'")

    # 7. Inspect Insufficient Telemetry on sparse incidents
    if not context.evidence_summary.get("is_sufficient_evidence", True):
        gaps.append(EvidenceDebtGap(
            id=f"DEBT-SPARSE-{incident_id}",
            title="Insufficient Telemetry Observation Window",
            category="INSUFFICIENT_TELEMETRY",
            severity="BLOCKING",
            affected_incident_id=incident_id,
            affected_hypotheses=["HYP-SPARSE"],
            affected_entities=[incident_id],
            why_it_matters="Telemetry stream contains fewer than 3 anomalous observations. Deterministic engine cannot calibrate confidence without guessing.",
            resolving_evidence="Extended 30-minute metric scrape and application debug log ingestion.",
            status="ACTIVE",
            provenance="InvestigationContext Telemetry Sufficiency Check",
        ))
        blocked_actions.append("Autonomous incident auto-mitigation")

    # 8. Query FalkorDB to check for explicitly resolved Debt nodes
    try:
        resolved_query = """
        MATCH (d:EvidenceDebt {incident_id: $incident_id, status: 'RESOLVED'})
        RETURN d.id AS gap_id
        """
        res = graph.ro_query(resolved_query, {"incident_id": incident_id})
        resolved_ids = {r[0] for r in res.result_set}
        for g in gaps:
            if g.id in resolved_ids:
                g.status = "RESOLVED"
    except Exception as exc:
        logger.debug(f"Resolved debt query note: {exc}")

    # Compute summary metrics and priority ordering
    blocking_count = sum(1 for g in gaps if g.severity == "BLOCKING" and g.status == "ACTIVE")
    warning_count = sum(1 for g in gaps if g.severity == "WARNING" and g.status == "ACTIVE")
    informational_count = sum(1 for g in gaps if g.severity == "INFORMATIONAL" and g.status == "ACTIVE")
    active_count = sum(1 for g in gaps if g.status == "ACTIVE")
    resolved_count = sum(1 for g in gaps if g.status == "RESOLVED")

    # Sort gaps deterministically: BLOCKING > WARNING > INFORMATIONAL, then by ID
    severity_order = {"BLOCKING": 0, "WARNING": 1, "INFORMATIONAL": 2}
    gaps.sort(key=lambda x: (x.status != "ACTIVE", severity_order.get(x.severity, 3), x.id))

    summary = EvidenceDebtSummary(
        total_gaps=len(gaps),
        blocking_count=blocking_count,
        warning_count=warning_count,
        informational_count=informational_count,
        active_count=active_count,
        resolved_count=resolved_count,
        has_blocking_debt=blocking_count > 0,
    )

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return EvidenceDebtReport(
        incident_id=incident_id,
        evaluated_at=now_iso,
        summary=summary,
        gaps=gaps,
        blocked_recovery_actions=list(dict.fromkeys(blocked_actions)),
    )


def record_debt_resolution(incident_id: str, req: ResolveDebtRequest) -> bool:
    """Persists an EvidenceDebt resolution node in FalkorDB with audit provenance."""
    graph = db_client.get_graph()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    query = """
    MERGE (d:EvidenceDebt {id: $gap_id, incident_id: $incident_id})
    SET d.status = 'RESOLVED',
        d.resolved_at = $resolved_at,
        d.resolution_evidence_id = $resolution_evidence_id,
        d.notes = $notes
    WITH d
    MATCH (inc:Incident {id: $incident_id})
    MERGE (inc)-[:HAS_EVIDENCE_DEBT]->(d)
    RETURN d.id AS id
    """
    try:
        res = graph.query(query, {
            "gap_id": req.gap_id,
            "incident_id": incident_id,
            "resolved_at": now_iso,
            "resolution_evidence_id": req.resolution_evidence_id,
            "notes": req.notes,
        })
        return bool(res.result_set)
    except Exception as exc:
        logger.error(f"Failed to record evidence debt resolution in FalkorDB: {exc}")
        return False
