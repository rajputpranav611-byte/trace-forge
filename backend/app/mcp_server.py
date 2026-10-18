"""Model Context Protocol (MCP) Server for TraceForge Graph Incident Investigation.

Implements the official Model Context Protocol server exposing the 5 required
graph-powered tools for AI agents acting on connected operational data in FalkorDB.
"""

import sys
import logging
from typing import Optional, Dict, Any
from mcp.server.mcpserver import MCPServer
from app.core.mcp_services import (
    trace_dependency_path_service,
    get_blast_radius_service,
    inspect_incident_evidence_service,
    compare_hypotheses_service,
    simulate_graph_intervention_service,
)

# Ensure diagnostic logs go strictly to stderr so stdio JSON-RPC transport remains clean
logger = logging.getLogger("traceforge.mcp")
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [TraceForge-MCP] %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Initialize MCP Server instance
mcp_server = MCPServer(
    name="traceforge-graph-investigation",
    instructions="TraceForge operational incident investigation & counterfactual graph simulator backed by FalkorDB.",
    version="1.0.0",
)


@mcp_server.tool(
    name="trace_dependency_path",
    description=(
        "Find relevant directed dependency paths between two real service nodes in FalkorDB. "
        "Returns the path chains, length, and relationship types according to the directed graph schema. "
        "Enforces bounded traversal depth (1-5, default 3)."
    ),
)
def trace_dependency_path(
    source_service_id: str,
    target_service_id: str,
    max_depth: int = 3,
) -> Dict[str, Any]:
    """Finds directed dependency paths between two service nodes in FalkorDB."""
    try:
        return trace_dependency_path_service(
            source_service_id=source_service_id,
            target_service_id=target_service_id,
            max_depth=max_depth,
        )
    except Exception as exc:
        logger.error(f"Error in trace_dependency_path: {exc}")
        return {
            "error": str(exc),
            "source_service_id": source_service_id,
            "target_service_id": target_service_id,
            "path_found": False,
        }


@mcp_server.tool(
    name="get_blast_radius",
    description=(
        "Identify downstream services potentially affected by an incident or failing service in FalkorDB. "
        "Traverses directed relationships (dependent)-[:DEPENDS_ON*]->(service) up to max_depth. "
        "Returns affected service names, IDs, tiers, and minimum hop distances."
    ),
)
def get_blast_radius(
    service_id: str,
    max_depth: int = 3,
) -> Dict[str, Any]:
    """Identifies downstream services depending on the specified service node."""
    try:
        return get_blast_radius_service(
            service_id=service_id,
            max_depth=max_depth,
        )
    except Exception as exc:
        logger.error(f"Error in get_blast_radius: {exc}")
        return {
            "error": str(exc),
            "service_id": service_id,
            "total_affected_downstream_services": 0,
        }


@mcp_server.tool(
    name="inspect_incident_evidence",
    description=(
        "Retrieve all correlated evidence relevant to an incident from FalkorDB. "
        "Returns affected services, correlated alerts, metric observations with standard deviations, "
        "candidate deployments, and detects missing relationship debt. "
        "Explicitly labels observed facts, inferred relationships, and synthetic items."
    ),
)
def inspect_incident_evidence(
    incident_id: str,
    max_depth: int = 3,
) -> Dict[str, Any]:
    """Retrieves all telemetry, topology, and historical evidence for an incident."""
    try:
        return inspect_incident_evidence_service(
            incident_id=incident_id,
            max_depth=max_depth,
        )
    except Exception as exc:
        logger.error(f"Error in inspect_incident_evidence: {exc}")
        return {
            "error": str(exc),
            "incident_id": incident_id,
        }


@mcp_server.tool(
    name="compare_hypotheses",
    description=(
        "Compare competing root-cause hypotheses using TraceForge's deterministic scoring engine. "
        "Evaluates supporting evidence, contradicting facts, temporal proximity, and causal graph paths. "
        "Returns ranked hypotheses with auditable mathematical factor breakdowns."
    ),
)
async def compare_hypotheses(
    incident_id: str,
    max_depth: int = 3,
) -> Dict[str, Any]:
    """Ranks competing root cause hypotheses using real deterministic graph scoring."""
    try:
        return await compare_hypotheses_service(
            incident_id=incident_id,
            max_depth=max_depth,
        )
    except Exception as exc:
        logger.error(f"Error in compare_hypotheses: {exc}")
        return {
            "error": str(exc),
            "incident_id": incident_id,
            "hypotheses": [],
        }


@mcp_server.tool(
    name="simulate_graph_intervention",
    description=(
        "Run a controlled counterfactual graph experiment in FalkorDB using an isolated graph copy. "
        "Supported actions: 'remove_dependency', 'isolate_service', 'rollback_deployment', 'remove_evidence'. "
        "Evaluates causal shift, blast radius contraction, and hypothesis rank deltas without mutating baseline data. "
        "Clearly labeled as a non-destructive simulation."
    ),
)
async def simulate_graph_intervention(
    incident_id: str,
    action_type: str,
    source_id: str,
    target_id: Optional[str] = None,
    relationship_type: str = "DEPENDS_ON",
    justification: str = "Agent Counterfactual Investigation",
) -> Dict[str, Any]:
    """Executes an isolated counterfactual graph surgery simulation and returns structured diffs."""
    try:
        return await simulate_graph_intervention_service(
            incident_id=incident_id,
            action_type=action_type,
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            justification=justification,
        )
    except Exception as exc:
        logger.error(f"Error in simulate_graph_intervention: {exc}")
        return {
            "error": str(exc),
            "simulation": True,
            "production_mutated": False,
            "incident_id": incident_id,
        }


def main():
    """Starts the TraceForge MCP Server on stdio transport for client integration."""
    logger.info("Starting TraceForge MCP Server (stdio transport)...")
    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    main()
