import datetime
import logging
from typing import List, Dict, Any, Optional
from app.db.client import db_client
from app.schemas.memory import (
    EpistemicProvenance,
    HistoricalInvestigationRecord,
    HistoricalComparison,
    InvestigationMemoryResponse,
    RunbookPrerequisiteMatch,
)
from app.db.investigation import build_investigation_context

logger = logging.getLogger("traceforge.memory")


def list_historical_investigations(
    graph_name: Optional[str] = None,
    limit: int = 25,
) -> List[HistoricalInvestigationRecord]:
    """Retrieves all historical investigations with verified outcomes, hypotheses,

    and provenance directly from FalkorDB.
    """
    graph = db_client.get_graph(graph_name)
    query = """
    MATCH (inv:Investigation)-[:INVESTIGATES]->(inc:Incident)
    OPTIONAL MATCH (inv)-[:RANKS_HYPOTHESIS]->(h:Hypothesis)
    OPTIONAL MATCH (h)-[:SUPPORTED_BY]->(e:Evidence)
    OPTIONAL MATCH (inc)-[:RESOLVED_BY]->(ra:RecoveryAction)
    OPTIONAL MATCH (inc)-[:HAS_RECOVERY_PROPOSAL]->(rp:RecoveryProposal)-[:RESULTED_IN]->(sr:SimulationResult)
    RETURN inv.id AS inv_id,
           inc.id AS inc_id,
           inc.title AS inc_title,
           inc.severity AS inc_severity,
           inc.status AS inc_status,
           inc.started_at AS started_at,
           inv.ranked_at AS ranked_at,
           inv.abstained AS abstained,
           collect(DISTINCT {
               id: h.id,
               title: h.title,
               score: h.score,
               rank: h.rank,
               verdict: h.verdict
           }) AS hypotheses,
           collect(DISTINCT e.id) AS evidence_ids,
           collect(DISTINCT {
               id: ra.id,
               action_type: ra.action_type,
               status: ra.status,
               executed_at: ra.executed_at
           }) AS real_recovery_actions,
           collect(DISTINCT {
               id: rp.id,
               action_type: rp.action_type,
               state: rp.state,
               success: sr.success,
               executed_at: sr.executed_at
           }) AS simulated_actions
    ORDER BY inv.ranked_at DESC
    LIMIT $limit
    """
    res = graph.ro_query(query, {"limit": limit})
    records: List[HistoricalInvestigationRecord] = []

    for row in res.result_set:
        inv_id, inc_id, title, sev, status, started, ranked_at, abstained, raw_hyps, evi_ids, real_actions, sim_actions = row
        
        valid_hyps = [h for h in raw_hyps if h and h.get("id")]
        # Sort hypotheses by rank if available
        valid_hyps.sort(key=lambda x: x.get("rank") or 999)
        top_h = valid_hyps[0] if valid_hyps else {}

        filtered_real = [a for a in real_actions if a and a.get("id") and a.get("status") == "completed"]
        filtered_sim = [s for s in sim_actions if s and s.get("id")]

        provenance = EpistemicProvenance(
            source_type="graph_node",
            source_id=f"Investigation:{inv_id}",
            verified=bool(filtered_real),
            epistemic_status="VERIFIED_OBSERVATION" if filtered_real else ("SIMULATED_DRY_RUN" if filtered_sim else "UNVERIFIED_CLAIM"),
            notes=f"Investigation memory backed by FalkorDB for {inc_id}",
        )

        records.append(HistoricalInvestigationRecord(
            investigation_id=inv_id or f"INV-{inc_id}",
            incident_id=inc_id,
            incident_title=title or "Untitled Incident",
            incident_severity=sev or "UNKNOWN",
            incident_status=status or "unknown",
            started_at=started or "",
            ranked_at=ranked_at or started or "",
            abstained=bool(abstained),
            top_hypothesis_title=top_h.get("title"),
            top_hypothesis_score=top_h.get("score"),
            top_hypothesis_verdict=top_h.get("verdict"),
            hypotheses_count=len(valid_hyps),
            supporting_evidence_ids=[eid for eid in evi_ids if eid],
            unresolved_questions=[],
            verified_recovery_actions=filtered_real,
            simulated_outcomes=filtered_sim,
            evidence_gaps=[],
            provenance=provenance,
        ))

    # Also check for seeded completed incidents like INC-2026-7104 that may have resolution without explicit Ranked Investigation node
    existing_inc_ids = {r.incident_id for r in records}
    fallback_query = """
    MATCH (inc:Incident)
    WHERE NOT inc.id IN $existing_inc_ids
    OPTIONAL MATCH (inc)-[:AFFECTS]->(s:Service)
    OPTIONAL MATCH (inc)-[:RESOLVED_BY]->(ra:RecoveryAction)
    OPTIONAL MATCH (inc)-[:HAS_RECOVERY_PROPOSAL]->(rp:RecoveryProposal)-[:RESULTED_IN]->(sr:SimulationResult)
    RETURN inc.id AS inc_id,
           inc.title AS title,
           inc.severity AS sev,
           inc.status AS status,
           inc.started_at AS started_at,
           collect(DISTINCT {
               id: ra.id,
               action_type: ra.action_type,
               status: ra.status,
               executed_at: ra.executed_at
           }) AS real_actions,
           collect(DISTINCT {
               id: rp.id,
               action_type: rp.action_type,
               state: rp.state,
               success: sr.success,
               executed_at: sr.executed_at
           }) AS sim_actions
    ORDER BY inc.started_at DESC
    LIMIT 10
    """
    fb_res = graph.ro_query(fallback_query, {"existing_inc_ids": list(existing_inc_ids) if existing_inc_ids else ["NONE"]})
    for fb_row in fb_res.result_set:
        f_inc_id, f_title, f_sev, f_status, f_started, f_real, f_sim = fb_row
        valid_real = [a for a in f_real if a and a.get("id")]
        valid_sim = [s for s in f_sim if s and s.get("id")]
        records.append(HistoricalInvestigationRecord(
            investigation_id=f"HIST-{f_inc_id}",
            incident_id=f_inc_id,
            incident_title=f_title or "Untitled Incident",
            incident_severity=f_sev or "UNKNOWN",
            incident_status=f_status or "unknown",
            started_at=f_started or "",
            ranked_at=f_started or "",
            abstained=False,
            top_hypothesis_title="Historical precedent from system archive",
            top_hypothesis_score=0.90 if valid_real else 0.50,
            top_hypothesis_verdict="HISTORICAL_ARCHIVE",
            hypotheses_count=1 if valid_real else 0,
            supporting_evidence_ids=[],
            unresolved_questions=[],
            verified_recovery_actions=valid_real,
            simulated_outcomes=valid_sim,
            evidence_gaps=[],
            provenance=EpistemicProvenance(
                source_type="graph_node",
                source_id=f"Incident:{f_inc_id}",
                verified=bool(valid_real),
                epistemic_status="VERIFIED_OBSERVATION" if valid_real else "UNVERIFIED_CLAIM",
                notes="Archived operational incident precedent in FalkorDB",
            ),
        ))

    return records


def retrieve_and_compare_historical_memory(
    current_incident_id: str,
    max_depth: int = 3,
    graph_name: Optional[str] = None,
) -> InvestigationMemoryResponse:
    """Orchestrates historical memory comparison for a given active incident:

    1. Retrieves relevant historical incidents through graph dependency relationships.
    2. Compares previous incident evidence with the current incident.
    3. Identifies concrete similarities and differences.
    4. Retrieves previously verified outcomes (distinguishing verified real vs simulated).
    5. Checks runbook prerequisites satisfaction on the current incident.
    6. Explains why a historical case is relevant or not relevant.
    """
    current_ctx = build_investigation_context(current_incident_id, max_depth=max_depth, graph_name=graph_name)
    if not current_ctx:
        raise ValueError(f"Incident '{current_incident_id}' not found in graph.")

    curr_affected_svcs = [s.id for s in current_ctx.topology.affected_services]
    curr_traversed_svcs = [s.id for s in current_ctx.topology.traversed_services]
    curr_all_svcs = set(curr_affected_svcs + curr_traversed_svcs)

    curr_alert_names = {a.name for a in current_ctx.alerts}
    curr_alert_sources = {a.source for a in current_ctx.alerts}
    curr_metrics = {m.metric_name for m in current_ctx.metrics}

    graph = db_client.get_graph(graph_name)

    # 1. Traverse all historical incidents in FalkorDB
    hist_query = """
    MATCH (h_inc:Incident)
    WHERE h_inc.id <> $curr_inc_id
    OPTIONAL MATCH (h_inc)-[:AFFECTS]->(s:Service)
    OPTIONAL MATCH (s)-[:PRODUCES_ALERT]->(a:Alert)
    OPTIONAL MATCH (a)-[:CORRELATES_WITH]->(m:MetricObservation)
    OPTIONAL MATCH (h_inc)-[:RESOLVED_BY]->(ra:RecoveryAction)
    OPTIONAL MATCH (h_inc)-[:HAS_RECOVERY_PROPOSAL]->(rp:RecoveryProposal)-[:RESULTED_IN]->(sr:SimulationResult)
    OPTIONAL MATCH (h_inv:Investigation)-[:INVESTIGATES]->(h_inc)
    RETURN h_inc.id AS id,
           h_inc.title AS title,
           h_inc.severity AS severity,
           h_inc.status AS status,
           h_inc.started_at AS started_at,
           h_inc.summary AS summary,
           collect(DISTINCT h_inv.id) AS inv_ids,
           collect(DISTINCT s.id) AS affected_services,
           collect(DISTINCT {
               id: a.id,
               name: a.name,
               source: a.source,
               service_id: s.id
           }) AS alerts,
           collect(DISTINCT {
               id: m.id,
               metric_name: m.metric_name,
               value: m.value
           }) AS metrics,
           collect(DISTINCT {
               id: ra.id,
               action_type: ra.action_type,
               status: ra.status,
               executed_at: ra.executed_at
           }) AS real_recovery_actions,
           collect(DISTINCT {
               id: rp.id,
               action_type: rp.action_type,
               state: rp.state,
               success: sr.success,
               executed_at: sr.executed_at
           }) AS sim_actions
    """
    res = graph.ro_query(hist_query, {"curr_inc_id": current_incident_id})

    comparisons: List[HistoricalComparison] = []

    for row in res.result_set:
        h_id, h_title, h_sev, h_status, h_started, h_summary, h_inv_ids, h_svcs, h_alerts, h_metrics, h_real_acts, h_sim_acts = row
        h_inv_id = h_inv_ids[0] if (h_inv_ids and h_inv_ids[0]) else None

        h_svc_set = set([s for s in h_svcs if s])
        common_svcs = list(curr_all_svcs.intersection(h_svc_set))
        common_direct = list(set(curr_affected_svcs).intersection(h_svc_set))

        valid_h_alerts = [a for a in h_alerts if a and a.get("id")]
        valid_h_metrics = [m for m in h_metrics if m and m.get("id")]
        h_alert_names = {a["name"] for a in valid_h_alerts}
        h_metric_names = {m["metric_name"] for m in valid_h_metrics}

        # Similarities
        similarities: List[str] = []
        if common_direct:
            similarities.append(f"Direct affected service overlap: {', '.join(common_direct)}")
        elif common_svcs:
            similarities.append(f"Topological dependency overlap: {', '.join(common_svcs)}")

        matching_alert_names = curr_alert_names.intersection(h_alert_names)
        if matching_alert_names:
            similarities.append(f"Shared alert patterns: {', '.join(matching_alert_names)}")

        matching_metrics = curr_metrics.intersection(h_metric_names)
        if matching_metrics:
            similarities.append(f"Correlated metric signatures: {', '.join(matching_metrics)}")

        # Differences
        differences: List[str] = []
        unique_curr_svcs = set(curr_affected_svcs) - h_svc_set
        if unique_curr_svcs:
            differences.append(f"Current incident uniquely impacts: {', '.join(unique_curr_svcs)}")

        unique_hist_svcs = h_svc_set - curr_all_svcs
        if unique_hist_svcs:
            differences.append(f"Historical incident impacted unrelated services: {', '.join(unique_hist_svcs)}")

        unique_curr_alerts = curr_alert_names - h_alert_names
        if unique_curr_alerts:
            differences.append(f"Current incident exhibits distinct alerts: {', '.join(list(unique_curr_alerts)[:3])}")

        # Relevance scoring logic (transparent and deterministic)
        relevance_score = 0.0
        relevance_reasons: List[str] = []

        if common_direct:
            relevance_score += 0.50
            relevance_reasons.append("directly impacts the same primary tier-1 service")
        elif common_svcs:
            relevance_score += 0.30
            relevance_reasons.append("connected through multi-hop topological service dependencies")

        if matching_alert_names:
            relevance_score += 0.25
            relevance_reasons.append("shares alert signatures")

        if matching_metrics:
            relevance_score += 0.15
            relevance_reasons.append("shares telemetry metric anomalies")

        relevance_score = min(1.0, round(relevance_score, 2))
        is_relevant = relevance_score >= 0.25

        if is_relevant:
            relevance_explanation = f"Relevant (Score {relevance_score:.2f}): Historical case {h_id} {' and '.join(relevance_reasons)}."
        else:
            relevance_explanation = (
                f"Not Relevant (Score {relevance_score:.2f}): Historical case {h_id} involves distinct services ({', '.join(list(h_svc_set)[:2]) or 'none'}) "
                "with no shared topology or correlated alert telemetry."
            )

        # 4. Verified outcomes: filter real vs simulated
        valid_real_acts = [a for a in h_real_acts if a and a.get("id") and a.get("status") == "completed"]
        valid_sim_acts = [s for s in h_sim_acts if s and s.get("id")]

        # 5. Check runbook prerequisites satisfaction on current incident
        prereq_checks: List[RunbookPrerequisiteMatch] = []
        for rbk in current_ctx.runbooks:
            if rbk.steps:
                # First step is diagnostic prerequisite
                step0 = rbk.steps[0]
                # Check if current incident has alerts matching the service
                has_alert = any(a.service_id == rbk.service_id for a in current_ctx.alerts)
                prereq_checks.append(RunbookPrerequisiteMatch(
                    runbook_id=rbk.id,
                    runbook_title=rbk.title,
                    service_id=rbk.service_id,
                    required_step_id=step0.id,
                    required_action=step0.action,
                    is_satisfied=has_alert,
                    reason=f"Step 1 ({step0.action}) diagnostic condition is {'satisfied' if has_alert else 'unverified'} on {rbk.service_name}.",
                ))

        comparisons.append(HistoricalComparison(
            historical_incident_id=h_id,
            historical_title=h_title or "Untitled Incident",
            historical_investigation_id=h_inv_id,
            is_relevant=is_relevant,
            relevance_score=relevance_score,
            relevance_explanation=relevance_explanation,
            common_affected_services=common_svcs,
            evidence_similarities=similarities if similarities else ["No direct telemetry or topology matches."],
            evidence_differences=differences if differences else ["Identical service scope."],
            verified_recovery_outcomes=valid_real_acts,
            simulated_outcomes_summary=valid_sim_acts,
            runbook_prerequisite_checks=prereq_checks,
            unresolved_questions_carried_over=[
                f"Did historical resolution '{a['action_type']}' on {h_id} apply to current dependency tier?"
                for a in valid_real_acts
            ],
            epistemic_disclaimer="Simulated dry-run successes and LLM hypotheses are historical references and NOT treated as verified real-world operational truth.",
        ))

    # Sort descending by relevance score
    comparisons.sort(key=lambda x: x.relevance_score, reverse=True)

    return InvestigationMemoryResponse(
        current_incident_id=current_incident_id,
        current_affected_services=curr_affected_svcs,
        retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        historical_comparisons=comparisons,
        total_relevant_found=len([c for c in comparisons if c.is_relevant]),
    )
