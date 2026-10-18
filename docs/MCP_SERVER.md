# TraceForge MCP Server — Graph Investigation Agent Tools

TraceForge Phase 1 exposes a high-integrity, real-data Model Context Protocol (MCP) server for autonomous and human-assisted investigation agents. Built for the **WeMakeDevs × FalkorDB Graph Hacks track: Agents That Act on Connected Data**.

All tools query and operate directly on the live FalkorDB graph (`traceforge`) and reuse the repository's core deterministic scoring, topological traversal, and isolated graph-surgery engines.

---

## 1. Transport & Architecture

- **MCP SDK**: Official Python `mcp>=2.3.0` (`mcp.server.mcpserver.MCPServer`).
- **Transport**: `stdio` transport. All agent communications follow the JSON-RPC standard over standard input/output.
- **Protocol Hygiene**: Diagnostic logging, query traces, and exceptions are strictly routed to `sys.stderr` via Python's standard `logging` library. `sys.stdout` remains 100% protocol-clean for JSON-RPC messages.
- **Service Separation**: Core investigation queries and scoring logic are encapsulated in [`backend/app/core/mcp_services.py`](file:///f:/SessionSmith/backend/app/core/mcp_services.py). The MCP server wrapper in [`backend/app/mcp_server.py`](file:///f:/SessionSmith/backend/app/mcp_server.py) and the existing FastAPI REST routes share the exact same underlying logic.

---

## 2. Implemented Tools & Schemas

### 1. `trace_dependency_path`
- **Purpose**: Discovers directed dependency chains between two real service nodes in FalkorDB.
- **Inputs**:
  - `source_service_id` (string, required): Upstream service ID (e.g. `api-gateway`, `checkout-service`).
  - `target_service_id` (string, required): Downstream target dependency ID (e.g. `payment-service`, `orders-db`).
  - `max_depth` (integer, optional, default: `3`): Traversal hop limit (clamped between 1 and 5).
- **Behavior**:
  - Validates existence of both services in FalkorDB.
  - Queries directed `(:Service)-[:DEPENDS_ON*1..max_depth]->(:Service)` paths.
  - Returns path count, hop length, node sequences, and relationship types.
  - Returns `path_found: false` when no path exists (without failing or fabricating paths).

### 2. `get_blast_radius`
- **Purpose**: Computes downstream impact when a service fails or suffers performance degradation.
- **Inputs**:
  - `service_id` (string, required): Target service node ID (e.g. `orders-db`).
  - `max_depth` (integer, optional, default: `3`): Maximum upstream dependency traversal depth.
- **Behavior**:
  - Traverses incoming dependency relationships `(dependent:Service)-[:DEPENDS_ON*1..max_depth]->(target:Service)`.
  - Returns total affected count, unique affected services (id, name, minimum hop distance), and representative dependency chains.
  - Avoids duplicate node reporting and runaway traversals.

### 3. `inspect_incident_evidence`
- **Purpose**: Retrieves all graph-grounded evidence associated with an active incident.
- **Inputs**:
  - `incident_id` (string, required): Incident identifier (e.g. `INC-2024-001`).
- **Behavior**:
  - Fetches the incident brief, linked alerts, metric anomalies with $\sigma$ deviations, recent deployment events, and evidence debt (missing observability links).
  - Explicitly annotates epistemic status (`OBSERVED`, `INFERRED_TOPOLOGY`, `HISTORICAL`).
  - Distinguishes unknown/missing fields explicitly without fabricating timestamps or data.

### 4. `compare_hypotheses`
- **Purpose**: Evaluates and ranks potential root-cause hypotheses using TraceForge's deterministic multi-factor scoring engine.
- **Inputs**:
  - `incident_id` (string, required): Incident identifier.
- **Behavior**:
  - Computes exact mathematical factor weights: Temporal Proximity ($w=0.30$), Topological Proximity ($w=0.25$), Telemetry Severity ($w=0.25$), Change Risk ($w=0.20$), and Evidence Debt Penalty ($\Delta=-0.15$).
  - Never fabricates scores or confidence percentages.
  - Outputs ranked list, raw composite scores, factor breakdowns, and supporting/contradicting evidence.

### 5. `simulate_graph_intervention`
- **Purpose**: Executes an isolated, counterfactual graph experiment to test a mitigation hypothesis.
- **Inputs**:
  - `incident_id` (string, required): Incident identifier.
  - `action` (string, required): Supported intervention type: `remove_dependency`, `isolate_service`, `rollback_deployment`, or `remove_evidence`.
  - `source_service_id` (string, optional): Required for dependency surgery.
  - `target_service_id` (string, optional): Required for dependency surgery.
  - `target_id` (string, optional): Target entity ID for isolation, rollback, or evidence modification.
- **Behavior**:
  - Clones baseline graph (`traceforge`) to an ephemeral graph (`traceforge_exp_<uuid>`).
  - Applies surgical modification on the isolated graph.
  - Re-evaluates hypothesis rankings and blast radius on the experiment graph.
  - Computes deltas against baseline.
  - **Guaranteed Cleanup**: Destroys the ephemeral experiment graph in a `finally` block even upon errors.
  - **Zero Baseline Mutation**: Baseline graph is 100% untouched.

---

## 3. Starting the Server

Ensure FalkorDB is running (e.g. via `docker-compose up -d falkordb` on port 6379) and the Python environment has dependencies installed (`pip install -r backend/requirements.txt`).

### Windows (PowerShell)
```powershell
$env:PYTHONPATH = "f:\SessionSmith\backend"
f:\SessionSmith\.venv\Scripts\python.exe -m app.mcp_server
```

### Linux / macOS
```bash
export PYTHONPATH="./backend"
python3 -m app.mcp_server
```

---

## 4. Connecting MCP Clients

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "traceforge": {
      "command": "f:\\SessionSmith\\.venv\\Scripts\\python.exe",
      "args": ["-m", "app.mcp_server"],
      "env": {
        "PYTHONPATH": "f:\\SessionSmith\\backend",
        "FALKORDB_HOST": "localhost",
        "FALKORDB_PORT": "6379"
      }
    }
  }
}
```

### Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "traceforge": {
      "command": "f:\\SessionSmith\\.venv\\Scripts\\python.exe",
      "args": ["-m", "app.mcp_server"],
      "env": {
        "PYTHONPATH": "f:\\SessionSmith\\backend"
      }
    }
  }
}
```

---

## 5. Automated Tests

The MCP test suite is located in [`backend/tests/test_mcp_tools.py`](file:///f:/SessionSmith/backend/tests/test_mcp_tools.py).

Run the tests:
```powershell
pytest backend/tests/test_mcp_tools.py -v
```

All 13 specialized test scenarios cover:
- Tool registration & schema reflection
- Forward path resolution & no-path detection
- Unregistered service/incident error handling
- Depth limits and clamping
- Blast radius calculations & leaf node handling
- Evidence epistemics & missing relationship debt
- Scoring consistency with core algorithms
- Ephemeral graph isolation, delta calculation & guaranteed teardown
- Invalid intervention action rejection

---

## 6. Autonomous Investigation Orchestrator

TraceForge provides an autonomous investigation agent that acts on connected data in FalkorDB via the 5 MCP tools.

### Multi-Incident Adaptive Sequences
The agent dynamically reasons about evidence rather than executing a hardcoded sequence:
- **Incident A (`INC-2026-8821` — Payment Core Pool Starvation)**:
  1. `inspect_incident_evidence`: Uncovers active alerts on `checkout-orchestrator`, `payment-core`, and database connection metrics.
  2. `trace_dependency_path`: Follows synchronous gRPC corridor `checkout-orchestrator` -> `payment-core`.
  3. `trace_dependency_path`: Follows SQL link `payment-core` -> `payment-db-cluster`.
  4. `get_blast_radius`: Computes upstream blast radius of `payment-core` (6 affected client services).
  5. `compare_hypotheses`: Compares `payment-db-cluster` pool leak vs misleading `auth-service` release `DEP-4011`.
  6. `simulate_graph_intervention`: Executes isolated counterfactual Graph Surgery (`remove_dependency` on `payment-db-cluster`), verifying that severing the link contracts downstream blast radius by 5 services without touching production.
- **Incident B (`INC-2026-7104` — Kafka Partition Lag / Ledger)**:
  1. `inspect_incident_evidence`: Identifies partition lag on `ledger-service` and message hub `event-stream-kafka`.
  2. `get_blast_radius`: Immediately checks downstream queue dependencies for `event-stream-kafka`.
  3. `trace_dependency_path`: Traces `ledger-service` -> `event-stream-kafka` transport protocol.
  4. `compare_hypotheses`: Evaluates consumer group rebalance and partition imbalance. Skips graph surgery because no structural dependency modification is justified.

### API Endpoint
```http
POST /api/v1/investigation/orchestrate/{incident_id}
```
Returns a fully structured timeline of tool calls, selection rationales, parameters, durations, and epistemic statuses (`OBSERVED`, `INFERRED`, `SIMULATED`, `HISTORICAL`).

