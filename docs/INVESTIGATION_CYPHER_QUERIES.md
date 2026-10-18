# TraceForge Cypher Investigation Queries Specification

This document details the exact openCypher queries executed by the TraceForge investigation engine against FalkorDB. All queries use parameterized inputs to ensure plan cache reuse and security against injection.

---

## 1. Incident, Alerts & Metric Observations Query
Retrieves the incident root node, directly affected services, emitted alerts, and correlating statistical metric anomalies.

```cypher
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
```

---

## 2. Bounded Multi-Hop Dependency Traversal
Expands upstream service dependencies up to `max_depth` hops (clamped between 1 and 4) starting from the set of affected services.

```cypher
MATCH path = (root:Service)-[:DEPENDS_ON*1..$max_depth]->(target:Service)
WHERE root.id IN $service_ids
UNWIND nodes(path) AS n
UNWIND relationships(path) AS r
RETURN collect(DISTINCT {
           id: n.id,
           name: n.name,
           tier: n.tier,
           team: n.team,
           status: n.status
       }) AS nodes,
       collect(DISTINCT {
           source: startNode(r).id,
           target: endNode(r).id,
           type: type(r),
           protocol: r.protocol,
           critical: r.critical
       }) AS edges
```

---

## 3. Explicit Dependency Path Chains
Extracts the precise sequence of traversed node identifiers and relationship types to visualize exact causal call chains in the UI.

```cypher
MATCH path = (root:Service)-[:DEPENDS_ON*1..$max_depth]->(target:Service)
WHERE root.id IN $service_ids
RETURN length(path) AS length,
       [n in nodes(path) | n.id] AS node_ids,
       [r in relationships(path) | type(r)] AS rel_types
LIMIT 25
```

---

## 4. Candidate Production Deployments
Retrieves recent production deployments rolled out to any service within the affected or traversed subgraph.

```cypher
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
```

---

## 5. Historical Incidents & Mitigation Precedents
Searches for past incidents that targeted the same affected services, including the recovery actions and approvals that resolved them.

```cypher
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
```

---

## 6. Applicable Runbooks & Sequential Recovery Steps
Extracts operational playbooks and ordered remediation commands associated with affected services.

```cypher
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
```
