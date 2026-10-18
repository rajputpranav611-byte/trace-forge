"""Core investigation services that power both MCP tools and backend endpoints.

Maintains strict separation between tool transport/schema definition and the
underlying graph querying, deterministic scoring, and graph surgery logic.
"""

import logging
from typing import Any, Dict, List, Optional
from app.db.client import db_client
from app.core.config import get_settings
from app.db.investigation import build_investigation_context
from app.db.queries import find_downstream_dependents
from app.db.surgery import execute_counterfactual_comparison
from app.core.ranking.engine import rank_hypotheses
from app.core.llm.verifier import execute_hypothesis_generation_workflow
from app.schemas.surgery import CreateExperimentRequest, GraphSurgeryAction

logger = logging.getLogger("traceforge.mcp.services")


def trace_dependency_path_service(
    source_service_id: str,
    target_service_id: str,
    max_depth: int = 3,
    graph_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Finds directed dependency paths between two service nodes in FalkorDB.

    Path represents: (source)-[:DEPENDS_ON*]->(target)
    """
    if not source_service_id or not source_service_id.strip():
        raise ValueError("source_service_id cannot be empty")
    if not target_service_id or not target_service_id.strip():
        raise ValueError("target_service_id cannot be empty")

    source_id = source_service_id.strip()
    target_id = target_service_id.strip()
    clamped_depth = max(1, min(max_depth, 5))

    graph = db_client.get_graph(graph_name)

    # 1. Validate source node existence
    src_check = graph.ro_query(
        "MATCH (s:Service {id: $src_id}) RETURN s.id AS id, s.name AS name, s.tier AS tier, s.status AS status",
        {"src_id": source_id},
    )
    if not src_check.result_set or src_check.result_set[0][0] is None:
        raise ValueError(f"Source service '{source_id}' does not exist in FalkorDB graph")
    src_info = {
        "id": src_check.result_set[0][0],
        "name": src_check.result_set[0][1],
        "tier": src_check.result_set[0][2],
        "status": src_check.result_set[0][3],
    }

    # 2. Validate target node existence
    tgt_check = graph.ro_query(
        "MATCH (t:Service {id: $tgt_id}) RETURN t.id AS id, t.name AS name, t.tier AS tier, t.status AS status",
        {"tgt_id": target_id},
    )
    if not tgt_check.result_set or tgt_check.result_set[0][0] is None:
        raise ValueError(f"Target service '{target_id}' does not exist in FalkorDB graph")
    tgt_info = {
        "id": tgt_check.result_set[0][0],
        "name": tgt_check.result_set[0][1],
        "tier": tgt_check.result_set[0][2],
        "status": tgt_check.result_set[0][3],
    }

    # 3. Query directed paths up to clamped_depth
    query = f"""
    MATCH p = (src:Service {{id: $src_id}})-[:DEPENDS_ON*1..{clamped_depth}]->(tgt:Service {{id: $tgt_id}})
    RETURN length(p),
           [n in nodes(p) | n.id],
           [r in relationships(p) | type(r)],
           [n in nodes(p) | n.name]
    LIMIT 25
    """
    res = graph.ro_query(query, {"src_id": source_id, "tgt_id": target_id})

    paths = []
    for row in res.result_set:
        paths.append({
            "length": row[0],
            "node_ids": row[1],
            "rel_types": row[2],
            "node_names": row[3],
        })

    return {
        "source_service": src_info,
        "target_service": tgt_info,
        "max_depth_enforced": clamped_depth,
        "path_found": len(paths) > 0,
        "total_paths": len(paths),
        "paths": paths,
        "traversal_semantics": "Directed upstream dependency traversal: (source)-[:DEPENDS_ON*]->(target)",
    }


def get_blast_radius_service(
    service_id: str,
    max_depth: int = 3,
    graph_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Identifies downstream services that depend on this service (downstream impact / blast radius).

    Directed edge: (dependent)-[:DEPENDS_ON*]->(root:Service {id: service_id})
    """
    if not service_id or not service_id.strip():
        raise ValueError("service_id cannot be empty")

    svc_id = service_id.strip()
    clamped_depth = max(1, min(max_depth, 5))

    graph = db_client.get_graph(graph_name)

    # 1. Validate root service existence
    root_check = graph.ro_query(
        "MATCH (s:Service {id: $svc_id}) RETURN s.id AS id, s.name AS name, s.tier AS tier, s.status AS status, s.team AS team",
        {"svc_id": svc_id},
    )
    if not root_check.result_set or root_check.result_set[0][0] is None:
        raise ValueError(f"Service '{svc_id}' does not exist in FalkorDB graph")

    root_info = {
        "id": root_check.result_set[0][0],
        "name": root_check.result_set[0][1],
        "tier": root_check.result_set[0][2],
        "status": root_check.result_set[0][3],
        "team": root_check.result_set[0][4],
    }

    # 2. Traverse downstream dependents with hops
    query = f"""
    MATCH path = (dependent:Service)-[:DEPENDS_ON*1..{clamped_depth}]->(root:Service {{id: $svc_id}})
    WHERE dependent.id <> $svc_id
    RETURN dependent.id AS id,
           dependent.name AS name,
           dependent.tier AS tier,
           dependent.status AS status,
           dependent.team AS team,
           min(length(path)) AS min_hop_distance,
           collect(DISTINCT [n in nodes(path) | n.id]) AS sample_paths
    """
    res = graph.ro_query(query, {"svc_id": svc_id})

    affected_services = []
    seen_ids = set()
    for row in res.result_set:
        dep_id = row[0]
        if dep_id and dep_id not in seen_ids:
            seen_ids.add(dep_id)
            affected_services.append({
                "service_id": dep_id,
                "name": row[1] or "Unknown",
                "tier": row[2],
                "status": row[3],
                "team": row[4],
                "hop_distance": row[5],
                "sample_paths": row[6][:3] if row[6] else [],
            })

    # Sort affected services by hop distance and tier
    affected_services.sort(key=lambda x: (x["hop_distance"], x["tier"]))

    return {
        "root_service": root_info,
        "max_depth_enforced": clamped_depth,
        "total_affected_downstream_services": len(affected_services),
        "traversal_semantics": "Downstream dependency blast radius: (dependent:Service)-[:DEPENDS_ON*]->(root:Service)",
        "affected_services": affected_services,
    }


def inspect_incident_evidence_service(
    incident_id: str,
    max_depth: int = 3,
    graph_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieves all evidence associated with an incident from FalkorDB.

    Labels observed, inferred, and synthetic data transparently.
    """
    if not incident_id or not incident_id.strip():
        raise ValueError("incident_id cannot be empty")

    inc_id = incident_id.strip()
    context = build_investigation_context(incident_id=inc_id, max_depth=max_depth, graph_name=graph_name)
    if not context:
        raise ValueError(f"Incident '{inc_id}' not found in FalkorDB graph")

    alerts = [
        {
            "id": a.id,
            "name": a.name,
            "service_id": a.service_id,
            "service_name": a.service_name,
            "severity": a.severity,
            "source": a.source or "Unknown Source",
            "observation_timestamp": a.timestamp or "Unknown",
            "description": a.description,
            "metric_name": a.metric_name or "None",
            "metric_value": a.value if a.value is not None else "None",
            "epistemic_status": "OBSERVED",
        }
        for a in context.alerts
    ]

    metrics = [
        {
            "id": m.id,
            "metric_name": m.metric_name,
            "observation_timestamp": m.timestamp or "Unknown",
            "observed_value": m.value,
            "baseline_value": m.baseline,
            "deviation_sigma": m.deviation_sigma,
            "unit": m.unit or "",
            "epistemic_status": "OBSERVED",
        }
        for m in context.metrics
    ]

    deployments = [
        {
            "id": d.id,
            "service_id": d.service_id,
            "service_name": d.service_name,
            "version": d.version,
            "deployed_at": d.deployed_at or "Unknown",
            "commit_sha": d.commit_sha or "Unknown",
            "author": d.author or "Unknown",
            "status": d.status,
            "strategy": d.strategy or "Unknown",
            "epistemic_status": "OBSERVED",
        }
        for d in context.deployments
    ]

    affected_services = [
        {
            "id": s.id,
            "name": s.name,
            "tier": s.tier,
            "team": s.team,
            "status": s.status,
            "epistemic_status": "OBSERVED",
        }
        for s in context.topology.affected_services
    ]

    traversed_services = [
        {
            "id": s.id,
            "name": s.name,
            "tier": s.tier,
            "team": s.team,
            "status": s.status,
            "epistemic_status": "INFERRED_TOPOLOGY",
        }
        for s in context.topology.traversed_services
    ]

    return {
        "incident": {
            "id": context.incident.id,
            "title": context.incident.title,
            "severity": context.incident.severity,
            "status": context.incident.status,
            "started_at": context.incident.started_at,
            "resolved_at": context.incident.resolved_at or "Active / Ongoing",
            "summary": context.incident.summary,
            "epistemic_status": "OBSERVED",
        },
        "evidence_summary": context.evidence_summary,
        "affected_services": affected_services,
        "traversed_dependencies": traversed_services,
        "dependency_edges_count": len(context.topology.dependency_edges),
        "alerts": alerts,
        "metric_observations": metrics,
        "deployments": deployments,
        "missing_relationships_debt": context.topology.missing_relationships_detected,
    }


async def compare_hypotheses_service(
    incident_id: str,
    max_depth: int = 3,
    graph_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Compares candidate root causes using the real deterministic scoring and ranking engine."""
    if not incident_id or not incident_id.strip():
        raise ValueError("incident_id cannot be empty")

    inc_id = incident_id.strip()
    context = build_investigation_context(incident_id=inc_id, max_depth=max_depth, graph_name=graph_name)
    if not context:
        raise ValueError(f"Incident '{inc_id}' not found in FalkorDB graph")

    verified_resp = await execute_hypothesis_generation_workflow(context)
    ranked_list, abstained, unresolved = rank_hypotheses(verified_resp.hypotheses, context)

    hypotheses_output = []
    for hyp in ranked_list:
        hypotheses_output.append({
            "rank": hyp.rank,
            "hypothesis_id": hyp.id,
            "title": hyp.title,
            "statement": hyp.statement,
            "suspected_entity": hyp.suspected_entity,
            "verdict": hyp.verdict,
            "deterministic_score": hyp.deterministic_score,
            "causal_path_found": hyp.causal_path_found,
            "causal_path": hyp.causal_path,
            "supporting_evidence_ids": hyp.supporting_evidence_ids,
            "contradicting_evidence_ids": hyp.contradicting_evidence_ids,
            "score_factors": [
                {
                    "factor_name": f.name,
                    "contribution": f.contribution,
                    "reason": f.reason,
                }
                for f in hyp.score_factors
            ],
            "recommended_action": hyp.recommended_action,
        })

    return {
        "incident_id": inc_id,
        "total_hypotheses_evaluated": len(ranked_list),
        "abstained": abstained,
        "top_hypothesis": hypotheses_output[0] if hypotheses_output else None,
        "hypotheses": hypotheses_output,
        "unresolved_questions": unresolved,
        "epistemic_disclaimer": "Deterministic evaluation backed by real graph topology, temporal window, and metric evidence.",
    }


async def simulate_graph_intervention_service(
    incident_id: str,
    action_type: str,
    source_id: str,
    target_id: Optional[str] = None,
    relationship_type: str = "DEPENDS_ON",
    justification: str = "MCP Counterfactual Investigation",
) -> Dict[str, Any]:
    """Runs a safe, isolated counterfactual graph surgery experiment in FalkorDB."""
    if not incident_id or not incident_id.strip():
        raise ValueError("incident_id cannot be empty")
    if not action_type or not action_type.strip():
        raise ValueError("action_type cannot be empty")
    if not source_id or not source_id.strip():
        raise ValueError("source_id cannot be empty")

    supported_actions = ["remove_dependency", "isolate_service", "rollback_deployment", "remove_evidence"]
    if action_type not in supported_actions:
        raise ValueError(f"Unsupported action_type '{action_type}'. Supported: {', '.join(supported_actions)}")

    if action_type == "remove_dependency" and not target_id:
        raise ValueError("target_id is required for action_type 'remove_dependency'")

    action = GraphSurgeryAction(
        action_type=action_type,
        source_id=source_id.strip(),
        target_id=target_id.strip() if target_id else None,
        relationship_type=relationship_type,
        justification=justification,
    )

    req = CreateExperimentRequest(
        baseline_incident_id=incident_id.strip(),
        experiment_name=f"MCP-Sim-{action_type}-{source_id}",
        actions=[action],
    )

    comp = await execute_counterfactual_comparison(req)

    return {
        "simulation": True,
        "production_mutated": False,
        "experiment_id": comp.experiment_id,
        "baseline_incident_id": comp.baseline_incident_id,
        "disclaimer": comp.disclaimer,
        "causal_change_explanation": comp.causal_change_explanation,
        "blast_radius_diff": {
            "service_id": comp.blast_radius_diff.service_id,
            "baseline_downstream_count": comp.blast_radius_diff.baseline_downstream_count,
            "experiment_downstream_count": comp.blast_radius_diff.experiment_downstream_count,
            "severed_services": comp.blast_radius_diff.severed_services,
            "added_services": comp.blast_radius_diff.added_services,
        },
        "hypothesis_diffs": [
            {
                "hypothesis_id": d.hypothesis_id,
                "title": d.title,
                "baseline_rank": d.baseline_rank,
                "experiment_rank": d.experiment_rank,
                "baseline_score": d.baseline_score,
                "experiment_score": d.experiment_score,
                "score_delta": d.score_delta,
                "causal_path_changed": d.causal_path_changed,
                "evidence_diff_summary": d.evidence_diff_summary,
                "score_delta_explanation": d.score_delta_explanation,
                "factor_diffs": [
                    {
                        "factor_name": fd.factor_name,
                        "baseline_contribution": fd.baseline_contribution,
                        "experiment_contribution": fd.experiment_contribution,
                        "contribution_delta": fd.contribution_delta,
                        "baseline_reason": fd.baseline_reason,
                        "experiment_reason": fd.experiment_reason,
                    }
                    for fd in (d.factor_diffs or [])
                ],
            }
            for d in comp.hypothesis_diffs
        ],
    }
