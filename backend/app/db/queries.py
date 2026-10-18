import logging
from typing import Any, Dict, List, Optional
from falkordb import FalkorDB
from app.db.client import db_client

logger = logging.getLogger("traceforge.queries")


def create_graph_schema_indexes(graph_name: Optional[str] = None) -> None:
    """Ensures indexes exist on primary entity keys in FalkorDB."""
    graph = db_client.get_graph(graph_name)
    indexed_labels = [
        ("Service", "id"),
        ("Incident", "id"),
        ("Alert", "id"),
        ("Deployment", "id"),
        ("MetricObservation", "id"),
        ("Runbook", "id"),
        ("RunbookStep", "id"),
        ("Evidence", "id"),
        ("Hypothesis", "id"),
        ("Investigation", "id"),
        ("RecoveryAction", "id"),
        ("Approval", "id"),
    ]
    for label, prop in indexed_labels:
        try:
            graph.query(f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
        except Exception as e:
            # Index already exists or engine note
            logger.debug(f"Index creation note for {label}.{prop}: {e}")


def list_incidents(
    status: Optional[str] = None,
    limit: int = 50,
    graph_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves list of incidents, optionally filtered by status (active/resolved)."""
    graph = db_client.get_graph(graph_name)
    where_clause = "WHERE inc.status = $status" if status else ""
    query = f"""
    MATCH (inc:Incident)
    {where_clause}
    OPTIONAL MATCH (inc)-[:AFFECTS]->(s:Service)
    RETURN inc.id AS id,
           inc.title AS title,
           inc.severity AS severity,
           inc.status AS status,
           inc.started_at AS started_at,
           inc.resolved_at AS resolved_at,
           inc.summary AS summary,
           collect(DISTINCT s.name) AS affected_services
    ORDER BY inc.started_at DESC
    LIMIT $limit
    """
    params: Dict[str, Any] = {"limit": limit}
    if status:
        params["status"] = status

    result = graph.ro_query(query, params)
    incidents = []
    for record in result.result_set:
        incidents.append({
            "id": record[0],
            "title": record[1],
            "severity": record[2],
            "status": record[3],
            "started_at": record[4],
            "resolved_at": record[5],
            "summary": record[6],
            "affected_services": record[7],
        })
    return incidents


def get_incident_with_alerts(
    incident_id: str,
    graph_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieves an incident and its associated affected services and alerts."""
    graph = db_client.get_graph(graph_name)
    query = """
    MATCH (inc:Incident {id: $incident_id})
    OPTIONAL MATCH (inc)-[:AFFECTS]->(s:Service)
    OPTIONAL MATCH (s)-[:PRODUCES_ALERT]->(a:Alert)
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
               status: s.status
           }) AS services,
           collect(DISTINCT {
               id: a.id,
               name: a.name,
               severity: a.severity,
               source: a.source,
               timestamp: a.timestamp,
               description: a.description
           }) AS alerts
    """
    result = graph.ro_query(query, {"incident_id": incident_id})
    if not result.result_set or result.result_set[0][0] is None:
        return None

    row = result.result_set[0]
    # Filter out empty collected objects where OPTIONAL MATCH was null
    services = [s for s in row[7] if s.get("id") is not None]
    alerts = [a for a in row[8] if a.get("id") is not None]

    return {
        "id": row[0],
        "title": row[1],
        "severity": row[2],
        "status": row[3],
        "started_at": row[4],
        "resolved_at": row[5],
        "summary": row[6],
        "affected_services": services,
        "alerts": alerts,
    }


def traverse_dependencies(
    service_id: str,
    max_depth: int = 3,
    graph_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Traverses upstream dependencies that the specified service relies on (bounded depth).

    Directed edge: (service)-[:DEPENDS_ON]->(upstream)
    """
    graph = db_client.get_graph(graph_name)
    clamped_depth = max(1, min(max_depth, 5))
    query = f"""
    MATCH path = (root:Service {{id: $service_id}})-[:DEPENDS_ON*1..{clamped_depth}]->(target:Service)
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
               protocol: r.protocol
           }}) AS edges
    """
    result = graph.ro_query(query, {"service_id": service_id})
    if not result.result_set:
        return {"root_service_id": service_id, "nodes": [], "edges": []}

    row = result.result_set[0]
    return {
        "root_service_id": service_id,
        "nodes": row[0] or [],
        "edges": row[1] or [],
    }


def find_downstream_dependents(
    service_id: str,
    max_depth: int = 3,
    graph_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Finds services that depend on this service (downstream impact / blast radius).

    Directed edge: (downstream)-[:DEPENDS_ON]->(this_service)
    """
    graph = db_client.get_graph(graph_name)
    clamped_depth = max(1, min(max_depth, 5))
    query = f"""
    MATCH path = (dependent:Service)-[:DEPENDS_ON*1..{clamped_depth}]->(root:Service {{id: $service_id}})
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
               type: type(r)
           }}) AS edges
    """
    result = graph.ro_query(query, {"service_id": service_id})
    if not result.result_set:
        return {"root_service_id": service_id, "nodes": [], "edges": []}

    row = result.result_set[0]
    return {
        "root_service_id": service_id,
        "nodes": row[0] or [],
        "edges": row[1] or [],
    }


def get_deployments_for_service(
    service_id: str,
    limit: int = 10,
    graph_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves deployments deployed to the target service ordered by deployment time."""
    graph = db_client.get_graph(graph_name)
    query = """
    MATCH (d:Deployment)-[r:DEPLOYED_TO]->(s:Service {id: $service_id})
    RETURN d.id AS id,
           d.version AS version,
           d.commit_sha AS commit_sha,
           d.deployed_at AS deployed_at,
           d.author AS author,
           d.status AS status,
           d.environment AS environment,
           r.strategy AS strategy,
           s.name AS service_name
    ORDER BY d.deployed_at DESC
    LIMIT $limit
    """
    result = graph.ro_query(query, {"service_id": service_id, "limit": limit})
    deployments = []
    for record in result.result_set:
        deployments.append({
            "id": record[0],
            "version": record[1],
            "commit_sha": record[2],
            "deployed_at": record[3],
            "author": record[4],
            "status": record[5],
            "environment": record[6],
            "strategy": record[7],
            "service_name": record[8],
        })
    return deployments


def get_historical_incidents_for_service(
    service_id: str,
    graph_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves past incidents affecting the given service along with how they were resolved."""
    graph = db_client.get_graph(graph_name)
    query = """
    MATCH (inc:Incident)-[:AFFECTS]->(s:Service {id: $service_id})
    OPTIONAL MATCH (inc)-[:RESOLVED_BY]->(ra:RecoveryAction)
    RETURN inc.id AS id,
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
    """
    result = graph.ro_query(query, {"service_id": service_id})
    incidents = []
    for record in result.result_set:
        actions = [a for a in record[7] if a.get("id") is not None]
        incidents.append({
            "id": record[0],
            "title": record[1],
            "severity": record[2],
            "status": record[3],
            "started_at": record[4],
            "resolved_at": record[5],
            "summary": record[6],
            "recovery_actions": actions,
        })
    return incidents
