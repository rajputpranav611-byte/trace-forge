# TraceForge Operational Graph Model & Schema Specification
**Domain:** NexusPay Payment Platform  
**Target Engine:** FalkorDB (openCypher)

---

## 1. Node Types & Core Properties

All nodes have a unique, stable `id` and an ISO-8601 `created_at` timestamp.

| Node Label | Core Properties | Description |
| :--- | :--- | :--- |
| **`Service`** | `id`, `name`, `tier` (1-3), `team`, `language`, `repository`, `status` | Microservices, data stores, API gateways, external acquirers. |
| **`Incident`** | `id`, `title`, `severity` (SEV1-SEV3), `status` (active/resolved), `started_at`, `resolved_at`, `summary` | Operational incidents triggering investigations. |
| **`Alert`** | `id`, `name`, `severity` (critical/warning), `timestamp`, `source`, `description`, `metric_name`, `value` | Monitoring alerts from Prometheus / Datadog. |
| **`MetricObservation`**| `id`, `metric_name`, `timestamp`, `value`, `baseline`, `deviation_sigma`, `unit` | Statistical anomalies in latency, error rate, saturation. |
| **`Deployment`** | `id`, `version`, `commit_sha`, `deployed_at`, `author`, `status` (success/failed), `environment` | CI/CD production releases. |
| **`Runbook`** | `id`, `title`, `service_id`, `version`, `updated_at`, `url` | Mitigation documentation and procedure playbooks. |
| **`RunbookStep`** | `id`, `runbook_id`, `step_number`, `action`, `command`, `estimated_time_mins` | Individual actionable recovery steps. |
| **`Evidence`** | `id`, `type` (metric/log/diff/trace), `description`, `observed_at`, `source_ref`, `confidence` | Discovered facts supporting or refuting theories. |
| **`Hypothesis`** | `id`, `statement`, `confidence` (0.0 - 1.0), `status` (validated/refuted/open), `created_at` | Candidate root cause theories formed during triage. |
| **`Investigation`** | `id`, `incident_id`, `started_at`, `updated_at`, `status` (in_progress/completed), `lead_agent` | Investigation execution tracking. |
| **`RecoveryAction`** | `id`, `action_type` (rollback/scale/circuit_break/cache_flush), `target_entity_id`, `executed_at`, `status` | Remediation actions taken to recover service. |
| **`Approval`** | `id`, `action_id`, `approver`, `role`, `status` (approved/rejected), `decided_at`, `notes` | Human/agent safety gate approvals. |

---

## 2. Relationship Types, Directions & Semantics

Directions follow strict causal, structural, and dependency flow:

```
(Service)-[:DEPENDS_ON {protocol, timeout_ms, criticality}]->(Service)
(Incident)-[:AFFECTS {impact_score}]->(Service)
(Service)-[:PRODUCES_ALERT]->(Alert)
(Alert)-[:CORRELATES_WITH]->(MetricObservation)
(Deployment)-[:DEPLOYED_TO {strategy}]->(Service)
(Runbook)-[:APPLIES_TO]->(Service)
(Runbook)-[:HAS_STEP {sequence}]->(RunbookStep)
(Investigation)-[:INVESTIGATES]->(Incident)
(Investigation)-[:EXPLORES_HYPOTHESIS]->(Hypothesis)
(Hypothesis)-[:SUPPORTS {weight}]->(Evidence)
(Hypothesis)-[:CONTRADICTS {weight}]->(Evidence)
(Investigation)-[:HAS_EVIDENCE]->(Evidence)
(Evidence)-[:INDICATES_ROOT_CAUSE]->(Service|Deployment|MetricObservation)
(Incident)-[:RESOLVED_BY]->(RecoveryAction)
(RecoveryAction)-[:TARGETS]->(Service)
(RecoveryAction)-[:EXECUTES_STEP]->(RunbookStep)
(RecoveryAction)-[:REQUIRES]->(Approval)
(Incident)-[:RESULTED_IN]->(Incident)
```

### Relationship Direction Matrix:
- `(Downstream:Service)-[:DEPENDS_ON]->(Upstream:Service)`: If Upstream fails, Downstream breaks.
- `(Incident)-[:AFFECTS]->(Service)`: The incident directly degrades this service.
- `(Service)-[:PRODUCES_ALERT]->(Alert)`: The alert was emitted by this service.
- `(Deployment)-[:DEPLOYED_TO]->(Service)`: Release rolled out to this target.
- `(Incident)-[:RESOLVED_BY]->(RecoveryAction)`: Remediation that mitigated the incident.
- `(RecoveryAction)-[:REQUIRES]->(Approval)`: Action gatekeeper constraint.

---

## 3. NexusPay Synthetic Environment (20 Services Across 5 Layers)

### Topology Layers:
1. **Edge & Ingress (Tier 1):**
   - `nexus-edge-gateway` -> `nexus-api-gateway`
2. **Core Domain Services (Tier 1):**
   - `auth-service`
   - `checkout-orchestrator`
   - `payment-core`
   - `fraud-detection-service`
   - `ledger-service`
   - `card-vault`
3. **Internal Processing & Routing (Tier 2):**
   - `tokenization-worker`
   - `risk-scoring-engine`
   - `merchant-config-service`
   - `notification-service`
   - `reconciliation-worker`
4. **Data & Storage Layer (Tier 1 & 2):**
   - `payment-db-cluster` (PostgreSQL)
   - `session-cache-redis` (Redis Cluster)
   - `event-stream-kafka` (Kafka Cluster)
   - `vault-hsm-store` (Encrypted HSM)
5. **External Acquirer & Partner Integrations (Tier 3):**
   - `visa-direct-gateway`
   - `mastercard-send-gateway`
   - `stripe-fallback-proxy`

---

## 4. Architectural Edge Cases & Fault Scenarios Seeded

1. **Active SEV1 Incident (`INC-2026-8821`): Payment Latency Spike & Cascading Timeouts**
   - Root Cause: Connection pool exhaustion on `payment-db-cluster` caused by unindexed query introduced in release `DEP-4012` on `payment-core`.
2. **Misleading Deployment Correlation:**
   - Deployment `DEP-4011` was deployed to `auth-service` 3 minutes before `INC-2026-8821` began, generating high alert noise and misleading triage toward auth token validation, while the real fault was in `payment-core` database pooling.
3. **Missing Dependency Relationship in Catalog:**
   - `risk-scoring-engine` actually calls `merchant-config-service` synchronously over HTTP at runtime, but this dependency was omitted from the service registry catalog (missing link). An investigation can detect this hidden dependency via trace/evidence correlation.
4. **Historical Incident with Contrasting Outcome (`INC-2026-7104`):**
   - Historical SEV2 on `ledger-service` caused by Kafka partition rebalancing; mitigated via partition scaling runbook.
5. **Insufficient Evidence Incident (`INC-2026-9043`):**
   - Intermittent 502 alerts on `nexus-api-gateway` with low observation count and unconfirmed hypotheses (investigation state inconclusive).
