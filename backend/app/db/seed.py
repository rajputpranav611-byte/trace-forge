"""Deterministic, idempotent seed script for the NexusPay operational graph in FalkorDB.

Features:
- 20 connected services across 5 layers.
- Realistic incidents (active SEV1, historical SEV2, and insufficient evidence SEV3).
- Misleading deployment correlation (DEP-4011 to auth-service vs true bug in DEP-4012 on payment-core).
- Missing dependency relationship (risk-scoring-engine -> merchant-config-service hidden dependency).
- Runbooks with ordered steps and approval constraints.
- Fully idempotent using Cypher MERGE and indexed primary keys.
"""

import logging
from typing import Optional
from app.db.client import db_client
from app.db.queries import create_graph_schema_indexes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("traceforge.seed")

# 1. Services Definition (20 Services)
SERVICES = [
    # Layer 1: Edge & Ingress
    {"id": "nexus-edge-gateway", "name": "Nexus Edge Gateway", "tier": 1, "team": "Edge Traffic", "lang": "Go", "repo": "nexus-edge", "status": "operational"},
    {"id": "nexus-api-gateway", "name": "Nexus API Gateway", "tier": 1, "team": "Core Platform", "lang": "Go", "repo": "nexus-api-gateway", "status": "degraded"},
    # Layer 2: Core Domain Services
    {"id": "auth-service", "name": "Authentication & Session", "tier": 1, "team": "Identity", "lang": "Go", "repo": "auth-svc", "status": "operational"},
    {"id": "checkout-orchestrator", "name": "Checkout Orchestrator", "tier": 1, "team": "Checkout", "lang": "Node.js", "repo": "checkout-orch", "status": "degraded"},
    {"id": "payment-core", "name": "Payment Core Processing", "tier": 1, "team": "Payments", "lang": "Java", "repo": "payment-core", "status": "failing"},
    {"id": "fraud-detection-service", "name": "Fraud Detection Service", "tier": 1, "team": "Risk", "lang": "Python", "repo": "fraud-svc", "status": "operational"},
    {"id": "ledger-service", "name": "Financial Ledger", "tier": 1, "team": "Ledger", "lang": "Rust", "repo": "ledger-svc", "status": "operational"},
    {"id": "card-vault", "name": "Card Token Vault", "tier": 1, "team": "Security", "lang": "C++", "repo": "card-vault", "status": "operational"},
    # Layer 3: Internal Processing & Workers
    {"id": "tokenization-worker", "name": "Tokenization Worker", "tier": 2, "team": "Security", "lang": "Go", "repo": "token-worker", "status": "operational"},
    {"id": "risk-scoring-engine", "name": "Risk Scoring Engine", "tier": 2, "team": "Risk", "lang": "Python", "repo": "risk-engine", "status": "operational"},
    {"id": "merchant-config-service", "name": "Merchant Configuration", "tier": 2, "team": "Merchant", "lang": "Go", "repo": "merchant-cfg", "status": "operational"},
    {"id": "notification-service", "name": "Customer Notification", "tier": 2, "team": "Growth", "lang": "Node.js", "repo": "notification-svc", "status": "operational"},
    {"id": "reconciliation-worker", "name": "Settlement Reconciler", "tier": 2, "team": "Ledger", "lang": "Java", "repo": "reconciler", "status": "operational"},
    # Layer 4: Storage & Data Layer
    {"id": "payment-db-cluster", "name": "Postgres Payment Cluster", "tier": 1, "team": "Data Infra", "lang": "Postgres", "repo": "pg-payment-cluster", "status": "failing"},
    {"id": "session-cache-redis", "name": "Redis Session Cache", "tier": 1, "team": "Data Infra", "lang": "Redis", "repo": "redis-sessions", "status": "operational"},
    {"id": "event-stream-kafka", "name": "Kafka Event Bus", "tier": 1, "team": "Data Infra", "lang": "Kafka", "repo": "kafka-events", "status": "operational"},
    {"id": "vault-hsm-store", "name": "HSM Encrypted Storage", "tier": 1, "team": "SecOps", "lang": "Hardware", "repo": "hsm-store", "status": "operational"},
    # Layer 5: External Partners & Gateways
    {"id": "visa-direct-gateway", "name": "Visa Direct Acquirer", "tier": 3, "team": "Integrations", "lang": "Java", "repo": "visa-gw", "status": "operational"},
    {"id": "mastercard-send-gateway", "name": "Mastercard Send Acquirer", "tier": 3, "team": "Integrations", "lang": "Java", "repo": "mc-send-gw", "status": "operational"},
    {"id": "stripe-fallback-proxy", "name": "Stripe Secondary Proxy", "tier": 3, "team": "Integrations", "lang": "Go", "repo": "stripe-proxy", "status": "operational"},
]

# 2. Explicit Dependencies ((source)-[:DEPENDS_ON]->(target))
# Notice: 'risk-scoring-engine' -> 'merchant-config-service' is intentionally omitted to simulate the missing catalog link
DEPENDENCIES = [
    # Edge -> Gateways
    {"src": "nexus-edge-gateway", "target": "nexus-api-gateway", "protocol": "gRPC", "timeout": 2000, "critical": True},
    # API Gateway -> Core
    {"src": "nexus-api-gateway", "target": "auth-service", "protocol": "REST", "timeout": 1500, "critical": True},
    {"src": "nexus-api-gateway", "target": "checkout-orchestrator", "protocol": "REST", "timeout": 5000, "critical": True},
    # Auth -> Redis
    {"src": "auth-service", "target": "session-cache-redis", "protocol": "RESP", "timeout": 300, "critical": True},
    # Checkout -> Core Services
    {"src": "checkout-orchestrator", "target": "payment-core", "protocol": "gRPC", "timeout": 4000, "critical": True},
    {"src": "checkout-orchestrator", "target": "fraud-detection-service", "protocol": "gRPC", "timeout": 2000, "critical": False},
    {"src": "checkout-orchestrator", "target": "notification-service", "protocol": "async", "timeout": 5000, "critical": False},
    # Payment Core -> Vault, Ledger, DB, Gateways
    {"src": "payment-core", "target": "card-vault", "protocol": "gRPC", "timeout": 1000, "critical": True},
    {"src": "payment-core", "target": "payment-db-cluster", "protocol": "SQL", "timeout": 3000, "critical": True},
    {"src": "payment-core", "target": "event-stream-kafka", "protocol": "KafkaTCP", "timeout": 2000, "critical": True},
    {"src": "payment-core", "target": "visa-direct-gateway", "protocol": "HTTPS", "timeout": 6000, "critical": False},
    {"src": "payment-core", "target": "mastercard-send-gateway", "protocol": "HTTPS", "timeout": 6000, "critical": False},
    {"src": "payment-core", "target": "stripe-fallback-proxy", "protocol": "HTTPS", "timeout": 8000, "critical": False},
    # Fraud -> Risk Engine
    {"src": "fraud-detection-service", "target": "risk-scoring-engine", "protocol": "gRPC", "timeout": 1200, "critical": True},
    # Card Vault -> HSM & Token Worker
    {"src": "card-vault", "target": "vault-hsm-store", "protocol": "PKCS11", "timeout": 800, "critical": True},
    {"src": "card-vault", "target": "tokenization-worker", "protocol": "gRPC", "timeout": 500, "critical": True},
    # Ledger & Reconciler -> Kafka & DB
    {"src": "ledger-service", "target": "event-stream-kafka", "protocol": "KafkaTCP", "timeout": 2000, "critical": True},
    {"src": "ledger-service", "target": "payment-db-cluster", "protocol": "SQL", "timeout": 4000, "critical": True},
    {"src": "reconciliation-worker", "target": "ledger-service", "protocol": "gRPC", "timeout": 5000, "critical": False},
    {"src": "reconciliation-worker", "target": "payment-db-cluster", "protocol": "SQL", "timeout": 5000, "critical": True},
]

# 3. Deployments
DEPLOYMENTS = [
    {
        "id": "DEP-4010",
        "service_id": "checkout-orchestrator",
        "version": "v3.12.0",
        "commit_sha": "f1a8c09",
        "deployed_at": "2026-10-15T09:30:00Z",
        "author": "devops@nexuspay.io",
        "status": "success",
        "environment": "production",
        "strategy": "canary",
    },
    {
        # Misleading correlation: deployed right before incident to auth-service
        "id": "DEP-4011",
        "service_id": "auth-service",
        "version": "v2.8.4",
        "commit_sha": "e9b211d",
        "deployed_at": "2026-10-15T10:12:00Z",
        "author": "secops@nexuspay.io",
        "status": "success",
        "environment": "production",
        "strategy": "rolling",
    },
    {
        # TRUE ROOT CAUSE RELEASE: payment-core pool leak / unindexed scan
        "id": "DEP-4012",
        "service_id": "payment-core",
        "version": "v4.1.0-rc2",
        "commit_sha": "a78df42",
        "deployed_at": "2026-10-15T10:14:30Z",
        "author": "payments-lead@nexuspay.io",
        "status": "success",
        "environment": "production",
        "strategy": "blue-green",
    },
    {
        # Historical Deployment
        "id": "DEP-3980",
        "service_id": "ledger-service",
        "version": "v1.19.2",
        "commit_sha": "b44d99a",
        "deployed_at": "2026-10-01T14:00:00Z",
        "author": "ledger-team@nexuspay.io",
        "status": "success",
        "environment": "production",
        "strategy": "rolling",
    },
]

# 4. Incidents
INCIDENTS = [
    {
        # ACTIVE SEV1: Payment processing collapse & cascading gateway timeouts
        "id": "INC-2026-8821",
        "title": "Payment Core Connection Starvation & High Error Rate",
        "severity": "SEV1",
        "status": "active",
        "started_at": "2026-10-15T10:15:00Z",
        "resolved_at": "",
        "summary": "Checkout orchestrator receiving HTTP 504 Gateway Timeouts from payment-core. Connection pool to payment-db-cluster saturated at 100%.",
        "affects": ["payment-core", "checkout-orchestrator", "nexus-api-gateway"],
    },
    {
        # HISTORICAL SEV2: Resolved via partition scaling
        "id": "INC-2026-7104",
        "title": "Kafka Partition Consumer Lag on Financial Ledger",
        "severity": "SEV2",
        "status": "resolved",
        "started_at": "2026-10-02T16:20:00Z",
        "resolved_at": "2026-10-02T17:45:00Z",
        "summary": "Ledger service fell 1.2M messages behind on settlement events due to consumer rebalance loop. Resolved by scaling consumer group concurrency.",
        "affects": ["ledger-service", "event-stream-kafka"],
    },
    {
        # INSUFFICIENT EVIDENCE SEV3: Intermittent blips
        "id": "INC-2026-9043",
        "title": "Sporadic 502 Bad Gateway Anomalies on Edge Ingress",
        "severity": "SEV3",
        "status": "investigating",
        "started_at": "2026-10-15T12:00:00Z",
        "resolved_at": "",
        "summary": "Brief 1-second 502 spikes reported by synthetic monitoring. Evidence inconclusive, baseline telemetry within normal bounds.",
        "affects": ["nexus-edge-gateway"],
    },
]

# 5. Alerts
ALERTS = [
    # INC-2026-8821 Alerts
    {"id": "ALT-101", "service_id": "payment-core", "name": "PaymentCore_HighLatency_p99", "severity": "critical", "source": "Prometheus", "timestamp": "2026-10-15T10:15:30Z", "desc": "Payment-core p99 latency spiked from 120ms to 8400ms", "metric": "http_request_duration_seconds", "val": 8.4},
    {"id": "ALT-102", "service_id": "payment-core", "name": "Postgres_PoolExhausted", "severity": "critical", "source": "Datadog", "timestamp": "2026-10-15T10:16:00Z", "desc": "HikariCP active database connections reached maximum pool size (100/100)", "metric": "hikaricp_active_connections", "val": 100.0},
    {"id": "ALT-103", "service_id": "checkout-orchestrator", "name": "Checkout_UpstreamTimeouts", "severity": "critical", "source": "Prometheus", "timestamp": "2026-10-15T10:16:45Z", "desc": "Circuit breaker OPEN on downstream call to payment-core", "metric": "circuit_breaker_state", "val": 1.0},
    {"id": "ALT-104", "service_id": "nexus-api-gateway", "name": "Gateway_504_Surge", "severity": "warning", "source": "Prometheus", "timestamp": "2026-10-15T10:17:10Z", "desc": "Rate of 504 Gateway Timeouts exceeded 15% threshold", "metric": "http_5xx_rate", "val": 18.2},
    # Misleading alert noise on auth-service
    {"id": "ALT-105", "service_id": "auth-service", "name": "Auth_TokenVerificationLag", "severity": "warning", "source": "CloudWatch", "timestamp": "2026-10-15T10:14:00Z", "desc": "Transient cache jitter during DEP-4011 rollout (auto-recovered in 30s)", "metric": "token_verify_duration", "val": 45.0},
    # Historical incident alert
    {"id": "ALT-089", "service_id": "ledger-service", "name": "Kafka_ConsumerLag_High", "severity": "critical", "source": "Prometheus", "timestamp": "2026-10-02T16:21:00Z", "desc": "Consumer group ledger-settlement lag exceeded 1,000,000 offsets", "metric": "kafka_consumer_lag", "val": 1240000.0},
]

# 6. Metric Observations
METRIC_OBSERVATIONS = [
    {"id": "MET-501", "name": "hikaricp_active_connections", "ts": "2026-10-15T10:16:00Z", "val": 100.0, "base": 24.0, "sigma": 5.8, "unit": "connections", "alert_id": "ALT-102"},
    {"id": "MET-502", "name": "http_request_duration_seconds", "ts": "2026-10-15T10:15:30Z", "val": 8.4, "base": 0.12, "sigma": 7.2, "unit": "seconds", "alert_id": "ALT-101"},
    {"id": "MET-503", "name": "http_5xx_rate", "ts": "2026-10-15T10:17:10Z", "val": 18.2, "base": 0.05, "sigma": 6.1, "unit": "percent", "alert_id": "ALT-104"},
]

# 7. Runbooks & Steps
RUNBOOKS = [
    {
        "id": "RBK-PAY-01",
        "title": "Payment Core Database Pool Mitigation",
        "service_id": "payment-core",
        "version": "2.1",
        "url": "https://wiki.nexuspay.io/runbooks/payment-core-db",
        "steps": [
            {"id": "STP-01", "step_number": 1, "action": "Verify DB Connection Saturation", "cmd": "SELECT count(*) FROM pg_stat_activity WHERE state='active';", "time_mins": 2},
            {"id": "STP-02", "step_number": 2, "action": "Rollback Recent Canary/Blue-Green Release", "cmd": "argocd app rollback payment-core --revision DEP-4010", "time_mins": 5},
            {"id": "STP-03", "step_number": 3, "action": "Drain Idle Connections via PgBouncer", "cmd": "kill -HUP pgbouncer", "time_mins": 3},
        ],
    },
    {
        "id": "RBK-KAFKA-04",
        "title": "Kafka Consumer Lag Scaling & Rebalance Recovery",
        "service_id": "ledger-service",
        "version": "1.4",
        "url": "https://wiki.nexuspay.io/runbooks/kafka-lag",
        "steps": [
            {"id": "STP-11", "step_number": 1, "action": "Inspect Partition Assignment", "cmd": "kafka-consumer-groups.sh --describe --group ledger-settlement", "time_mins": 3},
            {"id": "STP-12", "step_number": 2, "action": "Scale Ledger Worker Replicas", "cmd": "kubectl scale deployment ledger-service --replicas=8", "time_mins": 4},
        ],
    },
]

# 8. Investigations, Hypotheses, Evidence, Recovery Actions & Approvals
INVESTIGATIONS = [
    {
        "id": "INV-8821",
        "incident_id": "INC-2026-8821",
        "status": "in_progress",
        "started_at": "2026-10-15T10:18:00Z",
        "lead_agent": "TraceForge-Investigator-01",
        "hypotheses": [
            {
                "id": "HYP-01",
                "statement": "Database connection pool exhaustion on payment-db-cluster caused by slow query in DEP-4012",
                "confidence": 0.94,
                "status": "validated",
                "supports": [
                    {"id": "EVI-01", "type": "metric", "desc": "HikariCP active connections hit max capacity of 100 within 90s of DEP-4012 release", "conf": 0.98},
                    {"id": "EVI-02", "type": "log", "desc": "Postgres slow query log indicates seq scan on settlements table taking >6500ms", "conf": 0.95},
                ],
            },
            {
                "id": "HYP-02",
                "statement": "Authentication service token validation failure in DEP-4011 cascading to checkout",
                "confidence": 0.12,
                "status": "refuted",
                "contradicts": [
                    {"id": "EVI-03", "type": "trace", "desc": "Auth service response times normalized 30s post-deploy; checkout errors are strictly 504 on payment-core call", "conf": 0.92},
                ],
            },
        ],
    },
    {
        "id": "INV-7104",
        "incident_id": "INC-2026-7104",
        "status": "completed",
        "started_at": "2026-10-02T16:25:00Z",
        "lead_agent": "TraceForge-Investigator-01",
        "hypotheses": [
            {
                "id": "HYP-10",
                "statement": "Kafka partition imbalance caused high worker consumer lag",
                "confidence": 0.96,
                "status": "validated",
                "supports": [
                    {"id": "EVI-11", "type": "metric", "desc": "Lag metric concentrated on 2 partitions out of 16", "conf": 0.99},
                ],
            }
        ],
    },
]

# Historical resolution for INC-2026-7104
HISTORICAL_RESOLUTIONS = [
    {
        "incident_id": "INC-2026-7104",
        "action_id": "REC-7104",
        "action_type": "scale_workers",
        "target_service": "ledger-service",
        "status": "completed",
        "executed_at": "2026-10-02T17:30:00Z",
        "approval": {
            "id": "APP-7104",
            "approver": "oncall-infra@nexuspay.io",
            "role": "Staff SRE",
            "status": "approved",
            "decided_at": "2026-10-02T17:28:00Z",
        },
    }
]


def seed_graph(graph_name: Optional[str] = None) -> None:
    """Inserts or merges all nodes and edges deterministically into FalkorDB."""
    logger.info("Initializing schema indexes...")
    create_graph_schema_indexes(graph_name)

    graph = db_client.get_graph(graph_name)

    # 1. Services
    logger.info(f"Seeding {len(SERVICES)} Services...")
    for s in SERVICES:
        query = """
        MERGE (s:Service {id: $id})
        ON CREATE SET s.name = $name,
                      s.tier = $tier,
                      s.team = $team,
                      s.language = $language,
                      s.repository = $repo,
                      s.status = $status,
                      s.created_at = '2026-01-01T00:00:00Z'
        ON MATCH SET  s.name = $name,
                      s.tier = $tier,
                      s.team = $team,
                      s.status = $status
        """
        graph.query(query, {
            "id": s["id"],
            "name": s["name"],
            "tier": s["tier"],
            "team": s["team"],
            "language": s["lang"],
            "repo": s["repo"],
            "status": s["status"],
        })

    # 2. Dependencies
    logger.info(f"Seeding {len(DEPENDENCIES)} Service Dependencies...")
    for dep in DEPENDENCIES:
        query = """
        MATCH (src:Service {id: $src})
        MATCH (tgt:Service {id: $target})
        MERGE (src)-[r:DEPENDS_ON]->(tgt)
        ON CREATE SET r.protocol = $protocol,
                      r.timeout_ms = $timeout,
                      r.critical = $critical
        ON MATCH SET  r.protocol = $protocol,
                      r.timeout_ms = $timeout,
                      r.critical = $critical
        """
        graph.query(query, dep)

    # 3. Deployments
    logger.info(f"Seeding {len(DEPLOYMENTS)} Deployments...")
    for d in DEPLOYMENTS:
        query = """
        MATCH (s:Service {id: $service_id})
        MERGE (dep:Deployment {id: $id})
        ON CREATE SET dep.version = $version,
                      dep.commit_sha = $commit_sha,
                      dep.deployed_at = $deployed_at,
                      dep.author = $author,
                      dep.status = $status,
                      dep.environment = $environment
        MERGE (dep)-[r:DEPLOYED_TO]->(s)
        ON CREATE SET r.strategy = $strategy
        """
        graph.query(query, d)

    # 4. Incidents
    logger.info(f"Seeding {len(INCIDENTS)} Incidents...")
    for inc in INCIDENTS:
        query = """
        MERGE (i:Incident {id: $id})
        ON CREATE SET i.title = $title,
                      i.severity = $severity,
                      i.status = $status,
                      i.started_at = $started_at,
                      i.resolved_at = $resolved_at,
                      i.summary = $summary
        ON MATCH SET  i.title = $title,
                      i.severity = $severity,
                      i.status = $status,
                      i.resolved_at = $resolved_at,
                      i.summary = $summary
        """
        graph.query(query, {
            "id": inc["id"],
            "title": inc["title"],
            "severity": inc["severity"],
            "status": inc["status"],
            "started_at": inc["started_at"],
            "resolved_at": inc["resolved_at"],
            "summary": inc["summary"],
        })

        # Relate Incident -> Affected Services
        for svc_id in inc["affects"]:
            rel_query = """
            MATCH (i:Incident {id: $inc_id})
            MATCH (s:Service {id: $svc_id})
            MERGE (i)-[:AFFECTS]->(s)
            """
            graph.query(rel_query, {"inc_id": inc["id"], "svc_id": svc_id})

    # 5. Alerts
    logger.info(f"Seeding {len(ALERTS)} Alerts...")
    for alt in ALERTS:
        query = """
        MATCH (s:Service {id: $service_id})
        MERGE (a:Alert {id: $id})
        ON CREATE SET a.name = $name,
                      a.severity = $severity,
                      a.source = $source,
                      a.timestamp = $timestamp,
                      a.description = $desc,
                      a.metric_name = $metric,
                      a.value = $val
        MERGE (s)-[:PRODUCES_ALERT]->(a)
        """
        graph.query(query, alt)

    # 6. Metric Observations
    logger.info(f"Seeding {len(METRIC_OBSERVATIONS)} Metric Observations...")
    for met in METRIC_OBSERVATIONS:
        query = """
        MATCH (a:Alert {id: $alert_id})
        MERGE (m:MetricObservation {id: $id})
        ON CREATE SET m.metric_name = $name,
                      m.timestamp = $ts,
                      m.value = $val,
                      m.baseline = $base,
                      m.deviation_sigma = $sigma,
                      m.unit = $unit
        MERGE (a)-[:CORRELATES_WITH]->(m)
        """
        graph.query(query, met)

    # 7. Runbooks & Steps
    logger.info(f"Seeding {len(RUNBOOKS)} Runbooks and steps...")
    for rbk in RUNBOOKS:
        query = """
        MATCH (s:Service {id: $service_id})
        MERGE (r:Runbook {id: $id})
        ON CREATE SET r.title = $title,
                      r.version = $version,
                      r.url = $url
        MERGE (r)-[:APPLIES_TO]->(s)
        """
        graph.query(query, {
            "id": rbk["id"],
            "title": rbk["title"],
            "version": rbk["version"],
            "url": rbk["url"],
            "service_id": rbk["service_id"],
        })
        for step in rbk["steps"]:
            step_query = """
            MATCH (r:Runbook {id: $rbk_id})
            MERGE (st:RunbookStep {id: $step_id})
            ON CREATE SET st.step_number = $step_num,
                          st.action = $action,
                          st.command = $cmd,
                          st.estimated_time_mins = $time
            MERGE (r)-[:HAS_STEP {sequence: $step_num}]->(st)
            """
            graph.query(step_query, {
                "rbk_id": rbk["id"],
                "step_id": step["id"],
                "step_num": step["step_number"],
                "action": step.get("action", ""),
                "cmd": step.get("cmd") or step.get("command") or "",
                "time": step.get("time_mins") or step.get("estimated_time_mins") or 5,
            })

    # 8. Investigations, Hypotheses & Evidence
    logger.info(f"Seeding {len(INVESTIGATIONS)} Investigations & Evidences...")
    for inv in INVESTIGATIONS:
        inv_query = """
        MATCH (inc:Incident {id: $incident_id})
        MERGE (iv:Investigation {id: $id})
        ON CREATE SET iv.status = $status,
                      iv.started_at = $started_at,
                      iv.lead_agent = $lead_agent
        MERGE (iv)-[:INVESTIGATES]->(inc)
        """
        graph.query(inv_query, {
            "id": inv["id"],
            "incident_id": inv["incident_id"],
            "status": inv["status"],
            "started_at": inv["started_at"],
            "lead_agent": inv["lead_agent"],
        })

        for hyp in inv.get("hypotheses", []):
            hyp_query = """
            MATCH (iv:Investigation {id: $inv_id})
            MERGE (h:Hypothesis {id: $id})
            ON CREATE SET h.statement = $statement,
                          h.confidence = $confidence,
                          h.status = $status
            MERGE (iv)-[:EXPLORES_HYPOTHESIS]->(h)
            """
            graph.query(hyp_query, {
                "inv_id": inv["id"],
                "id": hyp["id"],
                "statement": hyp["statement"],
                "confidence": hyp["confidence"],
                "status": hyp["status"],
            })

            # Supporting evidence
            for evi in hyp.get("supports", []):
                evi_query = """
                MATCH (h:Hypothesis {id: $hyp_id})
                MATCH (iv:Investigation {id: $inv_id})
                MERGE (e:Evidence {id: $id})
                ON CREATE SET e.type = $type,
                              e.description = $desc,
                              e.confidence = $conf
                MERGE (h)-[:SUPPORTS {weight: $conf}]->(e)
                MERGE (iv)-[:HAS_EVIDENCE]->(e)
                """
                graph.query(evi_query, {
                    "hyp_id": hyp["id"],
                    "inv_id": inv["id"],
                    "id": evi["id"],
                    "type": evi["type"],
                    "desc": evi["desc"],
                    "conf": evi["conf"],
                })

            # Contradicting evidence
            for evi in hyp.get("contradicts", []):
                evi_query = """
                MATCH (h:Hypothesis {id: $hyp_id})
                MATCH (iv:Investigation {id: $inv_id})
                MERGE (e:Evidence {id: $id})
                ON CREATE SET e.type = $type,
                              e.description = $desc,
                              e.confidence = $conf
                MERGE (h)-[:CONTRADICTS {weight: $conf}]->(e)
                MERGE (iv)-[:HAS_EVIDENCE]->(e)
                """
                graph.query(evi_query, {
                    "hyp_id": hyp["id"],
                    "inv_id": inv["id"],
                    "id": evi["id"],
                    "type": evi["type"],
                    "desc": evi["desc"],
                    "conf": evi["conf"],
                })

    # 9. Historical Recovery Actions & Approvals
    for res in HISTORICAL_RESOLUTIONS:
        res_query = """
        MATCH (inc:Incident {id: $inc_id})
        MATCH (s:Service {id: $target_svc})
        MERGE (ra:RecoveryAction {id: $action_id})
        ON CREATE SET ra.action_type = $action_type,
                      ra.status = $status,
                      ra.executed_at = $executed_at
        MERGE (inc)-[:RESOLVED_BY]->(ra)
        MERGE (ra)-[:TARGETS]->(s)
        """
        graph.query(res_query, {
            "inc_id": res["incident_id"],
            "target_svc": res["target_service"],
            "action_id": res["action_id"],
            "action_type": res["action_type"],
            "status": res["status"],
            "executed_at": res["executed_at"],
        })

        app_info = res["approval"]
        app_query = """
        MATCH (ra:RecoveryAction {id: $action_id})
        MERGE (ap:Approval {id: $id})
        ON CREATE SET ap.approver = $approver,
                      ap.role = $role,
                      ap.status = $status,
                      ap.decided_at = $decided_at
        MERGE (ra)-[:REQUIRES]->(ap)
        """
        graph.query(app_query, {
            "action_id": res["action_id"],
            "id": app_info["id"],
            "approver": app_info["approver"],
            "role": app_info["role"],
            "status": app_info["status"],
            "decided_at": app_info["decided_at"],
        })

    logger.info("Graph seeding completed successfully.")


if __name__ == "__main__":
    seed_graph()
