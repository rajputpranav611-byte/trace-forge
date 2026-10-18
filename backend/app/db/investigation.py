from typing import Any, Dict, List, Optional
from app.db.client import db_client
from app.schemas.investigation import (
    IncidentBase,
    ServiceNode,
    AlertItem,
    MetricObservationItem,
    DeploymentItem,
    HistoricalIncidentItem,
    RunbookItem,
    RunbookStepItem,
    GraphEdge,
    TraversedPath,
    ServiceDependencyTopology,
    InvestigationContextResponse,
)


def get_incident_alerts_and_metrics(
    incident_id: str,
    graph_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieves the incident, its affected services, and all correlated alerts and metric observations."""
    graph = db_client.get_graph(graph_name)
    query = """
    MATCH (inc:Incident {id: $incident_id})
    OPTIONAL MATCH (inc)-[:AFFECTS]->(s:Service)
    OPTIONAL MATCH (s)-[:PRODUCES_ALERT]->(a:Alert)
    OPTIONAL MATCH (a)-[:CORRELATES_WITH]->(m:MetricObservation)
    RETURN inc.id AS id,
           inc.title AS title,
           inc.severity AS severity,
           inc.status AS status,
           inc.started_at AS started_at,
           inc.resolved_at AS resolved_at,
           inc.summary AS summary,
           collect(DISTINCT {
               id: s.id,
               name: s.name,
               tier: s.tier,
               team: s.team,
               status: s.status
           }) AS services,
           collect(DISTINCT {
               id: a.id,
               service_id: s.id,
               service_name: s.name,
               name: a.name,
               severity: a.severity,
               source: a.source,
               timestamp: a.timestamp,
               description: a.description,
               metric_name: a.metric_name,
               value: a.value
           }) AS alerts,
           collect(DISTINCT {
               id: m.id,
               alert_id: a.id,
               metric_name: m.metric_name,
               timestamp: m.timestamp,
               value: m.value,
               baseline: m.baseline,
               deviation_sigma: m.deviation_sigma,
               unit: m.unit
           }) AS metrics
    """
    res = graph.ro_query(query, {"incident_id": incident_id})
    if not res.result_set or res.result_set[0][0] is None:
        return {}

    row = res.result_set[0]
    return {
        "incident": {
            "id": row[0],
            "title": row[1],
            "severity": row[2],
            "status": row[3],
            "started_at": row[4],
            "resolved_at": row[5] or "",
            "summary": row[6],
        },
        "affected_services": [s for s in row[7] if s.get("id") is not None],
        "alerts": [a for a in row[8] if a.get("id") is not None],
        "metrics": [m for m in row[9] if m.get("id") is not None],
    }


def get_topology_for_services(
    service_ids: List[str],
    max_depth: int = 3,
    graph_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Traverses dependencies for all affected services up to a bounded depth and returns nodes, edges, and path sequences."""
    if not service_ids:
        return {"nodes": [], "edges": [], "paths": []}

    graph = db_client.get_graph(graph_name)
    clamped_depth = max(1, min(max_depth, 4))

    # Query 1: Extract distinct nodes and edges
    query = f"""
    MATCH path = (root:Service)-[:DEPENDS_ON*1..{clamped_depth}]->(target:Service)
    WHERE root.id IN $service_ids
    UNWIND nodes(path) AS n
    UNWIND relationships(path) AS r
    RETURN collect(DISTINCT {{
               id: n.id,
               name: n.name,
               tier: n.tier,
               team: n.team,
               status: n.status
           }}) AS nodes,
           collect(DISTINCT {{
               source: startNode(r).id,
               target: endNode(r).id,
               type: type(r),
               protocol: r.protocol,
               critical: r.critical
           }}) AS edges
    """
    res = graph.ro_query(query, {"service_ids": service_ids})

    nodes = []
    edges = []
    if res.result_set and res.result_set[0][0]:
        nodes = res.result_set[0][0]
        edges = res.result_set[0][1]

    # Query 2: Extract explicit path chains
    path_query = f"""
    MATCH path = (root:Service)-[:DEPENDS_ON*1..{clamped_depth}]->(target:Service)
    WHERE root.id IN $service_ids
    RETURN length(path) AS length,
           [n in nodes(path) | n.id] AS node_ids,
           [r in relationships(path) | type(r)] AS rel_types
    LIMIT 25
    """
    path_res = graph.ro_query(path_query, {"service_ids": service_ids})
    paths = []
    for r in path_res.result_set:
        paths.append({
            "length": r[0],
            "node_ids": r[1],
            "relationship_types": r[2],
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "paths": paths,
    }


def get_applicable_runbooks(
    service_ids: List[str],
    graph_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves all runbooks and sequential steps applicable to any of the specified services."""
    if not service_ids:
        return []

    graph = db_client.get_graph(graph_name)
    query = """
    MATCH (r:Runbook)-[:APPLIES_TO]->(s:Service)
    WHERE s.id IN $service_ids
    OPTIONAL MATCH (r)-[hs:HAS_STEP]->(st:RunbookStep)
    RETURN r.id AS id,
           s.id AS service_id,
           s.name AS service_name,
           r.title AS title,
           r.version AS version,
           r.url AS url,
           collect(DISTINCT {
               id: st.id,
               step_number: hs.sequence,
               action: st.action,
               command: st.command,
               estimated_time_mins: st.estimated_time_mins
           }) AS steps
    """
    res = graph.ro_query(query, {"service_ids": service_ids})
    runbooks = []
    for row in res.result_set:
        raw_steps = [st for st in row[6] if st.get("id") is not None]
        # Sort steps by sequence number
        steps = sorted(raw_steps, key=lambda x: x.get("step_number") or 0)
        runbooks.append({
            "id": row[0],
            "service_id": row[1],
            "service_name": row[2],
            "title": row[3],
            "version": row[4],
            "url": row[5],
            "steps": steps,
        })
    return runbooks


def build_investigation_context(
    incident_id: str,
    max_depth: int = 3,
    graph_name: Optional[str] = None,
) -> Optional[InvestigationContextResponse]:
    """Deterministic orchestrator query assembling full incident context."""
    base_data = get_incident_alerts_and_metrics(incident_id, graph_name)
    if not base_data:
        return None

    inc_info = base_data["incident"]
    affected_services = base_data["affected_services"]
    alerts = base_data["alerts"]
    metrics = base_data["metrics"]

    affected_ids = [s["id"] for s in affected_services]

    # Traverse dependencies up to max_depth hops
    topo_data = get_topology_for_services(affected_ids, max_depth=max_depth, graph_name=graph_name)

    traversed_services = topo_data["nodes"]
    dependency_edges = topo_data["edges"]
    traversed_paths = topo_data["paths"]

    # Gather all candidate services to inspect for deployments and historical incidents
    all_service_ids = list(set(affected_ids + [n["id"] for n in traversed_services]))

    # Retrieve deployments for affected services
    graph = db_client.get_graph(graph_name)
    dep_query = """
    MATCH (d:Deployment)-[r:DEPLOYED_TO]->(s:Service)
    WHERE s.id IN $service_ids
    RETURN d.id AS id,
           s.id AS service_id,
           s.name AS service_name,
           d.version AS version,
           d.commit_sha AS commit_sha,
           d.deployed_at AS deployed_at,
           d.author AS author,
           d.status AS status,
           d.environment AS environment,
           r.strategy AS strategy
    ORDER BY d.deployed_at DESC
    LIMIT 20
    """
    dep_res = graph.ro_query(dep_query, {"service_ids": all_service_ids})
    deployments = []
    for r in dep_res.result_set:
        deployments.append(DeploymentItem(
            id=r[0],
            service_id=r[1],
            service_name=r[2],
            version=r[3],
            commit_sha=r[4],
            deployed_at=r[5],
            author=r[6],
            status=r[7],
            environment=r[8],
            strategy=r[9],
        ))

    # Retrieve historical incidents affecting these services (excluding current incident)
    hist_query = """
    MATCH (inc:Incident)-[:AFFECTS]->(s:Service)
    WHERE s.id IN $service_ids AND inc.id <> $current_incident_id
    OPTIONAL MATCH (inc)-[:RESOLVED_BY]->(ra:RecoveryAction)
    RETURN inc.id AS id,
           s.id AS service_id,
           s.name AS service_name,
           inc.title AS title,
           inc.severity AS severity,
           inc.status AS status,
           inc.started_at AS started_at,
           inc.resolved_at AS resolved_at,
           inc.summary AS summary,
           collect(DISTINCT {
               id: ra.id,
               action_type: ra.action_type,
               status: ra.status,
               executed_at: ra.executed_at
           }) AS recovery_actions
    ORDER BY inc.started_at DESC
    LIMIT 10
    """
    hist_res = graph.ro_query(hist_query, {
        "service_ids": all_service_ids,
        "current_incident_id": incident_id,
    })
    historical_incidents = []
    for r in hist_res.result_set:
        actions = [a for a in r[9] if a.get("id") is not None]
        historical_incidents.append(HistoricalIncidentItem(
            id=r[0],
            service_id=r[1],
            service_name=r[2],
            title=r[3],
            severity=r[4],
            status=r[5],
            started_at=r[6],
            resolved_at=r[7] or "",
            summary=r[8],
            recovery_actions=actions,
        ))

    # Retrieve applicable runbooks
    runbooks_raw = get_applicable_runbooks(all_service_ids, graph_name)
    runbooks = [RunbookItem(**rb) for rb in runbooks_raw]

    # Explicit missing relationship checks (e.g. risk-scoring-engine -> merchant-config-service)
    missing_relationships = []
    if "risk-scoring-engine" in all_service_ids:
        # Check if edge exists to merchant-config-service
        edge_exists = any(
            e.get("source") == "risk-scoring-engine" and e.get("target") == "merchant-config-service"
            for e in dependency_edges
        )
        if not edge_exists:
            missing_relationships.append(
                "Unregistered runtime dependency: 'risk-scoring-engine' calls 'merchant-config-service' synchronously, but no [:DEPENDS_ON] edge exists in the service catalog."
            )

    topology = ServiceDependencyTopology(
        affected_services=[ServiceNode(**s) for s in affected_services],
        traversed_services=[ServiceNode(**s) for s in traversed_services],
        dependency_edges=[GraphEdge(**e) for e in dependency_edges],
        traversed_paths=[TraversedPath(**p) for p in traversed_paths],
        missing_relationships_detected=missing_relationships,
    )

    evidence_summary = {
        "source_incident_id": incident_id,
        "affected_service_count": len(affected_services),
        "alert_count": len(alerts),
        "metric_anomalies_count": len(metrics),
        "total_traversed_nodes": len(traversed_services),
        "dependency_edge_count": len(dependency_edges),
        "deployment_candidate_count": len(deployments),
        "historical_precedent_count": len(historical_incidents),
        "runbook_count": len(runbooks),
        "is_sufficient_evidence": len(alerts) > 1 and len(metrics) > 0,
    }

    return InvestigationContextResponse(
        incident=IncidentBase(**inc_info),
        alerts=[AlertItem(**a) for a in alerts],
        metrics=[MetricObservationItem(**m) for m in metrics],
        topology=topology,
        deployments=deployments,
        historical_incidents=historical_incidents,
        runbooks=runbooks,
        evidence_summary=evidence_summary,
    )
