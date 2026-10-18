# TraceForge Operational Knowledge & Evidence Debt Specification

> **Operational Principle**:
> *"An investigation is only as reliable as its underlying knowledge graph. Evidence Debt represents unverified, stale, missing, or contradictory assumptions that limit automated decision-making."*

---

## 1. Overview & Conceptual Model

Evidence Debt quantifies operational knowledge deficiencies across 8 core categories:
1. `MISSING_DEPENDENCY_VERIFICATION`: A service dependency exists in runtime traffic but lacks an explicit cataloged `DEPENDS_ON` relationship in FalkorDB.
2. `UNLINKED_ALERT`: An alert is emitted by a service or infrastructure monitor but cannot be linked to the incident's causal failure chain (alert noise).
3. `TIMESTAMP_ANOMALY`: A deployment, alert, or metric lacks a verified timestamp or commit SHA, preventing precise temporal causal modeling.
4. `UNVERIFIED_RESOLUTION`: A historical incident recovery action was applied without formal post-incident verification or approval provenance.
5. `STALE_METRIC`: A metric observation is temporally desynchronized from incident inception (>15m window delta).
6. `MISSING_RUNBOOK_PREREQUISITE`: A runbook remediation step modifies production infrastructure but lacks signed approval provenance.
7. `CONTRADICTORY_EVIDENCE`: An active hypothesis is challenged by verified opposing observations.
8. `INSUFFICIENT_TELEMETRY`: Telemetry observations are sparse (<3 anomalous data points), requiring epistemic abstention.

---

## 2. Transparent Priority Rule (Documented & Non-Arbitrary)

Rather than inventing an uncalibrated pseudo-mathematical percentage score, Evidence Debt enforces a deterministic 3-tier priority rule:

```
+---------------------------------------------------------------------------------------+
|  BLOCKING                                                                             |
|  - Definition: Gaps that sever causal topological paths, prevent automated rollback,   |
|    or lack human safety approvals.                                                    |
|  - Impact: Hard-blocks autonomous remediation actions; flags ranking as unverified.   |
+---------------------------------------------------------------------------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------------+
|  WARNING                                                                              |
|  - Definition: Contradictory evidence, unlinked alert noise, or metric staleness.      |
|  - Impact: Penalizes confidence scores but permits human-in-the-loop inspection.       |
+---------------------------------------------------------------------------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------------+
|  INFORMATIONAL                                                                        |
|  - Definition: Minor hygiene gaps, missing author metadata, or optional telemetry.    |
|  - Impact: Tracked for post-incident review and knowledge catalog hygiene.            |
+---------------------------------------------------------------------------------------+
```

---

## 3. FalkorDB Provenance & Debt Resolution Flow

When an SRE or investigator provides the missing evidence (e.g. an OpenTelemetry distributed trace span or a cryptographic approval key), TraceForge records an `EvidenceDebt` node in FalkorDB:

```cypher
MERGE (d:EvidenceDebt {id: $gap_id, incident_id: $incident_id})
SET d.status = 'RESOLVED',
    d.resolved_at = $resolved_at,
    d.resolution_evidence_id = $resolution_evidence_id,
    d.notes = $notes
WITH d
MATCH (inc:Incident {id: $incident_id})
MERGE (inc)-[:HAS_EVIDENCE_DEBT]->(d)
```

This clears the blocked recovery actions and transitions the debt gap from `ACTIVE` to `RESOLVED` in real time.
